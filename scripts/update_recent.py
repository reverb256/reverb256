#!/usr/bin/env python3
"""Regenerate the "Recently Merged" block in README.md from GitHub.

Run in CI with GITHUB_TOKEN available. Writes the file in place.
"""
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
USER = "reverb256"
LIMIT = 8


def fetch_merged_prs():
    url = (
        "https://api.github.com/search/issues"
        f"?q=author:{USER}+is:pr+is:merged&sort=created&order=desc&per_page={LIMIT}"
    )
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    items = data.get("items", [])
    out = []
    for it in items:
        repo = it.get("repository_url", "").rsplit("/", 2)[-2:]
        repo_name = "/".join(repo) if len(repo) == 2 else it.get("repository_url", "")
        # repository_url looks like https://api.github.com/repos/owner/name
        ru = it.get("repository_url", "")
        if "/repos/" in ru:
            repo_name = ru.split("/repos/", 1)[1]
        out.append((repo_name, it.get("title", ""), it.get("html_url", ""), it.get("created_at", "")[:10]))
    return out


def render(prs):
    lines = ["<!--RECENT:START-->"]
    if not prs:
        lines.append("_No recently merged PRs found._")
    else:
        lines.append("| Date | Project | PR |")
        lines.append("| --- | --- | --- |")
        for repo, title, url, date in prs:
            lines.append(f"| {date} | `{repo}` | [{title}]({url}) |")
    lines.append("")
    lines.append("_Auto-updated weekly by GitHub Actions._")
    lines.append("<!--RECENT:END-->")
    return "\n".join(lines)


def main():
    prs = fetch_merged_prs()
    text = README.read_text(encoding="utf-8")
    new_block = render(prs)
    pattern = re.compile(r"<!--RECENT:START-->.*?<!--RECENT:END-->", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit("RECENT markers not found in README.md")
    new_text = pattern.sub(new_block, text, count=1)
    README.write_text(new_text, encoding="utf-8")
    print(f"Updated with {len(prs)} PRs")


if __name__ == "__main__":
    main()
