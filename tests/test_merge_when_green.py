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
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\n")
with open(os.environ["FAKE_GH_SCENARIO"], encoding="utf-8") as handle:
    scenario = json.load(handle)
if args[:2] == ["api", "repos/%s/pulls/6" % os.environ["GH_REPO"]]:
    if scenario.get("pr_error"):
        print("pull read failed", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(scenario["pr"]))
elif args[:2] == ["api", "repos/%s/commits/abc/check-runs?per_page=100" % os.environ["GH_REPO"]]:
    if scenario.get("checks_error"):
        print("check read failed", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(scenario["checks"] if "--jq" in args else {"check_runs": scenario["checks"]}))
elif args[:2] == ["pr", "merge"]:
    raise SystemExit(scenario.get("merge_rc", 0))
else:
    print("unexpected gh call: %r" % args, file=sys.stderr)
    raise SystemExit(2)
'''


def pr(**overrides):
    value = {
        "state": "open",
        "head": {"sha": "abc", "repo": {"full_name": REPO}},
        "base": {"ref": "main"},
        "draft": False,
        "mergeable": True,
        "labels": [{"name": "ready-to-merge"}],
    }
    value.update(overrides)
    return value


def checks(**overrides):
    values = {
        name: {"name": name, "id": 1, "status": "completed", "conclusion": "success"}
        for name in ("pytest", "lint", "lychee")
    }
    for name, fields in overrides.items():
        values[name].update(fields)
    return list(values.values())


def run_gate(tmp_path, *, scenario=None, event_name="pull_request_target", event=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario or {"pr": pr(), "checks": checks()}))
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event if event is not None else {"pull_request": {"number": 6}}))
    log_path = tmp_path / "gh.log"
    env = os.environ.copy()
    env.update({
        "PATH": str(bin_dir) + os.pathsep + env["PATH"],
        "GH_TOKEN": "test-token",
        "GH_REPO": REPO,
        "EVENT_NAME": event_name,
        "EVENT_PATH": str(event_path),
        "FAKE_GH_SCENARIO": str(scenario_path),
        "FAKE_GH_LOG": str(log_path),
    })
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
    return result, calls


def merged(calls):
    return any(call[:2] == ["pr", "merge"] for call in calls)


def test_green_labelled_pr_merges(tmp_path):
    result, calls = run_gate(tmp_path)
    assert result.returncode == 0, result.stderr
    assert merged(calls)
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
    result, calls = run_gate(tmp_path, scenario=scenario)
    assert result.returncode == 0, result.stderr
    assert not merged(calls)


def test_unreadable_state_fails_closed(tmp_path):
    result, calls = run_gate(tmp_path, scenario={"pr_error": True})
    assert result.returncode != 0
    assert not merged(calls)


def test_unreadable_checks_fail_closed(tmp_path):
    result, calls = run_gate(tmp_path, scenario={"pr": pr(), "checks": checks(), "checks_error": True})
    assert result.returncode != 0
    assert not merged(calls)


def test_workflow_run_resolves_pr(tmp_path):
    event = {"workflow_run": {"pull_requests": [{"number": 6}]}}
    result, calls = run_gate(tmp_path, event_name="workflow_run", event=event)
    assert result.returncode == 0, result.stderr
    assert merged(calls)


def test_workflow_run_without_pr_skips_without_api(tmp_path):
    event = {"workflow_run": {"pull_requests": []}}
    result, calls = run_gate(tmp_path, event_name="workflow_run", event=event)
    assert result.returncode == 0, result.stderr
    assert calls == []


def test_workflow_delegates_logic_to_script():
    text = WORKFLOW.read_text()
    assert 'workflows: ["Tests", "Markdown lint", "Link check"]' in text
    assert "types: [labeled, synchronize, reopened, ready_for_review]" in text
    assert "contents: write" in text and "checks: read" in text
    assert "run: bash scripts/merge-when-green.sh" in text
    assert "${{" not in text.split("run: bash scripts/merge-when-green.sh", 1)[1]
