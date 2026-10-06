#!/usr/bin/env python3
"""Refresh the dynamic sections of the profile README and redraw the daily SVG card.

Stdlib only, so it runs the same in GitHub Actions and on a home server.
"""
import datetime
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

USER = os.environ.get("GH_USER", "j-ameswong")
TOKEN = os.environ.get("GITHUB_TOKEN")
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CARD = ROOT / "assets" / "daily-card.svg"
HOMELAB_PAYLOAD = ROOT / "data" / "home.json"
# (name, public URL, source repo)
DEPLOYMENTS = [
    ("assign-me", "https://assignme-weld.vercel.app/", "j-ameswong/assign-me"),
    ("uxhack", "https://uxhack-snakeup.vercel.app/signup", "j-ameswong/uxhack"),
    ("assessment-manager", "https://assessment-manager-fawn.vercel.app/", "j-ameswong/assessment-management"),
    ("UniConnect","https://uniconnect-portfolio.vercel.app/", "j-ameswong/mentee-mentor-matching"),
    ("bad-apple-ify","https://bad-apple-ify.vercel.app/", "j-ameswong/bad-apple-ify")
]
# homelab-ping.sh still sends emoji-prefixed lines; swap them for octicons on the way in.
HOMELAB_ICONS = {"🖥️": "clock", "🐳": "package", "🟢": "dot-green", "🔴": "dot-red"}
# Left out of the language bar: clashroyaletest is ~22 MB of HTML and drowns out everything else.
LANGUAGE_SKIP_REPOS = {"clashroyaletest"}
TOP_LANGUAGES = 5
# GitHub linguist colours for the card's language bar.
LANG_COLORS = {
    "Java": "#b07219", "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#663399", "Shell": "#89e051", "Lua": "#000080", "Go": "#00ADD8",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Rust": "#dea584", "Kotlin": "#A97BFF",
    "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883", "Svelte": "#ff3e00", "Dockerfile": "#384d54",
}
# Octicons (MIT, github.com/primer/octicons) drawn inline on the card.
OCTICON_CALENDAR = "M4.75 0a.75.75 0 01.75.75V2h5V.75a.75.75 0 011.5 0V2h1.25c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0113.25 16H2.75A1.75 1.75 0 011 14.25V3.75C1 2.784 1.784 2 2.75 2H4V.75A.75.75 0 014.75 0zm0 3.5h8.5a.25.25 0 01.25.25V6h-11V3.75a.25.25 0 01.25-.25h2zm-2.25 4v6.75c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25V7.5h-11z"
OCTICON_REPO = "M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z"
OCTICON_SPARKLE = "M8.5.75a.75.75 0 00-1.5 0v5.19L4.391 3.33a.75.75 0 10-1.06 1.061L5.939 7H.75a.75.75 0 000 1.5h5.19l-2.61 2.609a.75.75 0 101.061 1.06L7 9.561v5.189a.75.75 0 001.5 0V9.56l2.609 2.61a.75.75 0 101.06-1.061L9.561 8.5h5.189a.75.75 0 000-1.5H9.56l2.61-2.609a.75.75 0 00-1.061-1.06L8.5 5.939V.75z"


def gh(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER},
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def replace_section(text, name, body, inline=False):
    sep = "" if inline else "\n"
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}{sep}{body}{sep}{m.group(2)}", text)


def icon(name):
    return f'<img src="assets/icons/{name}.svg" width="14" height="14" alt=""/>'


def recent_activity(limit=5):
    lines, seen = [], set()
    for event in gh(f"/users/{USER}/events/public?per_page=50"):
        repo = event["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        kind, payload = event["type"], event.get("payload", {})
        if kind == "PushEvent" and ("push", repo) not in seen:
            seen.add(("push", repo))
            lines.append(f"{icon('commit')} Pushed to {link}")
        elif kind == "PullRequestEvent" and payload.get("action") == "opened":
            pr = payload["pull_request"]
            lines.append(f"{icon('pr')} Opened PR [#{pr['number']}]({pr['html_url']}) in {link}")
        elif kind == "ReleaseEvent":
            lines.append(f"{icon('tag')} Released `{payload['release']['tag_name']}` of {link}")
        elif kind == "CreateEvent" and payload.get("ref_type") == "repository":
            lines.append(f"{icon('repo')} Created {link}")
        elif kind == "WatchEvent":
            lines.append(f"{icon('star')} Starred {link}")
        if len(lines) >= limit:
            break
    return "<br/>\n".join(lines) or "Quiet day Zzzzz. Probably reading docs."


def probe(url):
    """Return (HTTP status, latency in ms), or (None, None) if the host never answered."""
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-status"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
    except urllib.error.HTTPError as err:
        status = err.code
    except OSError:
        return None, None
    return status, round((time.monotonic() - start) * 1000)


def deployments_section():
    lines = []
    for name, url, repo in DEPLOYMENTS:
        status, ms = probe(url)
        if status is None:
            health = f"{icon('dot-red')} unreachable"
        elif status < 400:
            health = f"{icon('dot-green')} up · {ms} ms"
        else:
            health = f"{icon('dot-red')} HTTP {status}"
        lines.append(f"- [{name}]({url}) {health} · [repo](https://github.com/{repo})")
    return "\n".join(lines)


def homelab_section():
    if not HOMELAB_PAYLOAD.exists():
        return None
    payload = json.loads(HOMELAB_PAYLOAD.read_text())
    lines = []
    for line in payload.get("lines", [])[:6]:
        for emoji, name in HOMELAB_ICONS.items():
            if line.startswith(emoji):
                line = f"{icon(name)} {line.removeprefix(emoji).lstrip()}"
                break
        lines.append(line)
    return "<br/>\n".join(lines) or None


def octicon(path, x, y, cls):
    return f'<path class="{cls}" transform="translate({x} {y})" fill-rule="evenodd" d="{path}"/>'


def language_bytes(repos):
    """Bytes of code per language, summed over every repo's GitHub language breakdown."""
    totals = Counter()
    for repo in repos:
        if repo["name"] in LANGUAGE_SKIP_REPOS:
            continue
        totals.update(gh(f"/repos/{repo['full_name']}/languages"))
    return totals


def language_bar(counts, x=44, y=100, width=496):
    """Classic metrics-style bar: top languages by bytes of code, everything else in grey."""
    total = sum(counts.values()) or 1
    segments, cursor = [], x
    for name, count in counts.most_common(TOP_LANGUAGES):
        w = width * count / total
        segments.append(f'<rect x="{cursor:.1f}" y="{y}" width="{w:.1f}" height="8" fill="{LANG_COLORS.get(name, "#959da5")}"/>')
        cursor += w

    # One flowing <text> so spacing follows the real glyph widths.
    legend = "".join(
        f'<tspan dx="{16 if i else 0}" fill="{LANG_COLORS.get(name, "#959da5")}">●</tspan> {escape(name)}'
        for i, (name, _) in enumerate(counts.most_common(TOP_LANGUAGES))
    ) or "—"

    return f"""<clipPath id="bar"><rect x="{x}" y="{y}" width="{width}" height="8" rx="5"/></clipPath>
  <g clip-path="url(#bar)"><rect x="{x}" y="{y}" width="{width}" height="8" fill="#d1d5da"/>{"".join(segments)}</g>
  <text class="f" x="{x}" y="{y + 30}">{legend}</text>"""


def render_card(repos, today):
    own = [r for r in repos if not r["fork"] and not r["archived"]]
    counts = language_bytes(own)
    # Deterministic "repo of the day": same pick all day, rotates daily.
    featured = sorted(own, key=lambda r: r["name"])[today.toordinal() % len(own)] if own else None

    feat_name = escape(featured["name"]) if featured else "nothing yet"
    feat_desc = escape(((featured or {}).get("description") or "No description.")[:70])

    CARD.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="560" height="220" viewBox="0 0 560 220">
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .h1 {{ font-size: 18px; font-weight: 700; fill: #0366d6; }}
    .h2 {{ font-size: 16px; fill: #0366d6; }}
    .h3 {{ font-size: 14px; fill: #0366d6; }}
    .f {{ font-size: 13px; fill: #777; }}
    .b {{ font-weight: 600; }}
    .hi {{ fill: #0366d6; }}
    .fi {{ fill: #959da5; }}
    @media (prefers-color-scheme: dark) {{
      .h1, .h2, .h3, .hi {{ fill: #58a6ff; }}
      .f {{ fill: #8b949e; }}
    }}
  </style>
  {octicon(OCTICON_CALENDAR, 12, 9, "hi")}
  <text class="h1" x="36" y="23">{today:%A, %d %B %Y}</text>

  {octicon(OCTICON_REPO, 12, 47, "hi")}
  <text class="h2" x="36" y="60">{len(own)} Repositories</text>
  <text class="h3" x="44" y="88">Most used languages</text>
  {language_bar(counts)}

  {octicon(OCTICON_SPARKLE, 12, 152, "hi")}
  <text class="h2" x="36" y="165">Repo of the day</text>
  {octicon(OCTICON_REPO, 20, 177, "fi")}
  <text class="f b" x="44" y="190">{feat_name}</text>
  <text class="f" x="44" y="209">{feat_desc}</text>
</svg>
""", encoding="utf-8")


def main():
    today = datetime.datetime.now(datetime.timezone.utc)
    repos = gh(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed")

    text = README.read_text(encoding="utf-8")
    text = replace_section(text, "ACTIVITY", recent_activity())
    text = replace_section(text, "DEPLOYMENTS", deployments_section())
    if (lab := homelab_section()):
        text = replace_section(text, "HOMELAB", lab)
    text = replace_section(text, "UPDATED", today.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    README.write_text(text, encoding="utf-8")

    CARD.parent.mkdir(exist_ok=True)
    render_card(repos, today)


if __name__ == "__main__":
    main()
