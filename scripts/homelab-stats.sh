#!/usr/bin/env bash
# Print the homelab status lines as JSON (the shape update_profile.py reads from data/home.json).
set -euo pipefail

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

jq -n \
  --arg uptime "🖥️ Server up ${UPTIME}" \
  --arg containers "🐳 ${CONTAINERS} containers running" \
  --arg tailnet "${TAILNET_ICON} Tailnet ${TAILNET}" \
  '{lines: [$uptime, $containers, $tailnet]}'
