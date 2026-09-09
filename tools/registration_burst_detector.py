#!/usr/bin/env python3
"""
Find registration-time clusters (co-registration bursts) within a list of
addresses - the same pattern manually found for VUKEQ's 23 9M-recipients
(7-minute burst) and QuorumWatch entity E-9359's 24 backfilled members (a
51-tick / ~20-second burst plus an 8-address ~4.3-minute burst).

A tight cluster of first-ever-transaction ticks across many addresses is a
real, independently-observable fingerprint of a scripted batch-onboarding
event - no QuorumWatch/core-node access needed, just public RPC data.

Usage:
    python3 tools/registration_burst_detector.py --addresses-file addrs.txt
    python3 tools/registration_burst_detector.py --qw-entity 229:E-9359
    python3 tools/registration_burst_detector.py --gap 100 --min-cluster 3 --addresses-file addrs.txt
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO / "docs" / "registration_tick_cache.json"

DEFAULT_GAP = 100          # ticks (~40s at ~2.5 ticks/sec) - gap that starts a new cluster
DEFAULT_MIN_CLUSTER = 3    # smaller groups are noise, not a real burst


def load_cache():
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def first_tx_tick(addr, cache):
    if addr in cache:
        return cache[addr]
    r = subprocess.run(
        ["curl", "-s", f"https://rpc.qubic.org/v2/identities/{addr}/transfers?desc=false&pageSize=1&page=0"],
        capture_output=True, text=True, timeout=20,
    )
    try:
        d = json.loads(r.stdout)
        tick = d["transactions"][0]["tickNumber"]
    except Exception:
        tick = None
    cache[addr] = tick
    return tick


def load_qw_entity(spec):
    """spec like '229:E-9359' -> list of addresses in that QuorumWatch entity."""
    epoch, entity_id = spec.split(":", 1)
    r = subprocess.run(["curl", "-s", "-4", f"https://quorumwatch.qubic.tools/api/entities/{epoch}"],
                        capture_output=True, text=True, timeout=30)
    entities = json.loads(r.stdout)
    ordered = subprocess.run(["curl", "-s", f"https://rpc.qubic.org/v1/epochs/{epoch}/computors"],
                              capture_output=True, text=True, timeout=30)
    identities = json.loads(ordered.stdout)["computors"]["identities"]
    for e in entities:
        if e["entity_id"] == entity_id:
            return [identities[i] for i in e["computor_indices"]]
    raise SystemExit(f"entity {entity_id} not found in epoch {epoch}")


def find_bursts(addr_ticks, gap, min_cluster):
    """addr_ticks: list of (addr, tick), tick may be None (excluded)."""
    pairs = sorted(((a, t) for a, t in addr_ticks if t is not None), key=lambda x: x[1])
    if not pairs:
        return []
    clusters = []
    current = [pairs[0]]
    for addr, tick in pairs[1:]:
        if tick - current[-1][1] <= gap:
            current.append((addr, tick))
        else:
            if len(current) >= min_cluster:
                clusters.append(current)
            current = [(addr, tick)]
    if len(current) >= min_cluster:
        clusters.append(current)
    return clusters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addresses-file", help="text file, one address per line")
    ap.add_argument("--qw-entity", help="epoch:entity_id, e.g. 229:E-9359")
    ap.add_argument("--gap", type=int, default=DEFAULT_GAP)
    ap.add_argument("--min-cluster", type=int, default=DEFAULT_MIN_CLUSTER)
    args = ap.parse_args()

    if args.addresses_file:
        addrs = [l.strip() for l in Path(args.addresses_file).read_text().splitlines() if l.strip()]
    elif args.qw_entity:
        addrs = load_qw_entity(args.qw_entity)
    else:
        raise SystemExit("need --addresses-file or --qw-entity")

    print(f"{len(addrs)} addresses to check", flush=True)
    cache = load_cache()
    addr_ticks = []
    for i, a in enumerate(addrs):
        tick = first_tx_tick(a, cache)
        addr_ticks.append((a, tick))
        if (i + 1) % 20 == 0:
            save_cache(cache)
            print(f"  {i+1}/{len(addrs)} checked", flush=True)
    save_cache(cache)

    clusters = find_bursts(addr_ticks, args.gap, args.min_cluster)
    print(f"\n{len(clusters)} registration burst(s) found (gap<={args.gap} ticks, min size {args.min_cluster}):\n")
    for c in clusters:
        span = c[-1][1] - c[0][1]
        print(f"  {len(c)} addresses, ticks {c[0][1]}-{c[-1][1]} (span {span} ticks)")
        for addr, tick in c:
            print(f"    {tick}  {addr}")
        print()


if __name__ == "__main__":
    main()
