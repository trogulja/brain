#!/usr/bin/env python3
"""
analyze - aggregate stats over recall_log + read_log.

Two append-only logs, analyzed independently:
- recall_log: what's been searched, what was surfaced
- read_log: what's been opened

The interesting cross-table signal is **surface-count vs read-count per
article**: an entry retrieved often but never opened is a quality
signal - content stale, name misleading, or BM25 over-ranking it. No
per-event correlation, no session/time matching: aggregate is what's
actionable.

Usage:
  analyze.py                # default report (last 30 days)
  analyze.py --days 7       # narrower window
  analyze.py --json         # machine-readable
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
DB_PATH = BRAIN / "search.db"


def load(db, since_iso):
    recalls = list(db.execute(
        "SELECT id, ts, query, type_filter, results_json FROM recall_log WHERE ts >= ?",
        (since_iso,),
    ))
    reads = list(db.execute(
        "SELECT id, ts, path FROM read_log WHERE ts >= ?",
        (since_iso,),
    ))
    return recalls, reads


def analyse(recalls, reads):
    query_counter = Counter()
    dead_queries = []
    surfaced = Counter()       # path -> times appeared in any recall.results_json
    type_filters = Counter()

    for rcl in recalls:
        _id, _ts, query, type_filter, results_json = rcl
        query_counter[query] += 1
        if type_filter:
            type_filters[type_filter] += 1
        try:
            parsed = json.loads(results_json) if results_json else []
        except json.JSONDecodeError:
            parsed = []
        # recall_log has two historical shapes:
        #   1) bare list of result dicts (old): [{path, ...}, ...]
        #   2) wrapper dict (current):          {"mode": "...", "results": [{abs_path, path, ...}, ...]}
        if isinstance(parsed, dict):
            results = parsed.get("results", [])
        else:
            results = parsed
        if not results:
            dead_queries.append(query)
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            path = r.get("abs_path") or r.get("path")
            if path:
                surfaced[path] += 1

    read_counts = Counter(read[2] for read in reads)

    # Quality signal: surfaced often, read rarely
    surface_vs_read = []
    for path, n_surf in surfaced.items():
        n_read = read_counts.get(path, 0)
        surface_vs_read.append((path, n_surf, n_read))
    # Flag when surfaced ≥3 and read ratio <30%
    retrieve_no_read = [
        row for row in surface_vs_read
        if row[1] >= 3 and (row[2] / row[1] if row[1] else 0) < 0.3
    ]
    retrieve_no_read.sort(key=lambda r: (r[1] - r[2], -r[1]), reverse=True)

    # Articles read but never surfaced - these reach Claude via wikilinks /
    # CLAUDE.md / direct paths. If frequent, BM25 may not be ranking them well.
    read_but_unsurfaced = [
        (path, n) for path, n in read_counts.items()
        if surfaced.get(path, 0) == 0
    ]
    read_but_unsurfaced.sort(key=lambda r: r[1], reverse=True)

    return {
        "totals": {
            "recalls": len(recalls),
            "reads": len(reads),
            "unique_paths_surfaced": len(surfaced),
            "unique_paths_read": len(read_counts),
            "dead_queries": len(dead_queries),
        },
        "top_queries": query_counter.most_common(10),
        "dead_queries_sample": Counter(dead_queries).most_common(10),
        "type_filters": dict(type_filters),
        "top_read_paths": read_counts.most_common(10),
        "top_surfaced_paths": surfaced.most_common(10),
        "retrieve_no_read": retrieve_no_read[:10],
        "read_but_unsurfaced": read_but_unsurfaced[:10],
    }


def relpath(p):
    try:
        return str(Path(p).relative_to(BRAIN))
    except ValueError:
        return p


def format_report(report, since_iso):
    t = report["totals"]
    out = [
        f"# Brain recall analytics - since {since_iso[:10]}",
        "",
        f"- Recalls: {t['recalls']}  (dead: {t['dead_queries']})",
        f"- Reads: {t['reads']}",
        f"- Unique paths: {t['unique_paths_surfaced']} surfaced, {t['unique_paths_read']} read",
    ]
    if report["type_filters"]:
        out.append(f"- Type filters used: {report['type_filters']}")

    if report["top_queries"]:
        out += ["", "## Most searched", ""]
        for q, n in report["top_queries"]:
            out.append(f"- `{q}` ({n}×)")

    if report["dead_queries_sample"]:
        out += [
            "",
            "## Dead queries (zero results - knowledge gaps?)",
            "",
        ]
        for q, n in report["dead_queries_sample"]:
            out.append(f"- `{q}` ({n}×)")

    if report["top_read_paths"]:
        out += ["", "## Most read", ""]
        for p, n in report["top_read_paths"]:
            out.append(f"- {relpath(p)} ({n}×)")

    if report["top_surfaced_paths"]:
        read_lookup = dict(report["top_read_paths"])
        out += ["", "## Most surfaced (in recall results)", ""]
        for p, n in report["top_surfaced_paths"]:
            read_n = read_lookup.get(p, 0)
            out.append(f"- {relpath(p)} ({n}× surfaced, {read_n}× read)")

    if report["retrieve_no_read"]:
        out += [
            "",
            "## Retrieve-no-read (surfaced ≥3×, read <30%)",
            "",
            "_Articles consistently surfaced but rarely opened. Content stale, name misleading, or BM25 over-ranking._",
            "",
        ]
        for path, n_surf, n_read in report["retrieve_no_read"]:
            out.append(f"- {relpath(path)} ({n_surf}× surfaced, {n_read}× read)")

    if report["read_but_unsurfaced"]:
        out += [
            "",
            "## Read but never surfaced",
            "",
            "_Reached via wikilink / CLAUDE.md / direct path, not via recall. If frequent, BM25 may be missing them._",
            "",
        ]
        for path, n in report["read_but_unsurfaced"]:
            out.append(f"- {relpath(path)} ({n}× read)")

    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(prog="analyze", description="recall + read aggregate analytics")
    p.add_argument("--days", type=int, default=30, help="window in days (default 30)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

    if not DB_PATH.exists():
        print("no search.db yet - run recall.py first", file=sys.stderr)
        sys.exit(1)

    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%S")
    db = sqlite3.connect(str(DB_PATH))
    recalls, reads = load(db, since)
    report = analyse(recalls, reads)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report, since))


if __name__ == "__main__":
    main()
