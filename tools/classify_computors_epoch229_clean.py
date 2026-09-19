#!/usr/bin/env python3
"""
Clean, epoch-229-scoped re-classification. The shared cache (computor_classification_cache.json)
is keyed by address only, not by epoch -- so an address that was a computor in both epoch 229
and epoch 230 got its epoch-229 evidence silently overwritten by this session's epoch-230 pass.
This redoes epoch 229 from scratch into its OWN cache file, explicitly excluding any transfer
at tick >= EPOCH230_PAYOUT_TICK (the confirmed real epoch-230 payout window, tick 80,371,514+)
so it can't pick up the wrong epoch's payout the way a plain "largest transfer ever" search would.

Usage: python3 tools/classify_computors_epoch229_clean.py
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "docs" / "investigation-report.html"
CACHE_PATH = REPO / "docs" / "computor_classification_cache_epoch229_clean.json"

REAL_PAYOUT_FLOOR = 100_000_000
EPOCH230_PAYOUT_TICK_FLOOR = 80_300_000  # confirmed epoch-230 payout lands at 80,371,514+; safe cutoff below it

PROTOCOL_ADDRESSES = {
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB",
    "BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARMID",
    "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACNKL",
    "DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANMIG",
    "EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVWRF",
    "FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYWJB",
    "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQGNM",
    "HAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHYCM",
    "IAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABXSH",
    "JAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVKHO",
    "KAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXIUO",
    "LAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKPTJ",
    "MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWLWD",
    "NAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAML",
    "OAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZTPD",
    "PAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYVRC",
    "QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPIYE",
    "RAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADKAH",
    "SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABNI",
    "TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXRFC",
    "UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHQEE",
    "VAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAILLJ",
    "WAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVDQA",
    "XAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXNMD",
    "YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMSME",
    "ZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZUQI",
}


def load_known_dict():
    html = REPORT.read_text()
    pairs = re.findall(r"'([A-Z0-9]{60})':\s*\['(\w+)',\s*'([^']*)'", html)
    return {addr: fam for addr, fam, _desc in pairs}


def load_epoch229_computors():
    html = REPORT.read_text()
    m = re.search(r"const EPOCH_COMPUTORS = (\{.*?\});", html, re.S)
    d = json.loads(m.group(1))
    return d["229"]


def curl_json(payload, retries=3):
    for attempt in range(retries):
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "https://rpc.qubic.org/query/v1/getEventLogs",
             "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=30,
        )
        try:
            return json.loads(r.stdout)
        except Exception:
            time.sleep(1)
    return {}


def largest_transfer_pre230(addr, key, floor, size=30):
    """Same as classify_computors.py's largest_transfer, but explicitly excludes any hit at
    tick >= EPOCH230_PAYOUT_TICK_FLOOR so an address that was ALSO a computor in epoch 230
    can't have its epoch-229 evidence contaminated by the (larger, more recent) epoch-230 payout."""
    d = curl_json({"filters": {key: addr}, "ranges": {"amount": {"gte": str(floor)}},
                   "pagination": {"offset": 0, "size": size}})
    hits = [e for e in d.get("eventLogs", []) if e["tickNumber"] < EPOCH230_PAYOUT_TICK_FLOOR]
    if not hits:
        return None, len(d.get("eventLogs", []))
    best = max(hits, key=lambda e: int(e["quTransfer"]["amount"]))
    return best["quTransfer"], len(d.get("eventLogs", []))


def classify_one(addr, known):
    if addr in known:
        return {"family": known[addr], "evidence": "known-dict"}

    t, total_seen = largest_transfer_pre230(addr, "source", REAL_PAYOUT_FLOOR)
    if t:
        dest = t["destination"]
        amt = int(t["amount"])
        if dest in known:
            return {"family": known[dest], "evidence": f"real epoch-229 payout {amt:,} QU -> {dest} ({known[dest]})"}
        return {"family": "unresolved", "evidence": f"real epoch-229 payout {amt:,} QU -> {dest} (destination not yet classified)"}
    if total_seen >= 30:
        # every one of the (up to 30) hits we pulled was >= the epoch-230 cutoff -- the real
        # epoch-229 payout may still exist further back than we paged; flag distinctly so it's
        # not confused with "genuinely never paid."
        return {"family": "unresolved", "evidence": f"all {total_seen} large transfers seen were post-epoch-230-cutoff; epoch-229 payout not found within page size"}
    return {"family": "unclassified", "evidence": "no real pre-epoch-230 payout found"}


def main():
    known = load_known_dict()
    computors = load_epoch229_computors()
    print(f"epoch 229 (clean pass): {len(computors)} computors, {len(known)} known-dict entries", file=sys.stderr)

    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())

    for i, addr in enumerate(computors):
        if addr in PROTOCOL_ADDRESSES or addr in cache:
            continue
        cache[addr] = classify_one(addr, known)
        if (i + 1) % 50 == 0 or (i + 1) == len(computors):
            print(f"  {i+1}/{len(computors)}", file=sys.stderr)
            CACHE_PATH.write_text(json.dumps(cache, indent=2))

    CACHE_PATH.write_text(json.dumps(cache, indent=2))

    from collections import Counter
    tally = Counter(cache.get(a, {}).get("family", "MISSING") for a in computors)
    print("\n=== epoch 229 clean family breakdown ===")
    for fam, n in tally.most_common():
        print(f"  {fam:15s} {n:4d}  ({100*n/len(computors):.1f}%)")


if __name__ == "__main__":
    main()
