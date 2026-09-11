#!/usr/bin/env python3
"""
Hub-migration detector: given a transaction map built by build_2m_transaction_map.py,
finds unknown high-traffic destinations, classifies them by their feeder computors'
OTHER (already-known) transaction history, and tests whether a genuine coordinated
infrastructure migration happened - i.e. many computors switching from an old known
hub to a new unknown one at the same real epoch boundary, not just gradual drift.

This codifies the real methodology from the 2026-09-10 session that found 5 new qli
hubs (YFOOWIQXTUFZ.../KMDQMMIPCSAN.../TFYYQUSPXQUD.../PZWVEIWCSLOP.../OVHDHTTKLONP...):
  1. Find unknown destinations with many distinct feeder computors (candidate new hubs).
  2. Classify each candidate by looking at ITS FEEDERS' own prior (non-candidate)
     transactions against the KNOWN dict - not the candidate's own outgoing activity,
     since pure-accumulation hubs never forward and can't be classified that way.
  3. For feeders with BOTH an old-known-hub payment and a new-candidate payment, check
     the tick gap between them - a tight, consistent gap (~1 epoch) across many
     different feeders is the signature of one coordinated switch, not organic drift.
  4. Cross-check timing clusters ACROSS candidate hubs against a random-placement null
     model (same window, same cluster counts) before treating alignment as meaningful -
     don't skip this, a shared payout-timing window alone proves nothing (Kevin's
     "mortgage on Wednesday" objection, 2026-09-10 - the null model is what answers it).

Usage:
    python3 detect_hub_migration.py --map tracking/2m_transaction_map_225_229.csv \
        --min-feeders 20 --out tracking/hub_migration_report.json

Run from the repo root (needs docs/investigation-report.html for the KNOWN dict).
"""
import argparse, csv, json, random, subprocess, sys
from collections import Counter, defaultdict


def load_known_dict():
    out = subprocess.run(
        ["node", "-e", """
const fs = require('fs');
const html = fs.readFileSync('docs/investigation-report.html','utf8');
const m = html.match(/<script>([\\s\\S]*)<\\/script>/);
const knownMatch = m[1].match(/const KNOWN = \\{[\\s\\S]*?\\n\\};/);
const KNOWN = new Function(knownMatch[0]+'; return KNOWN;')();
console.log(JSON.stringify(KNOWN));
"""], capture_output=True, text=True)
    if out.returncode != 0:
        print("WARNING: could not load KNOWN dict:", out.stderr, file=sys.stderr)
        return {}
    return json.loads(out.stdout)


def clusters(ticks, gap=1000):
    ticks = sorted(ticks)
    cl = [[ticks[0]]]
    for tk in ticks[1:]:
        if tk - cl[-1][-1] > gap:
            cl.append([tk])
        else:
            cl[-1].append(tk)
    return cl


def null_model_alignment_pvalue(count_a, count_b, real_aligned, lo, hi, tol=500, trials=500, seed=7):
    rng = random.Random(seed)
    null_results = []
    for _ in range(trials):
        a_rand = sorted(rng.randint(lo, hi) for _ in range(count_a))
        b_rand = sorted(rng.randint(lo, hi) for _ in range(count_b))
        aligned = sum(1 for sa in a_rand if any(abs(sa - sb) < tol for sb in b_rand))
        null_results.append(aligned)
    null_results.sort()
    mean_null = sum(null_results) / len(null_results)
    p_val = sum(1 for x in null_results if x >= real_aligned) / len(null_results)
    return mean_null, p_val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', required=True, help='CSV from build_2m_transaction_map.py')
    ap.add_argument('--min-feeders', type=int, default=20, help='minimum distinct source computors for a destination to be a migration candidate')
    ap.add_argument('--out', default='tracking/hub_migration_report.json')
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.map)))
    known = load_known_dict()
    print(f"Loaded {len(rows)} transactions, {len(known)} KNOWN dict entries", file=sys.stderr)

    # Step 1: unknown destinations by distinct-feeder count
    unknown_feeders = defaultdict(set)
    for r in rows:
        if not r['destination_family'] and r['destination']:
            unknown_feeders[r['destination']].add(r['source_identity'])

    candidates = [d for d, feeders in unknown_feeders.items() if len(feeders) >= args.min_feeders]
    candidates.sort(key=lambda d: -len(unknown_feeders[d]))
    print(f"\n{len(candidates)} candidate hubs with >= {args.min_feeders} distinct feeders:", file=sys.stderr)
    for c in candidates:
        print(f"  {c}: {len(unknown_feeders[c])} feeders", file=sys.stderr)

    if not candidates:
        print("No candidates found - nothing to report.", file=sys.stderr)
        return

    by_source = defaultdict(list)
    for r in rows:
        by_source[r['source_identity']].append(r)

    report = {'candidates': {}}

    for cand in candidates:
        feeders = unknown_feeders[cand]
        # Step 2: classify by feeders' OTHER transaction history
        fam_votes = Counter()
        for src in feeders:
            other = [t for t in by_source[src] if t['destination'] != cand]
            fams = [known.get(t['destination'], (None,))[0] for t in other]
            fams = [f for f in fams if f in ('mj', 'qli')]
            if fams:
                fam_votes[Counter(fams).most_common(1)[0][0]] += 1
        total_signal = sum(fam_votes.values())
        top_fam = fam_votes.most_common(1)[0][0] if fam_votes else None
        purity = fam_votes.most_common(1)[0][1] / total_signal if total_signal else 0

        # Step 3: migration gap check (old known-family hub -> this candidate)
        gaps = []
        for src in feeders:
            txs = by_source[src]
            old_fam_tx = [t for t in txs if known.get(t['destination'], (None,))[0] == top_fam and t['destination'] != cand]
            new_tx = [t for t in txs if t['destination'] == cand]
            if old_fam_tx and new_tx:
                last_old = max(int(t['tick']) for t in old_fam_tx)
                first_new = min(int(t['tick']) for t in new_tx)
                if first_new > last_old:
                    gaps.append(first_new - last_old)

        report['candidates'][cand] = {
            'num_feeders': len(feeders),
            'family_votes': dict(fam_votes),
            'family_signal_coverage': f"{total_signal}/{len(feeders)}",
            'inferred_family': top_fam,
            'purity': round(purity, 3),
            'migration_transitions_found': len(gaps),
            'gap_ticks_min': min(gaps) if gaps else None,
            'gap_ticks_max': max(gaps) if gaps else None,
            'gap_ticks_median': sorted(gaps)[len(gaps) // 2] if gaps else None,
        }
        print(f"\n{cand}: family={top_fam} (purity {purity:.1%}, {total_signal}/{len(feeders)} had signal), "
              f"{len(gaps)} clean transitions found, gap range {min(gaps) if gaps else '-'}-{max(gaps) if gaps else '-'}",
              file=sys.stderr)

    # Step 4: cross-candidate timing alignment with a real null model (only if >=2 candidates)
    if len(candidates) >= 2:
        print("\n=== Cross-candidate timing alignment (null-model tested, PER-PAIR window) ===", file=sys.stderr)
        cand_ticks = {c: sorted(int(r['tick']) for r in rows if r['destination'] == c) for c in candidates}
        report['timing_alignment'] = {'pairs': []}
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                a_ticks, b_ticks = cand_ticks[candidates[i]], cand_ticks[candidates[j]]
                if not a_ticks or not b_ticks:
                    continue
                # IMPORTANT: the null model's random-placement window must be THIS PAIR's own
                # combined tick range, not the range across all candidates - a wider global
                # window (some candidates may be from an unrelated, much older/different burst)
                # dilutes the null model and silently understates real significance.
                lo = min(a_ticks[0], b_ticks[0])
                hi = max(a_ticks[-1], b_ticks[-1])
                a_cl = [c[0] for c in clusters(a_ticks)]
                b_cl = [c[0] for c in clusters(b_ticks)]
                aligned = sum(1 for sa in a_cl if any(abs(sa - sb) < 500 for sb in b_cl))
                mean_null, p_val = null_model_alignment_pvalue(len(a_cl), len(b_cl), aligned, lo, hi)
                print(f"  {candidates[i]} vs {candidates[j]}: real={aligned}/{len(a_cl)}, null_mean={mean_null:.1f}, p={p_val:.3f} (window {lo}-{hi})", file=sys.stderr)
                report['timing_alignment']['pairs'].append({
                    'a': candidates[i], 'b': candidates[j],
                    'real_aligned': aligned, 'a_clusters': len(a_cl), 'b_clusters': len(b_cl),
                    'window': [lo, hi],
                    'null_mean': round(mean_null, 1), 'p_value': p_val,
                })

    import os
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    json.dump(report, open(args.out, 'w'), indent=2)
    print(f"\nFull report written to {args.out}", file=sys.stderr)


if __name__ == '__main__':
    main()
