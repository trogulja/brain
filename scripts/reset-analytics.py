#!/usr/bin/env python3
"""
reset-analytics - wipe or prune recall_log and read_log in ~/.brain/search.db.

Touches only the analytics tables; the FTS index (docs, files) is left
intact, so no reindex needed afterwards.

Usage:
  reset-analytics.py                       # dry run - show counts, do nothing
  reset-analytics.py --force               # delete everything
  reset-analytics.py --older-than 90       # dry run: show how many >90 days old
  reset-analytics.py --older-than 90 --force   # delete rows older than 90 days
  reset-analytics.py --force --recalls-only
  reset-analytics.py --force --reads-only
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
DB = BRAIN / "search.db"


def counts(db, cutoff=None):
    if cutoff is None:
        r = db.execute("SELECT COUNT(*) FROM recall_log").fetchone()[0]
        rd = db.execute("SELECT COUNT(*) FROM read_log").fetchone()[0]
    else:
        r = db.execute("SELECT COUNT(*) FROM recall_log WHERE ts < ?", (cutoff,)).fetchone()[0]
        rd = db.execute("SELECT COUNT(*) FROM read_log WHERE ts < ?", (cutoff,)).fetchone()[0]
    return r, rd


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true", help="actually delete (default is dry run)")
    p.add_argument("--older-than", type=int, metavar="DAYS",
                   help="only delete rows older than DAYS days (default: delete all)")
    p.add_argument("--recalls-only", action="store_true")
    p.add_argument("--reads-only", action="store_true")
    args = p.parse_args()

    if not DB.exists():
        print(f"no db at {DB}", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(DB))

    cutoff = None
    if args.older_than is not None:
        cutoff_dt = datetime.now() - timedelta(days=args.older_than)
        cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")
        scope = f"older than {args.older_than} days (before {cutoff})"
    else:
        scope = "all rows"

    r_before_total, rd_before_total = counts(db)
    r_target, rd_target = counts(db, cutoff)
    print(f"current totals: recall_log={r_before_total}  read_log={rd_before_total}")
    print(f"would delete ({scope}): recall_log={r_target}  read_log={rd_target}")

    if not args.force:
        print("dry run - pass --force to actually delete")
        return

    where = "WHERE ts < ?" if cutoff else ""
    params = (cutoff,) if cutoff else ()

    if not args.reads_only:
        db.execute(f"DELETE FROM recall_log {where}", params)
        if not cutoff:
            db.execute("DELETE FROM sqlite_sequence WHERE name='recall_log'")
    if not args.recalls_only:
        db.execute(f"DELETE FROM read_log {where}", params)
        if not cutoff:
            db.execute("DELETE FROM sqlite_sequence WHERE name='read_log'")
    db.commit()
    db.execute("VACUUM")

    r_after, rd_after = counts(db)
    print(f"after:  recall_log={r_after}  read_log={rd_after}")


if __name__ == "__main__":
    main()
