#!/usr/bin/env python3
"""Generate a self-hosted stats SVG for the profile README.

No third-party services: pulls from the GitHub API and writes assets/stats.svg.
Run in CI with GITHUB_TOKEN. Robust against paywalls and outages.
"""
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "stats.svg"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
USER = "reverb256"


def api(path):
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch():
    user = api(f"/users/{USER}")
    repos = []
    page = 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    langs = Counter(r.get("language") for r in repos if r.get("language"))
    top = langs.most_common(5)
    return {
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "stars": stars,
        "forks": forks,
        "top": top,
    }


def bar(x, y, w, h, fill):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}"/>'


def render(d):
    # tokyonight-ish palette
    bg = "#1a1b26"
    fg = "#c0caf5"
    muted = "#565f89"
    accent = "#7aa2f7"
    accent2 = "#bb9af7"
    green = "#9ece6a"

    w, h = 495, 195
    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub stats for {USER}">')
    parts.append(f'<rect width="{w}" height="{h}" rx="10" fill="{bg}"/>')
    parts.append(f'<text x="25" y="35" font-family="Segoe UI, Ubuntu, sans-serif" font-size="18" font-weight="700" fill="{fg}">{USER} · GitHub stats</text>')
    parts.append(f'<text x="25" y="55" font-family="Segoe UI, Ubuntu, sans-serif" font-size="11" fill="{muted}">self-hosted · refreshed weekly · no third-party service</text>')

    # stat tiles
    tiles = [
        ("Public repos", d["public_repos"], accent),
        ("Followers", d["followers"], accent2),
        ("Total stars", d["stars"], green),
        ("Total forks", d["forks"], "#e0af68"),
    ]
    tx = 25
    for label, val, color in tiles:
        parts.append(f'<text x="{tx}" y="95" font-family="Segoe UI, Ubuntu, sans-serif" font-size="26" font-weight="700" fill="{color}">{val}</text>')
        parts.append(f'<text x="{tx}" y="115" font-family="Segoe UI, Ubuntu, sans-serif" font-size="12" fill="{muted}">{label}</text>')
        tx += 118

    # top languages bar
    parts.append(f'<text x="25" y="145" font-family="Segoe UI, Ubuntu, sans-serif" font-size="13" font-weight="600" fill="{fg}">Top languages (by repo count)</text>')
    top = d["top"]
    total = sum(c for _, c in top) or 1
    bx, by, bw, bh = 25, 155, 445, 12
    x = bx
    colors = [accent, accent2, green, "#e0af68", "#f7768e"]
    for i, (lang, cnt) in enumerate(top):
        seg = int(bw * cnt / total)
        parts.append(bar(x, by, seg, bh, colors[i % len(colors)]))
        x += seg
    # legend
    lx = 25
    for i, (lang, cnt) in enumerate(top):
        parts.append(f'<circle cx="{lx + 5}" cy="182" r="4" fill="{colors[i % len(colors)]}"/>')
        parts.append(f'<text x="{lx + 13}" y="186" font-family="Segoe UI, Ubuntu, sans-serif" font-size="10" fill="{muted}">{lang} ({cnt})</text>')
        lx += 95
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    d = fetch()
    svg = render(d)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUT} ({d})")


if __name__ == "__main__":
    main()
