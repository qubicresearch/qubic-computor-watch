#!/usr/bin/env python3
"""
Cross-reference QuorumWatch's independent entity clustering (liveness/clock/
revenue/treasury signals, github.com/J0ET0M/qubic-quorumwatch) against our own
funding-trace family classification.

Kept STRICTLY SEPARATE from docs/investigation-report.html's KNOWN dict and
docs/computor_classification_cache.json - this is a secondary, third-party-
derived layer, not primary evidence. Output:

  - backfill_candidates: an unclassified/unresolved computor sitting inside an
    otherwise-pure QuorumWatch entity (all other known members agree on one
    family) - a real proposed classification, NOT auto-applied anywhere else.
  - disagreements: a QuorumWatch entity whose already-classified members do
    NOT agree with each other (mixed mj/qli/exch) - worth investigating, not
    resolving automatically.

Usage: python3 tools/quorumwatch_crossref.py --epoch 228 --epoch 229
"""
import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "docs" / "investigation-report.html"
CACHE_PATH = REPO / "docs" / "computor_classification_cache.json"
OUT_PATH = REPO / "docs" / "quorumwatch_crossref.json"


def load_known():
    html = REPORT.read_text()
    pairs = re.findall(r"'([A-Z0-9]{60})':\s*\['(\w+)',\s*'([^']*)'", html)
    return {a: fam for a, fam, _ in pairs}


def load_cache():
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def family_of(addr, known, cache):
    if addr in known:
        return known[addr]
    return cache.get(addr, {}).get("family")


def fetch_ordered_computors(epoch):
    r = subprocess.run(["curl", "-s", f"https://rpc.qubic.org/v1/epochs/{epoch}/computors"],
                        capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)["computors"]["identities"]


def fetch_qw_entities(epoch):
    r = subprocess.run(["curl", "-s", "-4", f"https://quorumwatch.qubic.tools/api/entities/{epoch}"],
                        capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)


def process_epoch(epoch, known, cache):
    ordered = fetch_ordered_computors(epoch)
    entities = fetch_qw_entities(epoch)

    backfill_candidates = []
    disagreements = []

    for e in entities:
        addrs = [ordered[i] for i in e["computor_indices"]]
        fams = {a: family_of(a, known, cache) for a in addrs}
        known_fams = {a: f for a, f in fams.items() if f and f not in ("unclassified", "unresolved")}
        fam_tally = Counter(known_fams.values())

        if len(fam_tally) > 1:
            disagreements.append({
                "epoch": epoch, "entity_id": e["entity_id"], "size": len(addrs),
                "family_breakdown": dict(fam_tally),
                "members_by_family": {a: f for a, f in known_fams.items()},
            })
            continue  # never backfill from a mixed entity

        if len(fam_tally) == 1:
            majority_family = next(iter(fam_tally))
            for a, f in fams.items():
                if f is None or f in ("unclassified", "unresolved"):
                    backfill_candidates.append({
                        "address": a, "epoch": epoch,
                        "proposed_family": majority_family,
                        "evidence": f"QuorumWatch entity {e['entity_id']} ({len(known_fams)}/{len(addrs)} known members, all {majority_family})",
                    })

    return {"backfill_candidates": backfill_candidates, "disagreements": disagreements,
            "n_entities": len(entities)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoch", action="append", type=int, required=True)
    args = ap.parse_args()

    known = load_known()
    cache = load_cache()

    out = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    for epoch in args.epoch:
        print(f"=== epoch {epoch} ===")
        result = process_epoch(str(epoch), known, cache)
        out[str(epoch)] = result
        print(f"  {result['n_entities']} entities, "
              f"{len(result['backfill_candidates'])} backfill candidates, "
              f"{len(result['disagreements'])} mixed-entity disagreements")

    OUT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"\nwritten to {OUT_PATH}")


if __name__ == "__main__":
    main()
