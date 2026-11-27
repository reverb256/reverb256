"""Tests for the reusable AGENTS.md policy guard."""
import importlib.util
from pathlib import Path

ACTION = Path(__file__).resolve().parent.parent / ".github" / "actions" / "agents-md-guard" / "check.py"
SPEC = importlib.util.spec_from_file_location("agents_md_guard", ACTION)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

CANONICAL = """## Git hygiene rules (fleet-wide)

Fleet-wide rules are maintained in one place: the `homelab-ops` repo,
`AGENTS-shared/` directory:
- `git-hygiene.md` — staging, forbidden files, gates, identity, pre-push checks
- `merge-policy.md` — AI review, evidence comment, `ready-to-merge` gate
- `fleet-conventions.md` — deployment, budget, secrets, SPOC, hard rules

Do not duplicate these blocks locally. Check drift with
`bin/agents-md-check.py --check` from the homelab-ops repo.
"""


def test_canonical_pointer_passes():
    assert guard.validate_text(CANONICAL) == []


def test_negated_direct_merge_reference_passes():
    text = CANONICAL + "\nAgents must not run `gh pr merge`.\n"
    assert guard.validate_text(text) == []


def test_no_agent_direct_merge_reference_passes():
    text = CANONICAL + "\nNo agent runs `gh pr merge`; the workflow merges.\n"
    assert guard.validate_text(text) == []


def test_old_block_fails():
    errors = guard.validate_text(guard.OLD_HEADER + "\n" + CANONICAL)
    assert any("duplicated fleet-rules block" in error for error in errors)


def test_stale_pointer_fails():
    errors = guard.validate_text(CANONICAL.replace("AI review, evidence comment, `ready-to-merge` gate", guard.STALE_POINTER))
    assert any("stale merge-policy pointer" in error for error in errors)


def test_missing_pointer_fails():
    errors = guard.validate_text("# Project rules\n")
    assert any("missing canonical fleet-rules pointer" in error for error in errors)


def test_direct_merge_instruction_fails():
    text = CANONICAL + "\nAI reviews and runs `gh pr merge` when green.\n"
    errors = guard.validate_text(text)
    assert any("direct agent merge instruction" in error for error in errors)


def test_direct_push_instruction_fails():
    text = CANONICAL + "\nAI agents may push directly to `main` after CI passes.\n"
    errors = guard.validate_text(text)
    assert any("retired direct-merge policy" in error for error in errors)


def test_optional_label_fails():
    text = CANONICAL + "\nThe ready-to-merge label is not required.\n"
    errors = guard.validate_text(text)
    assert any("label must be required" in error for error in errors)


def test_human_approval_wording_passes():
    text = CANONICAL + "\nHuman approval is not required, but an agent must review before labeling.\n"
    assert guard.validate_text(text) == []


def test_owner_only_review_and_label_policy_fails():
    retired = (
        "The owner reviews and gates merges; other agents open PRs.",
        "The owner adds `ready-to-merge` after reading the diff.",
        "Only the owner adds or removes `ready-to-merge`.",
        "Until an owner is assigned, Reverb gates merges.",
    )
    for line in retired:
        errors = guard.validate_text(CANONICAL + "\n" + line + "\n")
        assert any("owner-only review or label policy" in error for error in errors), line


def test_ai_review_and_label_policy_passes():
    text = CANONICAL + "\nAI agents review the exact head, post evidence, and add `ready-to-merge`; the workflow merges.\n"
    assert guard.validate_text(text) == []
