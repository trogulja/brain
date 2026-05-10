#!/usr/bin/env python3
"""Normalize lore frontmatter `sources:` references.

Some entries use `raw/NNN-slug.md`, others use just `NNN-slug.md`. Both should
resolve to the same raw file at ``~/.brain/lore/raw/``. Rewrite all to the
``raw/...`` form for consistency.

Dry-run: python normalize_source_refs.py
Apply:   python normalize_source_refs.py --apply
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
LORE_DIR = BRAIN / "lore"

_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_SOURCES_RE = re.compile(r"^(sources:\s*\[)([^\]]*)(\])", re.MULTILINE)
_NUM_SLUG_RE = re.compile(r"^\d{3}-.*\.md$")


def list_lore_files() -> list[Path]:
    return sorted(
        p
        for p in LORE_DIR.iterdir()
        if p.is_file()
        and p.name.endswith(".md")
        and p.name not in {"SCHEMA.md", "INDEX.md"}
    )


def _rewrite_item(item: str) -> str:
    if item.startswith("raw/") or item.startswith("http") or item.startswith("[["):
        return item
    if _NUM_SLUG_RE.match(item):
        return f"raw/{item}"
    return item  # unknown form, leave alone


def _rewrite_sources_block(fm: str) -> str:
    def repl(m: re.Match[str]) -> str:
        pre, items, post = m.group(1), m.group(2), m.group(3)
        new_list = [_rewrite_item(s.strip()) for s in items.split(",") if s.strip()]
        return f"{pre}{', '.join(new_list)}{post}"

    return _SOURCES_RE.sub(repl, fm, count=1)


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    print(f"Normalize source refs ({'APPLY' if apply else 'DRY-RUN'})")

    if not LORE_DIR.is_dir():
        print(f"error: lore dir not found: {LORE_DIR}", file=sys.stderr)
        return 2

    files = list_lore_files()
    changed_count = 0
    total_rewrites = 0

    for f in files:
        content = f.read_text(encoding="utf-8")
        m = _FRONT_RE.match(content)
        if not m:
            continue
        fm, body = m.group(1), m.group(2)

        new_fm = _rewrite_sources_block(fm)
        if new_fm == fm:
            continue

        # Count rewrites for reporting.
        old_match = _SOURCES_RE.search(fm)
        new_match = _SOURCES_RE.search(new_fm)
        old_items = (
            [s.strip() for s in old_match.group(2).split(",")] if old_match else []
        )
        new_items = (
            [s.strip() for s in new_match.group(2).split(",")] if new_match else []
        )
        rewrites = sum(
            1 for o, n in zip(old_items, new_items) if o != n
        )
        total_rewrites += rewrites
        changed_count += 1

        print(f"  {f.name}: {rewrites} ref(s) rewritten")
        for o, n in zip(old_items, new_items):
            if o != n:
                print(f"     {o} → {n}")

        if apply:
            f.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")

    print(f"\n{changed_count} files affected, {total_rewrites} references rewritten total")
    if not apply:
        print("(Dry-run - re-run with --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
