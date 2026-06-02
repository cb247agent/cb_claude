#!/usr/bin/env bash
# deploy-dashboard.sh — Build and push CB247 dashboard to GitHub Pages
#
# Prerequisites:
#   1. GitHub repo already exists at github.com/YOUR_USERNAME/ChasingBetter
#   2. GitHub Pages enabled: repo Settings → Pages → Source: Deploy from branch → main → /docs
#
# Usage:
#   bash scripts/deploy-dashboard.sh

set -e
cd "$(dirname "$0")/.."

echo "=== CB247 Dashboard Deploy ==="

# 1. Regenerate dashboard from latest data
echo "→ Building dashboard..."
.venv/bin/python3.13 scripts/bake-public-dashboard.py

# 2. Commit and push
echo "→ Committing..."
git add docs/index.html
git diff --cached --quiet && echo "  No changes to deploy." && exit 0

git commit -m "dashboard: update $(date '+%Y-%m-%d %H:%M')"
git push

echo ""
echo "✅ Deployed! Your dashboard will be live in ~1 minute at:"
echo "   https://cb247agent.github.io/cb_claude/"
