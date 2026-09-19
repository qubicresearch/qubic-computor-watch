#!/usr/bin/env python3
"""
Pull the CCF contract's full transfer history and decode every real vote-cast
transaction (inputType=2, inputSize=16) into (txTick, voter, proposalIndex,
proposalTick, voteValue). This is how individual computor votes actually show
up on-chain -- not as a per-computor "vote transaction" queryable by source,
but as transactions TO the CCF contract itself, only visible by pulling the
contract's OWN transfer history and decoding the raw input payload.

Usage: python3 tools/pull_ccf_vote_history.py [--out docs/ccf_full_vote_history_fresh.json]
"""
import argparse
import json
import struct
import time
import urllib.request

CCF_ADDR = "IAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABXSH"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/ccf_full_vote_history_fresh.json")
    ap.add_argument("--max-pages", type=int, default=45)
    args = ap.parse_args()

    all_votes = []
    seen_tx = set()
    page = 0
    size = 250
    while True:
        url = f"https://rpc.qubic.org/v2/identities/{CCF_ADDR}/transfers?desc=true&pageSize={size}&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    d = json.load(r)
                break
            except Exception as e:
                print("retry", page, e, flush=True)
                time.sleep(2)
        else:
            print("giving up at page", page)
            break
        txs = d.get("transactions", [])
        if not txs:
            break
        new = 0
        for tgroup in txs:
            tx = tgroup["transactions"][0]["transaction"]
            if tx["txId"] in seen_tx:
                continue
            seen_tx.add(tx["txId"])
            if tx["inputType"] == 2 and tx["inputSize"] == 16:
                raw = bytes.fromhex(tx["inputHex"])
                proposalIndex, proposalType, proposalTick, voteValue = struct.unpack("<HHIq", raw)
                all_votes.append({
                    "txTick": tx["tickNumber"], "src": tx["sourceId"],
                    "proposalIndex": proposalIndex, "proposalType": proposalType,
                    "proposalTick": proposalTick, "voteValue": voteValue,
                })
                new += 1
        print(f"page {page}: got {len(txs)}, new votes {new}, total {len(all_votes)}", flush=True)
        page += 1
        time.sleep(0.3)
        if new == 0 and len(txs) < size:
            break
        if page > args.max_pages:
            print("safety cap reached (near 10k record API limit)")
            break

    json.dump(all_votes, open(args.out, "w"))
    print("DONE, total vote transactions:", len(all_votes))
    from collections import Counter
    props = Counter((v["proposalIndex"], v["proposalTick"]) for v in all_votes)
    print("distinct proposal instances found:", len(props))
    for k, n in sorted(props.items(), key=lambda x: -x[1])[:20]:
        print(k, n)


if __name__ == "__main__":
    main()
