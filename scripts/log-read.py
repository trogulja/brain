#!/usr/bin/env python3
"""
PostToolUse hook: log Read tool calls under ~/.brain/ to read_log.

Reads Claude Code's hook payload from stdin (JSON), checks if it's a Read
on a file under ~/.brain/, and appends a (ts, path) row to read_log.
Correlation to recalls happens at analyze time via path-overlap +
time-window - no session_id or recall_id at write time.

Must be fast and silent - fires after every tool call. Bails early on the
~99% of cases that aren't relevant.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
DB_PATH = BRAIN / "search.db"
SKIP_MARKER = BRAIN / ".cache" / "skip-log"
SKIP_STALE_SECONDS = 1800  # 30 min


def should_skip_logging():
    """Sentinel: skills doing meta-work (cleanup, remember dedupe) touch
    ~/.brain/.cache/skip-log to mark their reads as audit, not use.
    Auto-stales after 30 min so a crashed skill doesn't permanently disable
    logging.
    """
    if not SKIP_MARKER.exists():
        return False
    try:
        age = time.time() - SKIP_MARKER.stat().st_mtime
    except OSError:
        return False
    return age < SKIP_STALE_SECONDS


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, ValueError):
        return

    if payload.get("tool_name") != "Read":
        return

    if should_skip_logging():
        return

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    try:
        abs_path = Path(file_path).resolve()
    except (OSError, ValueError):
        return

    try:
        abs_path.relative_to(BRAIN)
    except ValueError:
        return  # not under ~/.brain/

    if not DB_PATH.exists():
        return  # nothing to log against; recall.py creates the DB

    try:
        db = sqlite3.connect(str(DB_PATH), timeout=2.0)
    except sqlite3.OperationalError:
        return

    try:
        db.execute(
            "INSERT INTO read_log (ts, path) VALUES (?, ?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), str(abs_path)),
        )
        db.commit()
    except sqlite3.Error:
        pass
    finally:
        db.close()


if __name__ == "__main__":
    main()
