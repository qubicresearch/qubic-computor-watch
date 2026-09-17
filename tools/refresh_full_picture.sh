#!/bin/bash
# Refreshes pulse timeseries + owner-attribution snapshot + governance-by-owner,
# commits and pushes if anything changed. Invoked by qubic-dashboard-export.timer.
set -euo pipefail

REPO_DIR="/home/kevarms/qubic-computor-watch"
cd "$REPO_DIR"

python3 tools/export_pulse_timeseries.py
python3 tools/export_owner_history.py
python3 tools/export_governance_by_owner.py

git add docs/pulse_timeseries.json docs/owner_revenue_history.json docs/governance_by_owner.json
if git diff --cached --quiet; then
    echo "refresh_full_picture: no changes to commit"
    exit 0
fi

git commit -m "Refresh network pulse + owner attribution + governance data [automated]"
git pull --rebase origin main
git push origin main
