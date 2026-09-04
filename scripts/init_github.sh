#!/usr/bin/env bash
# Push the local memes-pages repository to GitHub.
# Usage:
#   ./scripts/init_github.sh <your-github-username> [remote-url]
# Requires: git push access (SSH key or HTTPS token), or the `gh` CLI.
set -euo pipefail

USERNAME="${1:?usage: init_github.sh <github-username> [remote-url]}"
REMOTE="${2:-git@github.com:${USERNAME}/memes-pages.git}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_DIR"

if command -v gh >/dev/null 2>&1; then
  echo "→ Creating GitHub repo via gh CLI…"
  gh repo create memes-pages --private --source=. --remote=origin --push || true
else
  echo "→ Adding remote ${REMOTE}"
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REMOTE"
  echo "→ Pushing main…"
  git push -u origin main
fi

echo "✔ Done. Next: follow docs/DEPLOYMENT.md to deploy on Railway."
