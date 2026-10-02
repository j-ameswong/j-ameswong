#!/usr/bin/env bash
# Setup systemd timer on home server
set -euo pipefail
REPO="j-ameswong/j-ameswong"

UPTIME=$(uptime -p | sed 's/^up //')
CONTAINERS=$(docker ps -q 2>/dev/null | wc -l) || CONTAINERS=0

# Counts only: hostnames and IPs stay off the public README.
if TAILNET=$(tailscale status --json 2>/dev/null | jq -r '
    (.Peer // {}) as $peers
    | "\(.BackendState): \($peers | map(select(.Online)) | length)/\($peers | length) peers online"'); then
  [[ $TAILNET == Running:* ]] && TAILNET_ICON="🟢" || TAILNET_ICON="🔴"
else
  TAILNET="unreachable" TAILNET_ICON="🔴"
fi

curl -fsS -X POST "https://api.github.com/repos/${REPO}/dispatches" \
  -H "Authorization: Bearer ${GH_PAT}" \
  -H "Accept: application/vnd.github+json" \
  -d "$(cat <<JSON
{"event_type": "home-server-update",
 "client_payload": {"lines": [
   "🖥️ Server up ${UPTIME}",
   "🐳 ${CONTAINERS} containers running",
   "${TAILNET_ICON} Tailnet ${TAILNET}"
 ]}}
JSON
)"
