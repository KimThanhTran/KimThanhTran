"""Draws the two GitHub stats cards of the profile README as SVG files, with no third-party service.

    GITHUB_TOKEN=... python scripts/generate_stats.py

Reads public data through the GitHub GraphQL API and writes assets/stats.svg and assets/languages.svg.
The workflow in .github/workflows/stats.yml runs it every day and commits the result.
Only the standard library is used.
"""
import html
import json
import os
import urllib.request
from pathlib import Path

USER = os.environ.get("STATS_USER", "KimThanhTran")
# repositories left out of the language chart (comma separated names)
EXCLUDE = {name.strip() for name in os.environ.get("STATS_EXCLUDE_REPOS", "TOOL").split(",") if name.strip()}
OUT = Path(__file__).resolve().parents[1] / "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Same palette as the previous "tokyonight" cards
BG, BORDER, TITLE, TEXT, ICON, MUTED = "#0D1117", "#30363d", "#70a5fd", "#38bdae", "#bf91f3", "#8b949e"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN (a token that can read public data is enough).")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GitHub returned an error: {payload.get('errors')}")
    return payload["data"]["user"]


def card(width, height, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{html.escape(title)}">'
        f'<title>{html.escape(title)}</title>'
        f'<rect x="0.5" y="0.5" rx="6" width="{width - 1}" height="{height - 1}" fill="{BG}" stroke="{BORDER}"/>'
        f'<text x="25" y="35" fill="{TITLE}" font-family="{FONT}" font-size="18" font-weight="600">{html.escape(title)}</text>'
        f'{body}</svg>\n'
    )


def stats_svg(user):
    contributions = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]
    rows = [
        ("★", "Stars earned", sum(repo["stargazerCount"] for repo in repos)),
        ("●", "Commits, last 12 months", contributions["totalCommitContributions"]),
        ("⇄", "Pull requests, last 12 months", contributions["totalPullRequestContributions"]),
        ("◆", "Repositories contributed to", contributions["totalRepositoryContributions"]),
        ("▣", "Public repositories", user["repositories"]["totalCount"]),
    ]
    lines = []
    for index, (icon, label, value) in enumerate(rows):
        y = 66 + index * 25
        lines.append(
            f'<text x="25" y="{y}" fill="{ICON}" font-family="{FONT}" font-size="14">{icon}</text>'
            f'<text x="50" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" font-weight="600">{html.escape(label)}:</text>'
            f'<text x="330" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" font-weight="700" text-anchor="end">{value:,}</text>'
        )
    title = f"{user['name'] or user['login']}'s GitHub stats"
    return card(360, 200, title, "".join(lines))


def languages_svg(user):
    totals, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        if repo["name"] in EXCLUDE:
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"

    everything = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:6]

    bar_x, bar_width, x = 25, 250, 25.0
    segments = []
    for name, size in top:
        share = size / everything
        segments.append(f'<rect x="{x:.1f}" y="52" width="{bar_width * share:.1f}" height="8" fill="{colors[name]}"/>')
        x += bar_width * share
    bar = (
        f'<clipPath id="bar"><rect x="{bar_x}" y="52" width="{bar_width}" height="8" rx="4"/></clipPath>'
        f'<rect x="{bar_x}" y="52" width="{bar_width}" height="8" rx="4" fill="#21262d"/>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )

    legend = []
    for index, (name, size) in enumerate(top):
        column, row = index % 2, index // 2
        lx, ly = 25 + column * 130, 88 + row * 24
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[name]}"/>'
            f'<text x="{lx + 17}" y="{ly}" fill="{TEXT}" font-family="{FONT}" font-size="12">'
            f'{html.escape(name)} {size / everything:.1%}</text>'
        )
    note = (
        f'<text x="25" y="178" fill="{MUTED}" font-family="{FONT}" font-size="10">'
        f'By bytes of code in public repositories</text>'
    )
    return card(300, 200, "Most used languages", bar + "".join(legend) + note)


def main():
    user = fetch()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_svg(user), encoding="utf-8", newline="\n")
    (OUT / "languages.svg").write_text(languages_svg(user), encoding="utf-8", newline="\n")
    print(f"Wrote {OUT / 'stats.svg'} and {OUT / 'languages.svg'}")


if __name__ == "__main__":
    main()
