#!/usr/bin/env python3
"""
audit-l0 - audit ~/.claude/CLAUDE.md against behavioral lore.

Reports:
- Token count of CLAUDE.md (warns if > soft cap, default 2000)
- For each rule (markdown bullet line), top-3 BM25 candidates from
  category: behavior lore - provenance candidates
- Behavioral lore unchanged 6+ months - staleness candidates
- BM25-similar rule pairs within CLAUDE.md - merge candidates

Pure audit. Reports findings; never modifies anything. The conversation
following an audit decides what to act on.

Usage:
  audit-l0.py
  audit-l0.py --cap 1500            # custom soft cap
  audit-l0.py --json                # machine-readable output
  audit-l0.py --claude-md PATH      # alternate CLAUDE.md path
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
DB_PATH = BRAIN / "search.db"
DEFAULT_CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
DEFAULT_CAP = 2000
STALENESS_DAYS = 180  # 6 months
RECALL_PY = BRAIN / "scripts" / "recall.py"


def estimate_tokens(text):
    """Rough token estimate: 1 token per ~4 chars (matches Claude tokenizer
    closely enough for soft warnings). Avoids depending on tiktoken."""
    return len(text) // 4


def parse_rules(claude_md_text):
    """Extract bullet-point rules from CLAUDE.md.

    A rule is a top-level bullet in any section. Indented sub-bullets
    are merged into the parent rule. We strip section headers and
    code fences.
    """
    rules = []
    in_fence = False
    current = None
    section = None

    for raw_line in claude_md_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            if current:
                rules.append(current)
                current = None
            continue
        m = re.match(r"^(\s*)-\s+(.+)$", line)
        if m:
            indent = len(m.group(1))
            content = m.group(2).strip()
            if indent == 0:
                if current:
                    rules.append(current)
                current = {"section": section, "text": content}
            elif current:
                current["text"] += " " + content
            continue
        if not line.strip():
            continue
        # continuation of current rule (paragraph following bullet)
        if current and line.startswith(" "):
            current["text"] += " " + line.strip()

    if current:
        rules.append(current)
    return rules


def bm25_candidates_for_rule(rule_text, top_n=3):
    """Run recall.py against behavioral lore for a given rule's text.
    Returns [(path, title, score), ...] up to top_n.
    """
    try:
        r = subprocess.run(
            ["python3", str(RECALL_PY), "--type", "lore", "--top", str(top_n * 3),
             "--json", rule_text[:200]],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []

    # Filter to category: behavior only
    out = []
    for result in data.get("results", []):
        abs_path = result.get("abs_path", "")
        if not abs_path:
            continue
        try:
            text = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^category:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1) == "behavior":
            out.append((result.get("path", ""), result.get("title", ""), result.get("score", 0)))
        if len(out) >= top_n:
            break
    return out


def bm25_similar_rule_pairs(rules, threshold=2.0):
    """Self-similarity over rule texts. Uses recall.py against the brain
    indexed corpus, but really we want pairwise rule comparison.
    Approach: query each rule's text and check if other rules' texts
    appear as top results - too noisy. Use a lighter approach: token
    overlap (Jaccard-like).
    """
    pairs = []

    def tokens(text):
        return set(t for t in re.findall(r"\w{4,}", text.lower()) if t)

    rule_tokens = [tokens(r["text"]) for r in rules]
    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            ti, tj = rule_tokens[i], rule_tokens[j]
            if not ti or not tj:
                continue
            shared = len(ti & tj)
            smaller = min(len(ti), len(tj))
            if smaller == 0:
                continue
            ratio = shared / smaller
            if ratio >= 0.4 and shared >= 3:
                pairs.append((i, j, shared, ratio))
    pairs.sort(key=lambda p: -p[3])
    return pairs[:5]


def stale_behavioral_lore():
    """List category: behavior lore unchanged 6+ months."""
    cutoff_dt = datetime.now() - timedelta(days=STALENESS_DAYS)
    out = []
    lore_dir = BRAIN / "lore"
    for path in lore_dir.glob("*.md"):
        if path.name in {"INDEX.md", "SCHEMA.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^category:\s*(\S+)", text, re.MULTILINE)
        if not m or m.group(1) != "behavior":
            continue
        m_updated = re.search(r"^updated:\s*(\S+)", text, re.MULTILINE)
        if not m_updated:
            continue
        try:
            updated = datetime.strptime(m_updated.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        if updated < cutoff_dt:
            title_m = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else path.stem
            out.append((str(path.relative_to(BRAIN)), title, m_updated.group(1)))
    out.sort(key=lambda r: r[2])
    return out


def behavioral_lore_count():
    count = 0
    for path in (BRAIN / "lore").glob("*.md"):
        if path.name in {"INDEX.md", "SCHEMA.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^category:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1) == "behavior":
            count += 1
    return count


def format_report(report, claude_md_path, cap):
    out = []
    t = report["totals"]
    out.append(f"# L0 audit - {claude_md_path}")
    out.append("")

    cap_status = "OK" if t["tokens"] <= cap else f"OVER by {t['tokens'] - cap}"
    out.append(f"- Tokens: ~{t['tokens']} / {cap} cap  ({cap_status})")
    out.append(f"- Rules parsed: {t['rules']}")
    out.append(f"- Behavioral lore entries: {t['behavioral_lore']}")
    if t["tokens"] > cap:
        out.append("")
        out.append(f"⚠️  CLAUDE.md is over the soft cap. Consider consolidating or trimming rules.")

    if report["provenance"]:
        out.append("")
        out.append("## Provenance candidates (BM25 → category: behavior lore)")
        out.append("")
        out.append("_Top 3 lore candidates per rule. None = no behavioral backing - capture-as-you-go on next revision._")
        out.append("")
        for entry in report["provenance"]:
            section = f" *[{entry['section']}]*" if entry["section"] else ""
            out.append(f"### Rule{section}")
            out.append(f"> {entry['text'][:160]}{'…' if len(entry['text']) > 160 else ''}")
            if entry["candidates"]:
                for c in entry["candidates"]:
                    out.append(f"- {c['path']} - {c['title']} (score: {c['score']:.2f})")
            else:
                out.append("- _(no behavioral lore matches - preference or backing missing)_")
            out.append("")

    if report["merge_candidates"]:
        out.append("## Merge candidates (similar rules in CLAUDE.md)")
        out.append("")
        out.append("_Rule pairs with high token overlap. Consider whether they should be one rule._")
        out.append("")
        for pair in report["merge_candidates"]:
            out.append(f"- **A:** {pair['a'][:120]}{'…' if len(pair['a']) > 120 else ''}")
            out.append(f"  **B:** {pair['b'][:120]}{'…' if len(pair['b']) > 120 else ''}")
            out.append(f"  shared tokens: {pair['shared']}, overlap: {pair['ratio']:.0%}")
        out.append("")

    if report["stale_behavioral_lore"]:
        out.append("## Stale behavioral lore (>6 months unchanged)")
        out.append("")
        out.append("_Still relevant? Or should the behavior have evolved?_")
        out.append("")
        for path, title, updated in report["stale_behavioral_lore"]:
            out.append(f"- {path} - {title} (updated {updated})")
        out.append("")

    return "\n".join(out).rstrip()


def main():
    p = argparse.ArgumentParser(prog="audit-l0", description="Audit ~/.claude/CLAUDE.md against behavioral lore")
    p.add_argument("--claude-md", type=Path, default=DEFAULT_CLAUDE_MD, help="path to CLAUDE.md (default: ~/.claude/CLAUDE.md)")
    p.add_argument("--cap", type=int, default=DEFAULT_CAP, help=f"soft token cap (default {DEFAULT_CAP})")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

    if not args.claude_md.exists():
        print(f"error: {args.claude_md} does not exist", file=sys.stderr)
        sys.exit(2)
    if not RECALL_PY.exists():
        print(f"error: {RECALL_PY} not found - Phase 1 not installed?", file=sys.stderr)
        sys.exit(2)

    text = args.claude_md.read_text(encoding="utf-8")
    tokens = estimate_tokens(text)
    rules = parse_rules(text)

    provenance = []
    for rule in rules:
        candidates = bm25_candidates_for_rule(rule["text"])
        provenance.append({
            "section": rule["section"],
            "text": rule["text"],
            "candidates": [
                {"path": c[0], "title": c[1], "score": c[2]}
                for c in candidates
            ],
        })

    pairs = bm25_similar_rule_pairs(rules)
    merge_candidates = [
        {
            "a": rules[i]["text"],
            "b": rules[j]["text"],
            "shared": shared,
            "ratio": ratio,
        }
        for i, j, shared, ratio in pairs
    ]

    stale = stale_behavioral_lore()
    n_behavior = behavioral_lore_count()

    report = {
        "totals": {
            "tokens": tokens,
            "rules": len(rules),
            "behavioral_lore": n_behavior,
        },
        "provenance": provenance,
        "merge_candidates": merge_candidates,
        "stale_behavioral_lore": stale,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report, args.claude_md, args.cap))


if __name__ == "__main__":
    main()
