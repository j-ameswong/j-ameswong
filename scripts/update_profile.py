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
]


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


def recent_activity(limit=5):
    lines, seen = [], set()
    for event in gh(f"/users/{USER}/events/public?per_page=50"):
        repo = event["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        kind, payload = event["type"], event.get("payload", {})
        if kind == "PushEvent" and ("push", repo) not in seen:
            seen.add(("push", repo))
            lines.append(f"- Pushed to {link}")
        elif kind == "PullRequestEvent" and payload.get("action") == "opened":
            pr = payload["pull_request"]
            lines.append(f"- Opened PR [#{pr['number']}]({pr['html_url']}) in {link}")
        elif kind == "ReleaseEvent":
            lines.append(f"- Released `{payload['release']['tag_name']}` of {link}")
        elif kind == "CreateEvent" and payload.get("ref_type") == "repository":
            lines.append(f"- Created {link}")
        elif kind == "WatchEvent":
            lines.append(f"- Starred {link}")
        if len(lines) >= limit:
            break
    return "\n".join(lines) or "- Quiet day Zzzzz. Probably reading docs."


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
            health = "🔴 unreachable"
        elif status < 400:
            health = f"🟢 up · {ms} ms"
        else:
            health = f"🔴 HTTP {status}"
        lines.append(f"- [{name}]({url}) {health} · [source](https://github.com/{repo})")
    return "\n".join(lines)


def homelab_section():
    if not HOMELAB_PAYLOAD.exists():
        return None
    payload = json.loads(HOMELAB_PAYLOAD.read_text())
    return "\n".join(f"- {line}" for line in payload.get("lines", [])[:6]) or None


def render_card(repos, today):
    own = [r for r in repos if not r["fork"] and not r["archived"]]
    stars = sum(r["stargazers_count"] for r in own)
    langs = Counter(r["language"] for r in own if r["language"]).most_common(3)
    # Deterministic "repo of the day": same pick all day, rotates daily.
    featured = sorted(own, key=lambda r: r["name"])[today.toordinal() % len(own)] if own else None

    feat_name = escape(featured["name"]) if featured else "nothing yet"
    feat_desc = escape(((featured or {}).get("description") or "No description.")[:70])
    lang_text = escape(" · ".join(name for name, _ in langs) or "—")

    CARD.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="560" height="170" viewBox="0 0 560 170">
  <style>
    .bg {{ fill: #ffffff; stroke: #d0d7de; }}
    .h {{ font: 600 15px system-ui, sans-serif; fill: #1f2328; }}
    .t {{ font: 13px system-ui, sans-serif; fill: #57606a; }}
    .n {{ font: 700 22px system-ui, sans-serif; fill: #0969da; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #0d1117; stroke: #30363d; }}
      .h {{ fill: #e6edf3; }} .t {{ fill: #8b949e; }} .n {{ fill: #58a6ff; }}
    }}
  </style>
  <rect class="bg" x="0.5" y="0.5" width="559" height="169" rx="10"/>
  <text class="h" x="20" y="32">📅 {today:%A, %d %B %Y}</text>
  <text class="n" x="20" y="72">{len(own)}</text><text class="t" x="20" y="92">repos</text>
  <text class="t" x="240" y="72">Top languages</text><text class="h" x="240" y="92">{lang_text}</text>
  <text class="t" x="20" y="128">Repo of the day</text>
  <text class="h" x="20" y="150">{feat_name} <tspan class="t">— {feat_desc}</tspan></text>
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
