#!/usr/bin/env python3
"""
Full forensic audit of every real vote cast in epoch 229's three governance
proposals (GQMPROP tick 77994817, CCF tick 78369421, CCF tick 78369500).
For every real vote: who cast it, when (txTick), what they voted, and which
real family/hub their epoch-229 money-flow traces to (via the already-clean,
tick-bounded epoch-229 classification). Also detects tight-timing clusters
(votes within 5 ticks of each other, >=5 members) per proposal.

Saved as a durable record so this can be cross-referenced against the
money-flow census, the exchange listing, and governance data later.

Usage: python3 tools/build_epoch229_vote_audit.py
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VOTES_PATH = "/tmp/claude-1000/-home-kevarms/fd6e6541-a96a-4bf9-b6d9-4d0e8364b844/scratchpad/all_votes_merged.json"
CACHE_PATH = REPO / "docs" / "computor_classification_cache_epoch229_clean.json"
OUT_PATH = REPO / "docs" / "epoch229_vote_audit.json"

PROPOSALS = {
    77994817: {"contract": "GQMPROP", "class": "GeneralOptions", "proposer": "AAMJNDZIAGURZEFMBDYMMAHFVFUCECRNKVSTUQIDPEWNDUBFUHDCTMZFOXZD", "proposerOwner": "qli"},
    78369421: {"contract": "CCF", "class": "Transfer", "proposer": "KGLUEQQRUOVFJCVIVNUXHPOXEOZBIWJPNHOQLCGOCANUYMXXCUBCGOUFNDXM", "proposerOwner": "jetski"},
    78369500: {"contract": "CCF", "class": "Transfer", "proposer": "PTXKGDSPQNDTBFRNLTRPKVZAEEMCWFBUBSMDYKMYSBYMYHJWLHURNIFFZSPF", "proposerOwner": "jetski"},
}


def hub_of(cache, addr):
    ev = cache.get(addr, {}).get("evidence", "")
    m = re.search(r"-> ([A-Z0-9]{60})", ev)
    if m:
        return m.group(1)
    if "known-dict" in ev:
        return "KNOWN_DICT_CARRIED_FORWARD"
    if "9M onboarding" in ev:
        return "9M_ONBOARDING_FUNDER"
    if "revenue-record" in ev.lower() or ("epoch-230 revenue" in ev):
        return "REVENUE_RECORD_NOT_SWEPT"
    return "UNRESOLVED"


def cluster(votes, gap=5, minsize=5):
    vs = sorted(votes, key=lambda v: v["txTick"])
    if not vs:
        return []
    groups, cur = [], [vs[0]]
    for v in vs[1:]:
        if v["txTick"] - cur[-1]["txTick"] <= gap:
            cur.append(v)
        else:
            groups.append(cur)
            cur = [v]
    groups.append(cur)
    return [g for g in groups if len(g) >= minsize]


def main():
    votes = json.load(open(VOTES_PATH))
    cache = json.load(open(CACHE_PATH))

    audit = {"epoch": 229, "proposals": {}}

    for tick, meta in PROPOSALS.items():
        vs = [v for v in votes if v["proposalTick"] == tick]
        # per-vote record with real family/hub attached
        records = []
        for v in vs:
            fam = cache.get(v["src"], {}).get("family", "UNKNOWN")
            hub = hub_of(cache, v["src"])
            records.append({
                "src": v["src"], "txTick": v["txTick"], "voteValue": v["voteValue"],
                "family": fam, "hub": hub,
            })

        fam_tally = Counter(r["family"] for r in records)
        vote_tally = Counter(r["voteValue"] for r in records)

        clusters = cluster(vs)
        cluster_summaries = []
        for g in clusters:
            members = [v["src"] for v in g]
            fam_c = Counter(cache.get(a, {}).get("family", "UNKNOWN") for a in members)
            hub_c = Counter(hub_of(cache, a) for a in members)
            vote_c = Counter(v["voteValue"] for v in g)
            cluster_summaries.append({
                "tickStart": g[0]["txTick"], "tickEnd": g[-1]["txTick"], "size": len(g),
                "voteValues": dict(vote_c), "family": dict(fam_c),
                "topHubs": hub_c.most_common(8), "members": sorted(members),
            })

        audit["proposals"][str(tick)] = {
            "meta": meta,
            "totalVotes": len(vs),
            "familyBreakdown": dict(fam_tally),
            "voteValueBreakdown": dict(vote_tally),
            "clusters": cluster_summaries,
            "allVotes": records,
        }

        print(f"proposal {tick} ({meta['contract']}, proposer {meta['proposerOwner']}): "
              f"{len(vs)} votes, family={dict(fam_tally)}, {len(cluster_summaries)} clusters (>=5)")

    OUT_PATH.write_text(json.dumps(audit, indent=2))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
