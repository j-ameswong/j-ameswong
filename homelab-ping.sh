#!/usr/bin/env bash
# Run from cron on home server
#   0 */6 * * *  GH_PAT=... /opt/profile/homelab-ping.sh
# GH_PAT: fine-grained token scoped to ONLY your profile repo, Contents: read & write.
set -euo pipefail
REPO="j-ameswong/j-ameswong"

UPTIME=$(uptime -p | sed 's/^up //')
CONTAINERS=$(docker ps -q 2>/dev/null | wc -l) || CONTAINERS=0

curl -fsS -X POST "https://api.github.com/repos/${REPO}/dispatches" \
  -H "Authorization: Bearer ${GH_PAT}" \
  -H "Accept: application/vnd.github+json" \
  -d "$(cat <<JSON
{"event_type": "home-server-update",
 "client_payload": {"lines": [
   "🖥️ Server up ${UPTIME}",
   "🐳 ${CONTAINERS} containers running"
 ]}}
JSON
)"
