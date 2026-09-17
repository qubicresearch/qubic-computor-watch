#!/usr/bin/env python3
"""
Export qubic-pulse's local SQLite metrics (epoch, tick quality, active
addresses, burned QUs, price/marketcap, ...) as an hourly-rollup JSON small
enough to ship in the static site. Raw table is 60s-resolution (~900K rows
over ~2 months as of 2026-09) -- too dense for the browser, so this
averages each metric into 1-hour buckets.

Must run on a box with direct access to the qubic-pulse DB (currently the
9950X, ~/Downloads/qubic-pulse/qubic-pulse.db, fed by the qubic-pulse.service
systemd user unit). Not runnable from GitHub Actions.

Usage: python3 tools/export_pulse_timeseries.py
"""
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = Path.home() / "Downloads" / "qubic-pulse" / "qubic-pulse.db"
OUT = REPO / "docs" / "pulse_timeseries.json"
BUCKET = 3600  # 1 hour


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    cur = con.cursor()
    cur.execute("SELECT ts, name, value FROM metrics ORDER BY ts")

    buckets = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))  # name -> bucket_ts -> [sum, count]
    row_count = 0
    for ts, name, value in cur:
        b = (ts // BUCKET) * BUCKET
        s = buckets[name][b]
        s[0] += value
        s[1] += 1
        row_count += 1
    con.close()

    metrics = {}
    for name, series in buckets.items():
        points = sorted((b, round(s / n, 4)) for b, (s, n) in series.items())
        metrics[name] = points

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "bucketSeconds": BUCKET,
        "rowsProcessed": row_count,
        "metrics": metrics,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{row_count} rows -> {sum(len(v) for v in metrics.values())} hourly points across {len(metrics)} metrics")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
