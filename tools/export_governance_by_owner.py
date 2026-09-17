#!/usr/bin/env python3
"""
Pull CCF/governance proposals per epoch from analytics.qubic.li, tagged with
its proposerOwner label (qli/minerlab/jetski/YNRE/none), so the dashboard can
show who is actually proposing/steering governance, not just who holds seats.

Usage: python3 tools/export_governance_by_owner.py
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "governance_by_owner.json"
BASE = "https://analytics.qubic.li/api/stats"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    epochs = get_json(f"{BASE}/proposals/epochs")["epochs"]
    all_proposals = []
    for ep in epochs:
        try:
            d = get_json(f"{BASE}/proposals/{ep}")
        except Exception as e:
            print(f"epoch {ep}: failed ({e})")
            continue
        for item in d.get("items", []):
            all_proposals.append({
                "epoch": item.get("epoch"),
                "contractName": item.get("contractName"),
                "proposalClassName": item.get("proposalClassName"),
                "proposerIdentity": item.get("proposerIdentity"),
                "proposerOwner": item.get("proposerOwner"),
                "url": item.get("url"),
                "proposalTime": item.get("proposalTime"),
                "isCancelled": item.get("isCancelled"),
            })
        print(f"epoch {ep}: {len(d.get('items', []))} proposals")

    from collections import Counter
    owner_tally = Counter(p["proposerOwner"] or "none" for p in all_proposals)

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "analytics.qubic.li /api/stats/proposals/{epoch}",
        "totalProposals": len(all_proposals),
        "byProposerOwner": dict(owner_tally),
        "proposals": all_proposals,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT}: {len(all_proposals)} proposals, by owner: {dict(owner_tally)}")


if __name__ == "__main__":
    main()
