"""Contract tests for the profile README.

These are static assertions: they run in CI without a cluster or network access.
They guard the invariants we care about so a bad edit fails before merge.
"""
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_exists_and_nonempty():
    assert README.is_file()
    assert len(_text()) > 500


def test_required_sections_present():
    text = _text()
    for heading in [
        "## 📊 GitHub Stats",
        "## 🚀 Now",
        "## 🛠 Featured Projects",
        "## 🧬 Tech Stack",
        "## 📖 The Real Story",
        "## 🗓 Journey",
        "## 🧠 Consciousness Exploration Archive",
        "## 🤝 Contributions to Open Source",
        "## 🔄 Recently Merged",
        "## 📫 Connect",
    ]:
        assert heading in text, f"missing section: {heading}"


def test_no_paywalled_trophy_card():
    text = _text()
    assert "github-profile-trophy" not in text
    # The trophy service renders "402 Payment Required" when its card is
    # paywalled. Match that phrase, not a bare "402": profile READMEs
    # legitimately link PR numbers that contain the digits (e.g. /pull/1402).
    assert "402 Payment Required" not in text


def test_no_nix_claims_in_stack():
    # Fleet is Omarchy-only; Nix/NixOS must not appear in the active stack line.
    text = _text()
    stack_line = next((l for l in text.splitlines() if l.startswith("**Languages:**")), "")
    assert "Nix" not in stack_line, "Nix leaked back into Languages line"
    infra_line = next((l for l in text.splitlines() if l.startswith("**Infra:**")), "")
    assert "NixOS" not in infra_line


def test_recent_markers_present():
    text = _text()
    assert "<!--RECENT:START-->" in text
    assert "<!--RECENT:END-->" in text


def test_featured_projects_table_has_rows():
    text = _text()
    # at least 5 data rows in the featured projects table
    in_table = False
    rows = 0
    for line in text.splitlines():
        if line.startswith("| Project | Language |"):
            in_table = True
            continue
        if in_table:
            if line.startswith("| ---"):
                continue
            if line.startswith("|"):
                rows += 1
            else:
                break
    assert rows >= 5, f"expected >=5 featured rows, got {rows}"


def test_no_raw_todo_or_placeholder():
    text = _text().lower()
    for bad in ["todo", "lorem ipsum", "xxx"]:
        assert bad not in text, f"placeholder text found: {bad}"