#!/usr/bin/env python3
"""
Classify every current computor into a family (mj/qli/exch/role) using the
methodology verified across this investigation:

  1. Already in the report's KNOWN dict -> use it directly.
  2. Otherwise, find the address's real epoch payout (largest outgoing
     transfer >= REAL_PAYOUT_FLOOR QU) and classify by whatever family its
     destination hub already has.
  3. If no real payout is on record yet, check for the two known secondary
     reveals: a real 10,000,000 QU side-payment to a known side hub, or being
     one of the "9,000,000 QU" funder wallets' onboarding recipients.
  4. Anything still unresolved is left unclassified, with its largest real
     transfer (if any) recorded so a human can follow up.

Results are cached incrementally to CACHE_PATH so the script is safe to
interrupt and re-run - already-classified addresses are never re-queried.

Usage:
    python3 tools/classify_computors.py [--epoch 229] [--limit N]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "docs" / "investigation-report.html"
CACHE_PATH = REPO / "docs" / "computor_classification_cache.json"

REAL_PAYOUT_FLOOR = 100_000_000  # QU - established floor for "this is a real epoch payout"
SIDE_PAYMENT_AMOUNT = 10_000_000
FUNDER_AMOUNT = 9_000_000

# The 25 official Qubic smart contracts + the null/protocol (ANN) address.
# Never hub candidates, never real computors - see qubic-known-contract-addresses.md.
PROTOCOL_ADDRESSES = {
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB",  # null/ANN
    "BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAARMID",  # QX
    "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACNKL",  # QUOTTERY
    "DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANMIG",  # RANDOM
    "EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVWRF",  # QUTIL
    "FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYWJB",  # MLM
    "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQGNM",  # GQMPROP
    "HAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHYCM",  # SWATCH
    "IAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABXSH",  # CCF
    "JAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVKHO",  # QEARN
    "KAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXIUO",  # QVAULT
    "LAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKPTJ",  # MSVAULT
    "MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWLWD",  # QBAY
    "NAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAML",  # QSWAP
    "OAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZTPD",  # NOST
    "PAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYVRC",  # QDRAW
    "QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPIYE",  # RL
    "RAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADKAH",  # QBOND
    "SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABNI",  # QIP
    "TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXRFC",  # QRAFFLE
    "UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHQEE",  # QRWA
    "VAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAILLJ",  # QRP
    "WAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVDQA",  # QTF
    "XAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXNMD",  # QDUEL
    "YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMSME",  # PULSE
    "ZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZUQI",  # VOTTUN
}

# The 11 confirmed "9,000,000 QU onboarding funder" wallets (2026-09-09 verification -
# all 11 traced to qli, see the CORRECTION note in the master memory file).
NINE_M_FUNDERS = {
    "VUKEQPVNKWVEKBHXZHNASJPJHUACYMQHCLBOAUTRLBBFQEEZEIQSCCYDTJYJ",
    "OSFBXSGRBQRJHEWPKIVVWPTTKTSBCWMYXQUCFIUBQFZWSMZMOTPIWQHAQPTI",
    "VUYDQJWYQMRZJHKNEUXOVCDGTAOBARGEMYLEIQNZZFHDHJBTNVULLXTBAHQL",
    "WPEDKQYFHDCBADJBHKQBGRPOWXKCUSUFENENEGEMDCTAIQPFBYZPUUEEMFMO",
    "EAFWYRBBVOADXGTBNNZNJMMBPNJCXPZCPDZZZCAGXGYNGVLEJBCAEUQAUUME",
    "ZOUODTJNQSVYBFVRYKLTYUANVXHBTDGCLVEMXDXYLBQKCKZWRNJIYONGEVKB",
    "TDHVJGVERJRKHDICPHEZPCSOHSFDTWTZGVBBPYAONELTZDSNXHSHHBCHQNZF",
    "JZAZNLEGBXOMPEDQYIVNVGDCVRBBFEZPFEQEIUOVYBAACOJBAMQENEYBGSVC",
    "SMCITEHEYIRTLBKQDUBCKFTBDZQDFJJFMGQPSNHSVAVFZFIJMIZUXVDFCCMJ",
    "VTIIKNEHCGCKEBKTAHFXXQYUEKQBTOYFUDRBAGWLRCBOMCFJNSGNXBPCXGSO",
    "JAOSHTYLMKVLPEYWJZNINEVHMLBBWYQZCVSUBZZUAEWIYPFPFHRRIMBAKCKI",
}


def load_known_dict():
    html = REPORT.read_text()
    pairs = re.findall(r"'([A-Z0-9]{60})':\s*\['(\w+)',\s*'([^']*)'", html)
    return {addr: fam for addr, fam, _desc in pairs}


def load_epoch_computors(epoch=None):
    html = REPORT.read_text()
    m = re.search(r"const EPOCH_COMPUTORS = (\{.*?\});", html, re.S)
    blob = m.group(1)
    epochs = re.findall(r'"(\d+)"\s*:\s*\[(.*?)\]', blob, re.S)
    epochs = {ep: re.findall(r'[A-Z]{60}', addrs) for ep, addrs in epochs}
    if epoch is None:
        epoch = max(epochs, key=int)
    return str(epoch), epochs[str(epoch)]


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


def largest_transfer(addr, key, floor, size=10):
    """key: 'source' for outgoing, 'destination' for incoming."""
    d = curl_json({"filters": {key: addr}, "ranges": {"amount": {"gte": str(floor)}},
                   "pagination": {"offset": 0, "size": size}})
    hits = d.get("eventLogs", [])
    if not hits:
        return None
    best = max(hits, key=lambda e: int(e["quTransfer"]["amount"]))
    return best["quTransfer"]


def classify_one(addr, known):
    if addr in known:
        return {"family": known[addr], "evidence": "known-dict"}

    # 1. real epoch payout -> known hub
    t = largest_transfer(addr, "source", REAL_PAYOUT_FLOOR)
    if t:
        dest = t["destination"]
        amt = int(t["amount"])
        if dest in known:
            return {"family": known[dest], "evidence": f"real payout {amt:,} QU -> {dest} ({known[dest]})"}
        return {"family": "unresolved", "evidence": f"real payout {amt:,} QU -> {dest} (destination not yet classified)"}

    # 2. 10,000,000 QU side-payment reveal (outgoing to a known side hub)
    d = curl_json({"filters": {"source": addr}, "ranges": {"amount": {"gte": "9000000"}},
                   "pagination": {"offset": 0, "size": 10}})
    for e in d.get("eventLogs", []):
        qt = e["quTransfer"]
        amt = int(qt["amount"])
        dest = qt["destination"]
        if amt == SIDE_PAYMENT_AMOUNT and dest in known:
            return {"family": known[dest], "evidence": f"10M side-payment -> {dest} ({known[dest]})"}

    # 3. 9,000,000 QU onboarding-funder reveal (incoming from a known funder)
    d = curl_json({"filters": {"destination": addr}, "ranges": {"amount": {"gte": "1000000"}},
                   "pagination": {"offset": 0, "size": 10}})
    for e in d.get("eventLogs", []):
        qt = e["quTransfer"]
        if int(qt["amount"]) == FUNDER_AMOUNT and qt["source"] in NINE_M_FUNDERS:
            return {"family": "qli", "evidence": f"9M onboarding funding from {qt['source']} (confirmed qli funder)"}

    return {"family": "unclassified", "evidence": "no real payout, side-payment, or funder reveal found"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoch", default=None, help="epoch key to classify (default: latest in EPOCH_COMPUTORS)")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N addresses (testing)")
    args = ap.parse_args()

    known = load_known_dict()
    epoch, computors = load_epoch_computors(args.epoch)
    print(f"epoch {epoch}: {len(computors)} computors, {len(known)} known-dict entries loaded", file=sys.stderr)

    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())

    targets = computors[: args.limit] if args.limit else computors
    for i, addr in enumerate(targets):
        if addr in PROTOCOL_ADDRESSES:
            continue
        if addr in cache:
            continue
        result = classify_one(addr, known)
        cache[addr] = result
        if (i + 1) % 20 == 0 or (i + 1) == len(targets):
            CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))
            print(f"  {i+1}/{len(targets)} processed", file=sys.stderr)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))

    tally = {}
    for addr in computors:
        fam = known.get(addr) or cache.get(addr, {}).get("family", "?")
        tally[fam] = tally.get(fam, 0) + 1
    print(f"\n=== epoch {epoch} family breakdown ({len(computors)} computors) ===")
    for fam, n in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {fam:15s} {n:4d}  ({100*n/len(computors):.1f}%)")


if __name__ == "__main__":
    main()
