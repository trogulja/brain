#!/usr/bin/env python3
"""Regenerate per-type INDEX.md files in ~/.brain/.

Reads each entry's frontmatter, groups by type-specific field, writes INDEX.md.

Dry-run: python regenerate_indices.py
Apply:   python regenerate_indices.py --apply
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

BRAIN = Path(__file__).resolve().parent.parent


# Per-type config: how to find entries, group them, link to them.
# Mirrors the legacy regenerate-indices.mjs config so output stays byte-equal
# for the existing types (lore, idea, research-link, followup). The `job`
# type is new in the Python port.
TYPE_CONFIG: dict[str, dict[str, Any]] = {
    "lore": {
        "label": "Lore",
        "entry_kind": "files",
        "skip": {"SCHEMA.md", "INDEX.md"},
        "group_by": "category",
        "group_order": [
            "behavior",
            "pattern",
            "convention",
            "lesson",
            "anti-pattern",
            "decision",
            "reference",
        ],
        "group_labels": {
            "behavior": "Behaviors",
            "pattern": "Patterns",
            "convention": "Conventions",
            "lesson": "Lessons",
            "anti-pattern": "Anti-patterns",
            "decision": "Decisions",
            "reference": "References",
        },
        "link_target": lambda slug: f"[[lore/{slug}]]",
        "sort_fn": lambda e: (e["slug"],),
    },
    "idea": {
        "label": "Idea",
        "entry_kind": "folders",
        "skip": {"raw"},
        "group_by": "phase",
        "group_order": ["Exploring", "Decided", "In-Progress", "Done", "Parked"],
        "group_labels": {
            "Exploring": "Exploring",
            "Decided": "Decided",
            "In-Progress": "In-Progress",
            "Done": "Done",
            "Parked": "Parked",
        },
        "link_target": lambda slug: f"[[idea/{slug}]]",
        "sort_fn": lambda e: (e["slug"],),
    },
    "research-link": {
        "label": "Research-Link",
        "entry_kind": "files",
        "skip": {"SCHEMA.md", "INDEX.md"},
        "group_by": "status",
        "group_order": ["inbox", "researching", "researched", "archived"],
        "group_labels": {
            "inbox": "Inbox (unread)",
            "researching": "Researching",
            "researched": "Researched",
            "archived": "Archived",
        },
        "link_target": lambda slug: f"[[research-link/{slug}]]",
        # Sort by `updated` desc within group; fall back to slug.
        # Python sort is ascending, so invert by negating string compare via
        # tuple of (negated-updated-key, slug). Simpler: build a key that
        # sorts the same way the JS comparator does.
        "sort_fn": "by_updated_desc",
    },
    "followup": {
        "label": "Followup",
        "entry_kind": "files",
        "skip": {"SCHEMA.md", "INDEX.md"},
        "group_by": "status",
        "group_order": ["open", "done", "dropped"],
        "group_labels": {
            "open": "Open",
            "done": "Done",
            "dropped": "Dropped",
        },
        "link_target": lambda slug: f"[[followup/{slug}]]",
        "extra_info": lambda fm: f" (with: {fm['with']})" if fm.get("with") else "",
        "sort_fn": "by_updated_desc",
    },
    "job": {
        "label": "Job",
        "entry_kind": "folders",
        "skip": {".archive", "raw"},
        "group_by": "status",
        "group_order": ["active", "done", "archived"],
        "group_labels": {
            "active": "Active",
            "done": "Done",
            "archived": "Archived",
        },
        "link_target": lambda slug: f"[[job/{slug}]]",
        "sort_fn": "by_updated_desc",
    },
}


# ---------- frontmatter parsing ----------

# Matches the leading `---\n...\n---\n` block. The trailing `\n---\n` requires
# the close fence to be followed by a newline; the legacy .mjs has the same
# constraint, so we match its behavior intentionally.
_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w[\w-]*):\s*(.*)$")


def parse_frontmatter(content: str) -> dict[str, Any]:
    m = _FRONT_RE.match(content)
    if not m:
        return {}
    fm: dict[str, Any] = {}
    for line in m.group(1).split("\n"):
        kv = _KV_RE.match(line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        # Strip outer single or double quotes (with '' or \" escapes within).
        if (val.startswith("'") and val.endswith("'")) or (
            val.startswith('"') and val.endswith('"')
        ):
            q = val[0]
            val = val[1:-1]
            if q == "'":
                val = val.replace("''", "'")
            else:
                val = val.replace('\\"', '"').replace("\\\\", "\\")
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            val = [s.strip() for s in inner.split(",") if s.strip()]
        fm[key] = val
    return fm


# ---------- entry collection ----------


def collect_entries(type_name: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    type_dir = BRAIN / type_name
    if not type_dir.is_dir():
        return []

    entries: list[dict[str, Any]] = []
    skip_set: set[str] = config["skip"]
    group_by: str = config["group_by"]

    # Mirror Node's fs.readdir order (which on macOS APFS is insertion/inode
    # order, not sorted). For byte-equality we don't sort here -- groups are
    # sorted later by sort_fn. Use sorted() to keep this deterministic across
    # filesystems; the legacy code's group sort is what determines output.
    for child in sorted(type_dir.iterdir()):
        name = child.name
        if name in skip_set:
            continue
        if name.startswith("."):
            continue

        if config["entry_kind"] == "files":
            if not child.is_file() or not name.endswith(".md"):
                continue
            slug = name[: -len(".md")]
            try:
                content = child.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = parse_frontmatter(content)
            entries.append(
                {
                    "slug": slug,
                    "title": fm.get("title") or slug,
                    "group": fm.get(group_by),
                    "updated": fm.get("updated", ""),
                    "fm": fm,
                }
            )
        elif config["entry_kind"] == "folders":
            if not child.is_dir():
                continue
            folder_note = child / f"{name}.md"
            if not folder_note.is_file():
                continue
            try:
                content = folder_note.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = parse_frontmatter(content)
            entries.append(
                {
                    "slug": name,
                    "title": fm.get("title") or name,
                    "group": fm.get(group_by),
                    "updated": fm.get("updated", ""),
                    "fm": fm,
                }
            )
    return entries


# ---------- sort helpers ----------


def _sort_key(spec: Any) -> Callable[[dict[str, Any]], Any]:
    """Resolve a TYPE_CONFIG sort_fn spec to a key function for list.sort()."""
    if spec == "by_updated_desc":
        # Replicates JS: (b.updated || '').localeCompare(a.updated || '')
        # || a.slug.localeCompare(b.slug).
        # Python's tuple sort is ascending, so flip `updated` by mapping it to
        # a value that sorts it descending. Trick: pair (-1, updated) won't
        # work for strings; use a wrapper that inverts string comparison.
        class _RevStr:
            __slots__ = ("s",)

            def __init__(self, s: str) -> None:
                self.s = s

            def __lt__(self, other: "_RevStr") -> bool:
                return self.s > other.s

            def __eq__(self, other: object) -> bool:
                return isinstance(other, _RevStr) and self.s == other.s

        return lambda e: (_RevStr(e.get("updated") or ""), e["slug"])
    if callable(spec):
        return spec
    raise ValueError(f"unknown sort_fn spec: {spec!r}")


# ---------- index generation ----------


def build_index(
    type_name: str, config: dict[str, Any], entries: list[dict[str, Any]]
) -> str:
    lines: list[str] = [f"# {config['label']} Index", ""]

    group_order: list[str] = config["group_order"]
    groups: dict[str, list[dict[str, Any]]] = {k: [] for k in group_order}
    ungrouped: list[dict[str, Any]] = []

    for entry in entries:
        gk = entry["group"]
        if gk and gk in groups:
            groups[gk].append(entry)
        else:
            ungrouped.append(entry)

    sort_key = _sort_key(config["sort_fn"])
    for k in group_order:
        groups[k].sort(key=sort_key)
    ungrouped.sort(key=sort_key)

    extra_info: Callable[[dict[str, Any]], str] | None = config.get("extra_info")
    link_target: Callable[[str], str] = config["link_target"]
    group_labels: dict[str, str] = config["group_labels"]
    group_by: str = config["group_by"]

    for k in group_order:
        listed = groups[k]
        lines.append(f"## {group_labels[k]}")
        lines.append("")
        if not listed:
            lines.append("_(none)_")
            lines.append("")
        else:
            for entry in listed:
                extra = extra_info(entry["fm"]) if extra_info else ""
                lines.append(
                    f"- {link_target(entry['slug'])} - {entry['title']}{extra}"
                )
            lines.append("")

    if ungrouped:
        lines.append("## Ungrouped (missing or unknown grouping field)")
        lines.append("")
        for entry in ungrouped:
            gv = entry["group"] if entry["group"] else "missing"
            lines.append(
                f"- {link_target(entry['slug'])} - {entry['title']} _({group_by}: {gv})_"
            )
        lines.append("")

    return "\n".join(lines)


# ---------- main ----------


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    print(f"Regenerate indices ({'APPLY' if apply else 'DRY-RUN'})")

    for type_name, config in TYPE_CONFIG.items():
        entries = collect_entries(type_name, config)
        index_content = build_index(type_name, config, entries)
        index_path = BRAIN / type_name / "INDEX.md"

        print(f"\n=== {type_name} ({len(entries)} entries) ===")

        # Summary by group.
        group_counts: dict[str, int] = {k: 0 for k in config["group_order"]}
        ungrouped = 0
        for entry in entries:
            k = entry["group"]
            if k and k in group_counts:
                group_counts[k] += 1
            else:
                ungrouped += 1
        summary = ", ".join(
            f"{k}={n}" for k, n in group_counts.items() if n > 0
        )
        ungrouped_part = f", ungrouped={ungrouped}" if ungrouped else ""
        print(f"  {summary or '(empty)'}{ungrouped_part}")
        print(f"  → {index_path} ({len(index_content.split(chr(10)))} lines)")

        if apply:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(index_content, encoding="utf-8")

    print(f"\n{'Indices written.' if apply else '(Dry-run - re-run with --apply.)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
