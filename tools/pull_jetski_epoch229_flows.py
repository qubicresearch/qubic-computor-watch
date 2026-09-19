#!/usr/bin/env python3
"""
Full in/out flow map for all three JETSKI wallets, confined strictly to
epoch 229's real, empirically-confirmed tick range [77700885, 79301927]
(from our own qubic-pulse live-polled data, not a possibly-stale boundaries
file), amount >= 2,000,000 QU (standing investigation floor).
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "docs" / "jetski_epoch229_flows.json"

LO_TICK = 77700885
HI_TICK = 79301927
FLOOR = "2000000"

JETSKI = {
    "JETSKIYUBUPF": "JETSKIYUBUPFUCODLCBAJNFVCINABCOQIEXEZWNWMAFGBKPBOFTUCECCCSXG",
    "JETSKIQRDEIV": "JETSKIQRDEIVUDRAXYUVZOBHJAMCWFSOJBDKBPRDKCWSCHQHDBJHCPIEJUAH",
    "JETSKIMZKTSL": "JETSKIMZKTSLXCGBKJQNNSOBLFQDTCYBJPFLYGHVRFSITZNCDHCKSSRAESFM",
}


def curl_json(payload):
    r = subprocess.run(["curl", "-s", "-X", "POST", "https://rpc.qubic.org/query/v1/getEventLogs",
                         "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
                        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


def pull_side(addr, key, direction, max_pages=45):
    results = []
    offset = 0
    size = 100
    while offset < max_pages * size:
        d = curl_json({"filters": {key: addr}, "ranges": {"amount": {"gte": FLOOR}},
                       "pagination": {"offset": offset, "size": size}})
        hits = d.get("eventLogs", [])
        if not hits:
            break
        oldest_reached = False
        for e in hits:
            t = e["quTransfer"]
            if LO_TICK <= e["tickNumber"] <= HI_TICK:
                results.append({"direction": direction, "counterparty": t["destination"] if direction == "OUT" else t["source"],
                                 "amount": int(t["amount"]), "tick": e["tickNumber"]})
            if e["tickNumber"] < LO_TICK:
                oldest_reached = True
        print(f"  {addr[:14]} {direction} offset {offset}: {len(hits)} hits, {len(results)} in-window so far")
        offset += size
        if oldest_reached:
            break
    return results


def main():
    result = {}
    for label, addr in JETSKI.items():
        print(f"=== {label} ===")
        out_tx = pull_side(addr, "source", "OUT")
        in_tx = pull_side(addr, "destination", "IN")
        result[label] = {"address": addr, "out": out_tx, "in": in_tx}
        out_total = sum(t["amount"] for t in out_tx)
        in_total = sum(t["amount"] for t in in_tx)
        print(f"{label}: epoch-229 window, >=2M QU: {len(in_tx)} in ({in_total:,}), {len(out_tx)} out ({out_total:,})")

    OUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
