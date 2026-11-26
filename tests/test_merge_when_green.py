"""Behavioural tests for the label-gated merge workflow script."""
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "merge-when-green.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "merge-when-green.yml"
REPO = "reverb256/reverb256"
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as h: h.write(json.dumps(args) + "\n")
with open(os.environ["FAKE_GH_SCENARIO"]) as h: s = json.load(h)
if args[:2] == ["api", "repos/%s/pulls/6" % os.environ["GH_REPO"]]:
    if s.get("pr_error"): raise SystemExit("pull read failed")
    print(json.dumps(s["pr"]))
elif args[:2] == ["api", "repos/%s/commits/abc/check-runs?per_page=100" % os.environ["GH_REPO"]]:
    if s.get("checks_error"): raise SystemExit("check read failed")
    print(json.dumps(s["checks"] if "--jq" in args else {"check_runs": s["checks"]}))
elif args[:2] == ["pr", "merge"]: raise SystemExit(s.get("merge_rc", 0))
else: raise SystemExit("unexpected gh call: %r" % args)
'''


def pr(**overrides):
    value = {"state": "open", "head": {"sha": "abc", "repo": {"full_name": REPO}},
             "base": {"ref": "main"}, "draft": False, "mergeable": True,
             "labels": [{"name": "ready-to-merge"}]}
    value.update(overrides)
    return value


def checks(**overrides):
    values = {n: {"name": n, "id": 1, "status": "completed", "conclusion": "success"}
              for n in ("pytest", "lint", "lychee")}
    for name, fields in overrides.items(): values[name].update(fields)
    return list(values.values())


def run_gate(tmp_path, scenario=None, event_name="pull_request_target", event=None):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    scenario_path, event_path, log_path = (tmp_path / n for n in ("scenario.json", "event.json", "gh.log"))
    scenario_path.write_text(json.dumps(scenario or {"pr": pr(), "checks": checks()}))
    event_path.write_text(json.dumps(event if event is not None else {"pull_request": {"number": 6}}))
    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"], GH_TOKEN="test",
               GH_REPO=REPO, EVENT_NAME=event_name, EVENT_PATH=str(event_path),
               FAKE_GH_SCENARIO=str(scenario_path), FAKE_GH_LOG=str(log_path))
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = [json.loads(x) for x in log_path.read_text().splitlines()] if log_path.exists() else []
    return result, calls


def merged(calls): return any(c[:2] == ["pr", "merge"] for c in calls)


def test_green_labelled_pr_merges(tmp_path):
    result, calls = run_gate(tmp_path)
    assert result.returncode == 0, result.stderr
    assert calls[-1] == ["pr", "merge", "6", "--repo", REPO, "--squash", "--delete-branch"]


@pytest.mark.parametrize("scenario", [
    {"pr": pr(labels=[]), "checks": checks()},
    {"pr": pr(), "checks": checks(pytest={"status": "in_progress", "conclusion": None})},
    {"pr": pr(), "checks": checks(lint={"conclusion": "failure"})},
    {"pr": pr(), "checks": [c for c in checks() if c["name"] != "lychee"]},
    {"pr": pr(head={"sha": "abc", "repo": {"full_name": "fork/repo"}}), "checks": checks()},
    {"pr": pr(state="closed"), "checks": checks()},
    {"pr": pr(draft=True), "checks": checks()},
    {"pr": pr(mergeable=False), "checks": checks()},
    {"pr": pr(), "checks": checks() + [{"name": "pytest", "id": 2, "status": "in_progress", "conclusion": None}]},
])
def test_refusals_never_merge(tmp_path, scenario):
    result, calls = run_gate(tmp_path, scenario)
    assert result.returncode == 0, result.stderr
    assert not merged(calls)


@pytest.mark.parametrize("scenario", [
    {"pr_error": True},
    {"pr": pr(), "checks": checks(), "checks_error": True},
])
def test_unreadable_state_fails_closed(tmp_path, scenario):
    result, calls = run_gate(tmp_path, scenario)
    assert result.returncode != 0
    assert not merged(calls)


def test_workflow_run_resolves_pr(tmp_path):
    result, calls = run_gate(tmp_path, event_name="workflow_run",
                             event={"workflow_run": {"pull_requests": [{"number": 6}]}})
    assert result.returncode == 0, result.stderr
    assert merged(calls)


def test_workflow_run_without_pr_skips_without_api(tmp_path):
    result, calls = run_gate(tmp_path, event_name="workflow_run",
                             event={"workflow_run": {"pull_requests": []}})
    assert result.returncode == 0, result.stderr
    assert calls == []


def test_workflow_delegates_logic_to_script():
    text = WORKFLOW.read_text()
    assert 'workflows: ["Tests", "Markdown lint", "Link check"]' in text
    assert "types: [labeled, synchronize, reopened, ready_for_review]" in text
    assert "contents: write" in text and "checks: read" in text
    assert "run: bash scripts/merge-when-green.sh" in text
