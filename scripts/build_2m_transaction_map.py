#!/usr/bin/env python3
"""
Builds a full transaction-level map of every real outgoing transfer >=2,000,000 QU
from every computor seat active across a given range of epochs.

IMPORTANT epoch-labeling nuance: a transaction's TICK falls inside epoch N's tick range,
but if it's a real epoch-revenue-payout forward, the revenue it represents was actually
EARNED in epoch N-1 (the protocol pays out ~2 days into the epoch AFTER the one it was
earned in). This script records both `tx_epoch` (the tick's real containing epoch, a
mechanical fact) and `likely_earned_epoch` (tx_epoch - 1, the best-guess epoch the
underlying revenue was earned in, IF this looks like a payout-forward transaction) so a
reader never conflates "when this transaction happened" with "which epoch's revenue this
is." This is NOT a certainty for every transaction (a seat could send a large transfer for
other reasons) - treat likely_earned_epoch as a labeled hypothesis, not settled fact.

Usage:
    python3 build_2m_transaction_map.py --epochs 225,226,227,228,229 --out tracking/2m_map.csv

Re-runnable on demand as new epochs close - this is meant to be a living tool, not a
one-off script. Requires: KNOWN dict extraction from docs/investigation-report.html
(run from the repo root) to label destinations against already-confirmed hubs.
"""
import argparse, json, sys, time, urllib.request, urllib.error, subprocess, csv
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
NULL_ADDR = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB'
QUTIL = 'EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVWRF'


def get_json(url, body=None, max_retries=8):
    if body is not None:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                      headers={**HEADERS, 'Content-Type': 'application/json'}, method='POST')
    else:
        req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise


def load_known_dict():
    """Extract the report's KNOWN dict (full addresses -> [family, desc]) via node."""
    out = subprocess.run(
        ["node", "-e", """
const fs = require('fs');
const html = fs.readFileSync('docs/investigation-report.html','utf8');
const m = html.match(/<script>([\\s\\S]*)<\\/script>/);
const knownMatch = m[1].match(/const KNOWN = \\{[\\s\\S]*?\\n\\};/);
const KNOWN = new Function(knownMatch[0]+'; return KNOWN;')();
console.log(JSON.stringify(KNOWN));
"""], capture_output=True, text=True, cwd=None)
    if out.returncode != 0:
        print("WARNING: could not load KNOWN dict:", out.stderr, file=sys.stderr)
        return {}
    return json.loads(out.stdout)


def epoch_of_tick(tick, boundaries):
    """boundaries: dict of {epoch_str: last_tick_of_that_epoch}. Smallest epoch whose
    boundary >= tick is the tick's real epoch."""
    candidates = sorted(((int(e), b) for e, b in boundaries.items()), key=lambda x: x[1])
    for e, b in candidates:
        if tick <= b:
            return e
    return None


def outgoing_transfers(ident, min_amount=2000000):
    try:
        d = get_json('https://rpc.qubic.org/query/v1/getEventLogs', {
            'filters': {'source': ident},
            'ranges': {'amount': {'gte': str(min_amount)}},
            'pagination': {'offset': 0, 'size': 30}
        }, max_retries=10)
        logs = d.get('eventLogs') or []
        return [e for e in logs if e.get('quTransfer')
                and e['quTransfer']['destination'] != NULL_ADDR
                and e['quTransfer']['destination'] != ident]
    except Exception as e:
        print(f"  GAVE UP on {ident}: {e}", file=sys.stderr)
        return None  # distinct from [] - marks a real failure, not "no transfers"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', required=True, help='comma-separated epoch numbers, e.g. 225,226,227,228,229')
    ap.add_argument('--out', default='tracking/2m_transaction_map.csv')
    ap.add_argument('--min-amount', type=int, default=2000000)
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()

    epochs = [int(e) for e in args.epochs.split(',')]
    print(f"Building 2M+ QU transaction map for epochs: {epochs}", file=sys.stderr)

    # Pull computor lists for each requested epoch, build unique identity set
    unique_ids = set()
    id_epochs = {}
    for e in epochs:
        d = get_json(f'https://rpc.qubic.org/v1/epochs/{e}/computors')
        ids = d['computors']['identities']
        unique_ids.update(ids)
        for i in ids:
            id_epochs.setdefault(i, []).append(e)
    print(f"Unique computor identities across these epochs: {len(unique_ids)}", file=sys.stderr)

    # Real epoch tick boundaries (for tagging tx tick -> real epoch)
    status = get_json('https://rpc.qubic.org/v1/status')
    boundaries = status['lastProcessedTicksPerEpoch']

    # Known hub dict, for labeling destinations
    known = load_known_dict()
    print(f"Loaded {len(known)} KNOWN dict entries for destination labeling", file=sys.stderr)

    def scan(id_list, workers):
        rows_local = []
        failed_local = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(outgoing_transfers, i, args.min_amount): i for i in id_list}
            done = 0
            for fut in as_completed(futs):
                ident = futs[fut]
                logs = fut.result()
                if logs is None:
                    failed_local.append(ident)
                else:
                    for e in logs:
                        tick = e.get('tickNumber')
                        tx_epoch = epoch_of_tick(tick, boundaries) if tick else None
                        dest = e['quTransfer']['destination']
                        dest_known = known.get(dest)
                        rows_local.append({
                            'source_identity': ident,
                            'source_served_epochs': ';'.join(str(x) for x in id_epochs.get(ident, [])),
                            'tick': tick,
                            'tx_epoch': tx_epoch,
                            'likely_earned_epoch': (tx_epoch - 1) if tx_epoch is not None else None,
                            'destination': dest,
                            'destination_family': dest_known[0] if dest_known else '',
                            'destination_desc': dest_known[1] if dest_known else '',
                            'amount_qu': e['quTransfer']['amount'],
                            'is_qutil': dest == QUTIL,
                        })
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(id_list)} scanned this pass, {len(rows_local)} tx found, {len(failed_local)} failed so far", file=sys.stderr)
        return rows_local, failed_local

    rows, failed = scan(unique_ids, args.workers)
    retry_round = 1
    while failed and retry_round <= 4:
        print(f"\nRETRY ROUND {retry_round}: re-scanning {len(failed)} identities that failed, at lower concurrency", file=sys.stderr)
        time.sleep(5)
        more_rows, still_failed = scan(failed, max(1, args.workers // 2))
        rows.extend(more_rows)
        failed = still_failed
        retry_round += 1

    if failed:
        print(f"\nWARNING: {len(failed)} identities STILL failed after all retries - results are INCOMPLETE for these:", file=sys.stderr)
        for f in failed:
            print(f"  UNRESOLVED: {f}", file=sys.stderr)

    rows.sort(key=lambda r: (r['tx_epoch'] or 0, r['amount_qu'] and int(r['amount_qu']) or 0), reverse=False)

    import os
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDONE: {len(rows)} total transactions >= {args.min_amount:,} QU written to {args.out}", file=sys.stderr)
    print(f"Covering {len(unique_ids)} unique computor identities across epochs {epochs}", file=sys.stderr)


if __name__ == '__main__':
    main()
