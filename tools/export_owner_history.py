#!/usr/bin/env python3
"""
Pull analytics.qubic.li's own third-party computor-owner attribution
(qli's own site self-labels qli/minerlab/jetski/YNRE-owned computor seats)
for every epoch it has data for, so the dashboard can show the trend over
time rather than one epoch's snapshot.

Usage: python3 tools/export_owner_history.py
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "owner_revenue_history.json"
BASE = "https://analytics.qubic.li/api/stats"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    epochs = get_json(f"{BASE}/owners/epochs")
    by_epoch = {}
    for ep in epochs:
        try:
            d = get_json(f"{BASE}/computor-revenue/by-owner?epoch={ep}")
        except Exception as e:
            print(f"epoch {ep}: failed ({e})")
            continue
        by_epoch[ep] = {
            "computorsWithOwner": d.get("computorsWithOwner"),
            "computorsWithoutOwner": d.get("computorsWithoutOwner"),
            "totalAttributedRevenue": d.get("totalAttributedRevenue"),
            "owners": [
                {"owner": o["owner"], "computorCount": o["computorCount"], "totalRevenue": o["totalRevenue"]}
                for o in d.get("owners", [])
            ],
        }
        print(f"epoch {ep}: {len(by_epoch[ep]['owners'])} owners, {d.get('computorsWithOwner')} attributed")

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "analytics.qubic.li /api/stats/computor-revenue/by-owner (qli's own self-reported attribution)",
        "epochs": by_epoch,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
