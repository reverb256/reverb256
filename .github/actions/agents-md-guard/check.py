#!/usr/bin/env python3
"""Validate the fleet-wide AGENTS.md pointer and retired policy wording."""
import argparse
import pathlib
import re
import sys

OLD_HEADER = "## Git hygiene rules for every agent on this fleet"
NEW_HEADER = "## Git hygiene rules (fleet-wide)"
REQUIRED_LINES = (
    "Fleet-wide rules are maintained in one place: the `homelab-ops` repo,",
    "`AGENTS-shared/` directory:",
    "- `merge-policy.md` — AI review, evidence comment, `ready-to-merge` gate",
    "`bin/agents-md-check.py --check` from the homelab-ops repo.",
)
STALE_POINTER = "PR merge workflow (AI agents label and merge)"
NEGATIONS = ("never", "must not", "do not", "cannot", "don't")
DIRECT_MERGE = re.compile(
    r"AI agents handle all merges|AI agents merge:\s*open a PR|"
    r"AI-driven (?:auto-merge|merge)|may push directly to\s+`?main`?",
    re.IGNORECASE,
)
OPTIONAL_LABEL = re.compile(
    r"(?:ready-to-merge|label)\s+(?:is\s+)?(?:not required|optional)|"
    r"(?:not required|optional)\s*:\s*(?:ready-to-merge|label)|"
    r"no\s+(?:ready-to-merge\s+)?label\s+(?:is\s+)?required",
    re.IGNORECASE,
)


def validate_text(text, name="AGENTS.md"):
    errors = []
    if OLD_HEADER in text:
        errors.append(f"{name}: duplicated fleet-rules block is retired; use the canonical pointer")
    if NEW_HEADER not in text:
        errors.append(f"{name}: missing canonical fleet-rules pointer")
    for line in REQUIRED_LINES:
        if line not in text:
            errors.append(f"{name}: missing canonical pointer line: {line}")
    if STALE_POINTER in text:
        errors.append(f"{name}: stale merge-policy pointer wording")
    for number, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        negated = any(word in low for word in NEGATIONS)
        if "gh pr merge" in low and not negated:
            errors.append(f"{name}:{number}: direct agent merge instruction is forbidden")
        if DIRECT_MERGE.search(line):
            errors.append(f"{name}:{number}: retired direct-merge policy wording")
        if OPTIONAL_LABEL.search(line):
            errors.append(f"{name}:{number}: ready-to-merge label must be required")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", default=["AGENTS.md"])
    args = parser.parse_args(argv)
    errors = []
    for name in args.files:
        path = pathlib.Path(name)
        if not path.is_file():
            errors.append(f"{name}: file not found")
            continue
        errors.extend(validate_text(path.read_text(encoding="utf-8"), name))
    for error in errors:
        if ":" in error and error.rsplit(":", 1)[-1].isdigit():
            file_name, line = error.rsplit(":", 1)
            print(f"::error file={file_name},line={line}::{error}")
        else:
            print(f"::error::{error}")
    if errors:
        print(f"AGENTS.md guard failed with {len(errors)} error(s).")
        return 1
    print(f"AGENTS.md guard passed for {len(args.files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
