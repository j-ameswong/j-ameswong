#!/usr/bin/env bash
# Refresh the profile README from the homelab and push it (replaces the old GitHub Action).
# Installed to /opt/profile/profile-update.sh (next to homelab-stats.sh) and run by
# profile-update.service. It works in its own clone, so it lives outside that clone to avoid
# rewriting itself mid-run.
set -euo pipefail

REMOTE="git@github.com:j-ameswong/j-ameswong.git"
BRANCH="main"
REPO_DIR="${STATE_DIRECTORY:-/var/lib/profile-update}/repo"

if [[ ! -d $REPO_DIR/.git ]]; then
  git clone --branch "$BRANCH" "$REMOTE" "$REPO_DIR"
  git -C "$REPO_DIR" config user.name "homelab[bot]"
  git -C "$REPO_DIR" config user.email "homelab-bot@users.noreply.github.com"
fi
cd "$REPO_DIR"

# This clone belongs to the bot: always start from whatever is on GitHub.
git fetch --quiet origin "$BRANCH"
git reset --quiet --hard "origin/$BRANCH"

mkdir -p data
"$(dirname "$0")/homelab-stats.sh" > data/home.json
GH_USER=j-ameswong python3 scripts/update_profile.py

git add -A
if git diff --cached --quiet; then
  echo "No changes."
  exit 0
fi
git commit --quiet -m "chore: refresh profile ($(date -u +%F))"

# Someone may have pushed while we ran; rebase once and retry.
if ! git push --quiet origin "HEAD:$BRANCH"; then
  git pull --quiet --rebase origin "$BRANCH"
  git push --quiet origin "HEAD:$BRANCH"
fi
echo "Pushed $(git rev-parse --short HEAD)."
