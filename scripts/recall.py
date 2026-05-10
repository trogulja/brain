#!/usr/bin/env python3
"""
recall - hybrid (BM25 + semantic) search over ~/.brain/

Indexes all .md files in the brain (excluding INDEX/SCHEMA/raw), returns top
results with snippets. Maintains an FTS5 index plus an embeddings table in
~/.brain/search.db; FTS reindexes on every call, embeddings are built by
scripts/build-embeddings.py (run that separately when notes change).

By default merges BM25 and semantic ranks via Reciprocal Rank Fusion (k=60).

Usage:
  recall.py "query terms"
  recall.py --type lore "auth"           # filter by type
  recall.py --top 10 "..."               # change result count
  recall.py --mode bm25 "..."            # BM25 only (skip model load)
  recall.py --mode semantic "..."        # embeddings only
  recall.py --mode hybrid "..."          # default - RRF merge
  recall.py --json "..."                 # machine-readable output
  recall.py --explain "..."              # show all stages (BM25/semantic/RRF/final)
  recall.py --explain --json "..."       # structured per-stage JSON
  recall.py --reindex                    # force full FTS reindex
"""

# Defensive bootstrap: re-exec under the brain venv python if invoked with any
# other interpreter (e.g. `python3 path/recall.py`). Hybrid/semantic modes need
# numpy, torch, sentence-transformers - installed only inside the brain venv.
#
# Venv resolution order:
#   1. $BRAIN_VENV (env override; either the venv root or the python binary).
#   2. <script-dir>/../.venv/bin/python (the script lives at <BRAIN>/scripts/).
# A non-existent resolved path is a hard error (no silent fallback).
import os as _os
import sys as _sys
from pathlib import Path as _Path


def _resolve_venv_python() -> _Path:
    override = _os.environ.get("BRAIN_VENV")
    if override:
        p = _Path(override).expanduser()
        # Accept either the venv root (with `bin/python`) or the python binary.
        if p.is_dir():
            return p / "bin" / "python"
        return p
    return _Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"


_VENV_PY = _resolve_venv_python()
if _sys.executable != str(_VENV_PY):
    if not _VENV_PY.exists():
        _sys.stderr.write(
            f"error: brain venv python not found at {_VENV_PY}\n"
            f"  set BRAIN_VENV to the venv root (or python binary), or run\n"
            f"  `python install.py --with-semantic` to create one.\n"
        )
        _sys.exit(2)
    _os.execv(str(_VENV_PY), [str(_VENV_PY), __file__, *_sys.argv[1:]])

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
DB_PATH = BRAIN / "search.db"
DEFAULT_TOP = 5
SCHEMA_VERSION = "4"

EXCLUDE_NAMES = {"INDEX.md", "SCHEMA.md", "MEMORY.md", "README.md"}
EXCLUDE_DIRS = {"attachments", ".cache", ".git", ".github", "raw"}
VALID_TYPES = {"lore", "idea", "research-link"}


def iter_brain_files():
    for path in BRAIN.rglob("*.md"):
        if path.name in EXCLUDE_NAMES:
            continue
        rel_parts = path.relative_to(BRAIN).parts
        if any(p in EXCLUDE_DIRS for p in rel_parts):
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue
        yield path


def parse_frontmatter(text):
    """Return (frontmatter_dict, body). Hand-rolled, simple key:value only."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5:]
    fm = {}
    for line in fm_block.splitlines():
        line = line.rstrip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip().strip("\"'")
        if v.startswith("[") and v.endswith("]"):
            v = [item.strip().strip("\"'") for item in v[1:-1].split(",") if item.strip()]
        fm[k] = v
    return fm, body


def extract_title(fm, body, path):
    if "title" in fm and fm["title"]:
        return fm["title"] if isinstance(fm["title"], str) else " ".join(fm["title"])
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def extract_tags(fm):
    tags = fm.get("tags", "")
    if isinstance(tags, list):
        return " ".join(tags)
    return tags or ""


def infer_type(fm, path):
    """Type from frontmatter, fallback to top-level directory under ~/.brain/."""
    t = fm.get("type", "")
    if isinstance(t, str) and t in VALID_TYPES:
        return t
    rel = path.relative_to(BRAIN).parts
    if rel and rel[0] in VALID_TYPES:
        return rel[0]
    return ""


def init_db(db):
    """Initialise schema; rebuild if version mismatch (search.db is disposable)."""
    db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    row = db.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()
    current = row[0] if row else None

    if current != SCHEMA_VERSION:
        db.executescript("""
            DROP TABLE IF EXISTS docs;
            DROP TABLE IF EXISTS files;
            DROP TABLE IF EXISTS recall_log;
            DROP TABLE IF EXISTS read_log;
        """)

    db.executescript(f"""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            type TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
            path UNINDEXED,
            type UNINDEXED,
            title,
            tags,
            body,
            tokenize = 'porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS recall_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            query TEXT NOT NULL,
            type_filter TEXT,
            results_json TEXT
        );
        CREATE TABLE IF NOT EXISTS read_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            path TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_recall_ts ON recall_log(ts);
        CREATE INDEX IF NOT EXISTS idx_read_ts ON read_log(ts);
        CREATE INDEX IF NOT EXISTS idx_read_path ON read_log(path);
    """)
    db.execute(
        "INSERT OR REPLACE INTO meta (k, v) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    db.commit()


def reindex(db, force=False):
    added = updated = removed = 0
    on_disk = {}
    for path in iter_brain_files():
        try:
            on_disk[str(path)] = path.stat().st_mtime
        except OSError:
            continue

    indexed = {row[0]: row[1] for row in db.execute("SELECT path, mtime FROM files")}

    for path_str in list(indexed):
        if path_str not in on_disk:
            db.execute("DELETE FROM docs WHERE path = ?", (path_str,))
            db.execute("DELETE FROM files WHERE path = ?", (path_str,))
            removed += 1

    for path_str, mtime in on_disk.items():
        prior = indexed.get(path_str)
        if not force and prior is not None and prior >= mtime:
            continue
        try:
            text = Path(path_str).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        path_obj = Path(path_str)
        title = extract_title(fm, body, path_obj)
        tags = extract_tags(fm)
        doc_type = infer_type(fm, path_obj)

        if prior is None:
            db.execute(
                "INSERT INTO docs (path, type, title, tags, body) VALUES (?, ?, ?, ?, ?)",
                (path_str, doc_type, title, tags, body),
            )
            db.execute(
                "INSERT INTO files (path, mtime, type) VALUES (?, ?, ?)",
                (path_str, mtime, doc_type),
            )
            added += 1
        else:
            db.execute("DELETE FROM docs WHERE path = ?", (path_str,))
            db.execute(
                "INSERT INTO docs (path, type, title, tags, body) VALUES (?, ?, ?, ?, ?)",
                (path_str, doc_type, title, tags, body),
            )
            db.execute(
                "UPDATE files SET mtime = ?, type = ? WHERE path = ?",
                (mtime, doc_type, path_str),
            )
            updated += 1

    db.commit()
    return added, updated, removed


SEARCH_SQL = """
    SELECT path,
           type,
           title,
           snippet(docs, 4, '«', '»', '...', 16) AS snip,
           bm25(docs, 0.0, 0.0, 10.0, 5.0, 1.0) AS score
    FROM docs
    WHERE docs MATCH ?
    {type_clause}
    ORDER BY score
    LIMIT ?
"""


def search(db, query, top_n, type_filter):
    type_clause = "AND type = ?" if type_filter else ""
    sql = SEARCH_SQL.format(type_clause=type_clause)
    params = [query]
    if type_filter:
        params.append(type_filter)
    params.append(top_n)

    try:
        return list(db.execute(sql, params))
    except sqlite3.OperationalError:
        terms = re.findall(r"\w+", query)
        if not terms:
            return []
        fallback = " OR ".join(terms)
        params[0] = fallback
        return list(db.execute(sql, params))


def semantic_search(db, query, top_n, type_filter):
    """Embed the query and return top_n (path, score) by cosine similarity.

    Returns [] if the embeddings table is empty/missing - caller decides
    whether to fall back or fail.
    """
    import numpy as np  # local import keeps BM25-only path light

    rows = list(db.execute("SELECT path, dim, vector FROM embeddings"))
    if not rows:
        return []
    paths = [r[0] for r in rows]
    dim = rows[0][1]
    matrix = np.frombuffer(b"".join(r[2] for r in rows), dtype=np.float32).reshape(
        len(rows), dim
    )

    if type_filter:
        keep = [
            i
            for i, p in enumerate(paths)
            if db.execute("SELECT type FROM files WHERE path = ?", (p,)).fetchone()
            == (type_filter,)
        ]
        if not keep:
            return []
        matrix = matrix[keep]
        paths = [paths[i] for i in keep]

    sys.path.insert(0, str(Path(__file__).parent))
    import _nomic  # noqa: E402

    model, _ = _nomic.load_trusted_model(quiet=True)
    q_vec = model.encode(
        [_nomic.QUERY_PREFIX + query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
    scores = matrix @ q_vec  # cosine since both sides normalized
    top_idx = np.argsort(-scores)[:top_n]
    return [(paths[i], float(scores[i])) for i in top_idx]


def rrf_merge(bm25_rows, sem_rows, top_n, k=60):
    """Reciprocal Rank Fusion. Higher score = better.

    bm25_rows: rows from search() - (path, type, title, snip, bm25_score)
              where bm25_score is negative-better (sqlite bm25 convention).
    sem_rows:  list of (path, cosine_score) from semantic_search.
    Returns list of (path, rrf_score, bm25_rank or None, sem_rank or None),
    sorted by rrf_score desc, length <= top_n.
    """
    contrib: dict[str, dict] = {}
    for rank, row in enumerate(bm25_rows, start=1):
        path = row[0]
        contrib.setdefault(path, {"bm25_rank": None, "sem_rank": None})
        contrib[path]["bm25_rank"] = rank
    for rank, (path, _score) in enumerate(sem_rows, start=1):
        contrib.setdefault(path, {"bm25_rank": None, "sem_rank": None})
        contrib[path]["sem_rank"] = rank

    out = []
    for path, info in contrib.items():
        score = 0.0
        if info["bm25_rank"] is not None:
            score += 1.0 / (k + info["bm25_rank"])
        if info["sem_rank"] is not None:
            score += 1.0 / (k + info["sem_rank"])
        out.append((path, score, info["bm25_rank"], info["sem_rank"]))
    out.sort(key=lambda t: t[1], reverse=True)
    return out[:top_n]


def fetch_doc_meta(db, path):
    """Pull (type, title, body) from the FTS docs table for a given path."""
    row = db.execute(
        "SELECT type, title, body FROM docs WHERE path = ?", (path,)
    ).fetchone()
    if row is None:
        return ("", Path(path).stem, "")
    return row


def make_snippet(body, query, length=160):
    """Cheap snippet: first window around any query term, else head of body."""
    terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    body_l = body.lower()
    for t in terms:
        idx = body_l.find(t)
        if idx != -1:
            start = max(0, idx - 40)
            end = min(len(body), start + length)
            snip = body[start:end].replace("\n", " ")
            return ("..." if start > 0 else "") + snip + ("..." if end < len(body) else "")
    head = body[:length].replace("\n", " ")
    return head + ("..." if len(body) > length else "")


def log_recall(db, query, type_filter, mode, results):
    cur = db.execute(
        "INSERT INTO recall_log (ts, query, type_filter, results_json) VALUES (?, ?, ?, ?)",
        (
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            query,
            type_filter,
            json.dumps({"mode": mode, "results": results}),
        ),
    )
    db.commit()
    return cur.lastrowid


def format_human(results, recall_id, mode):
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, 1):
        rel = Path(r["abs_path"]).relative_to(BRAIN)
        type_tag = f"[{r['type']}] " if r["type"] else ""
        lines.append(f"[{i}] {type_tag}{rel}")
        score_parts = []
        if mode == "hybrid":
            bm = r.get("bm25_rank")
            sm = r.get("sem_rank")
            score_parts.append(f"rrf={r['score']:.4f}")
            score_parts.append(f"bm25={'#' + str(bm) if bm else '-'}")
            score_parts.append(f"sem={'#' + str(sm) if sm else '-'}")
        elif mode == "bm25":
            score_parts.append(f"bm25={r['score']:.2f}")
        else:  # semantic
            score_parts.append(f"cos={r['score']:.3f}")
        lines.append(f"    {r['title']}  ({' '.join(score_parts)})")
        if r.get("snippet"):
            lines.append(f"    {' '.join(r['snippet'].split())}")
        lines.append("")
    if recall_id is not None:
        lines.append(f"(recall_id: {recall_id}, mode: {mode})")
    return "\n".join(lines).rstrip()


def format_json(results, recall_id, mode):
    return json.dumps(
        {"recall_id": recall_id, "mode": mode, "results": results},
        indent=2,
    )


def _bm25_stage_entries(db, bm25_rows):
    """Stage payload for BM25 candidates (rank-ordered, score is positive-better)."""
    out = []
    for rank, row in enumerate(bm25_rows, start=1):
        path, doc_type, title, _snip, score = row
        out.append(
            {
                "rank": rank,
                "abs_path": path,
                "path": str(Path(path).relative_to(BRAIN)),
                "type": doc_type or "",
                "title": title,
                "bm25_score": -score,  # sqlite bm25 is negative-better
            }
        )
    return out


def _semantic_stage_entries(db, sem_rows):
    """Stage payload for semantic candidates (rank-ordered cosine similarity)."""
    out = []
    for rank, (path, cos) in enumerate(sem_rows, start=1):
        doc_type, title, _body = fetch_doc_meta(db, path)
        out.append(
            {
                "rank": rank,
                "abs_path": path,
                "path": str(Path(path).relative_to(BRAIN)),
                "type": doc_type or "",
                "title": title,
                "cosine_score": cos,
            }
        )
    return out


def _rrf_stage_entries(db, rrf_rows):
    """Stage payload for RRF merged ranks."""
    out = []
    for rank, (path, rrf_score, bm_rank, sem_rank) in enumerate(rrf_rows, start=1):
        doc_type, title, _body = fetch_doc_meta(db, path)
        out.append(
            {
                "rank": rank,
                "abs_path": path,
                "path": str(Path(path).relative_to(BRAIN)),
                "type": doc_type or "",
                "title": title,
                "rrf_score": rrf_score,
                "bm25_rank": bm_rank,
                "sem_rank": sem_rank,
            }
        )
    return out


def format_explain_human(stages, results, recall_id, mode):
    """Render all four stages as human-readable text with clear section headers."""
    lines = []

    def header(name):
        lines.append(f"=== {name} ===")

    def render_skipped(reason):
        lines.append(f"  [skipped - {reason}]")
        lines.append("")

    # Stage 1: BM25
    header("Stage 1: BM25 candidates")
    if stages["bm25"] is None:
        render_skipped(f"{mode} mode")
    elif not stages["bm25"]:
        lines.append("  (no candidates)")
        lines.append("")
    else:
        for e in stages["bm25"]:
            type_tag = f"[{e['type']}] " if e["type"] else ""
            lines.append(f"  #{e['rank']:<2} bm25={e['bm25_score']:.2f}  {type_tag}{e['path']}")
            lines.append(f"        {e['title']}")
        lines.append("")

    # Stage 2: Semantic
    header("Stage 2: Semantic candidates (cosine)")
    if stages["semantic"] is None:
        render_skipped(f"{mode} mode")
    elif not stages["semantic"]:
        lines.append("  (no candidates - embeddings empty or unavailable)")
        lines.append("")
    else:
        for e in stages["semantic"]:
            type_tag = f"[{e['type']}] " if e["type"] else ""
            lines.append(f"  #{e['rank']:<2} cos={e['cosine_score']:.3f}  {type_tag}{e['path']}")
            lines.append(f"        {e['title']}")
        lines.append("")

    # Stage 3: RRF merge
    header("Stage 3: RRF merged ranks (k=60)")
    if stages["rrf"] is None:
        render_skipped(f"{mode} mode")
    elif not stages["rrf"]:
        lines.append("  (no merged candidates)")
        lines.append("")
    else:
        for e in stages["rrf"]:
            type_tag = f"[{e['type']}] " if e["type"] else ""
            bm = f"#{e['bm25_rank']}" if e["bm25_rank"] is not None else "-"
            sm = f"#{e['sem_rank']}" if e["sem_rank"] is not None else "-"
            lines.append(
                f"  #{e['rank']:<2} rrf={e['rrf_score']:.4f}  bm25={bm} sem={sm}  {type_tag}{e['path']}"
            )
            lines.append(f"        {e['title']}")
        lines.append("")

    # Stage 4: Final results
    header("Stage 4: Final selected results")
    if not results:
        lines.append("  (no results)")
        lines.append("")
    else:
        for i, r in enumerate(results, 1):
            rel = Path(r["abs_path"]).relative_to(BRAIN)
            type_tag = f"[{r['type']}] " if r["type"] else ""
            score_parts = []
            if mode == "hybrid":
                bm = r.get("bm25_rank")
                sm = r.get("sem_rank")
                score_parts.append(f"rrf={r['score']:.4f}")
                score_parts.append(f"bm25={'#' + str(bm) if bm else '-'}")
                score_parts.append(f"sem={'#' + str(sm) if sm else '-'}")
            elif mode == "bm25":
                score_parts.append(f"bm25={r['score']:.2f}")
            else:  # semantic
                score_parts.append(f"cos={r['score']:.3f}")
            lines.append(f"  [{i}] {type_tag}{rel}  ({' '.join(score_parts)})")
            lines.append(f"      {r['title']}")
            if r.get("snippet"):
                lines.append(f"      {' '.join(r['snippet'].split())}")
        lines.append("")

    if recall_id is not None:
        lines.append(f"(recall_id: {recall_id}, mode: {mode})")

    return "\n".join(lines).rstrip()


def format_explain_json(stages, results, recall_id, mode):
    """Render all four stages as structured JSON for machine consumption."""
    return json.dumps(
        {
            "recall_id": recall_id,
            "mode": mode,
            "bm25": stages["bm25"],
            "semantic": stages["semantic"],
            "rrf": stages["rrf"],
            "final": results,
        },
        indent=2,
    )


def build_results(db, ranked, query, mode):
    """Turn ranked rows into the unified result-dict shape used by formatters.

    `ranked` is one of:
      - bm25 rows: (path, type, title, snip, score)         when mode=bm25
      - semantic rows: (path, cos_score)                    when mode=semantic
      - rrf rows: (path, rrf_score, bm25_rank, sem_rank)    when mode=hybrid
    """
    out = []
    for row in ranked:
        if mode == "bm25":
            path, doc_type, title, snip, score = row
            out.append(
                {
                    "abs_path": path,
                    "path": str(Path(path).relative_to(BRAIN)),
                    "type": doc_type or "",
                    "title": title,
                    "snippet": snip,
                    "score": -score,  # sqlite bm25 is negative-better
                }
            )
        elif mode == "semantic":
            path, cos = row
            doc_type, title, body = fetch_doc_meta(db, path)
            out.append(
                {
                    "abs_path": path,
                    "path": str(Path(path).relative_to(BRAIN)),
                    "type": doc_type or "",
                    "title": title,
                    "snippet": make_snippet(body, query),
                    "score": cos,
                }
            )
        else:  # hybrid
            path, rrf, bm_rank, sem_rank = row
            doc_type, title, body = fetch_doc_meta(db, path)
            out.append(
                {
                    "abs_path": path,
                    "path": str(Path(path).relative_to(BRAIN)),
                    "type": doc_type or "",
                    "title": title,
                    "snippet": make_snippet(body, query),
                    "score": rrf,
                    "bm25_rank": bm_rank,
                    "sem_rank": sem_rank,
                }
            )
    return out


def main():
    p = argparse.ArgumentParser(prog="recall", description="hybrid search over ~/.brain/")
    p.add_argument("query", nargs="*", help="search terms")
    p.add_argument("--type", choices=sorted(VALID_TYPES), help="filter by entry type")
    p.add_argument("--top", type=int, default=DEFAULT_TOP, help=f"number of results (default {DEFAULT_TOP})")
    p.add_argument(
        "--mode",
        choices=["hybrid", "bm25", "semantic"],
        default="hybrid",
        help="search mode (default hybrid; bm25 skips model load)",
    )
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    p.add_argument(
        "--explain",
        action="store_true",
        help="show all stages (BM25, semantic, RRF merge, final). Combine with --json for structured output.",
    )
    p.add_argument("--reindex", action="store_true", help="force full reindex")
    args = p.parse_args()

    if not BRAIN.exists():
        print(f"error: brain not found at {BRAIN}", file=sys.stderr)
        sys.exit(2)

    db = sqlite3.connect(str(DB_PATH))
    init_db(db)

    a, u, r = reindex(db, force=args.reindex)
    if (a or u or r) and not args.json:
        print(f"(reindex: +{a} ~{u} -{r})", file=sys.stderr)

    if not args.query:
        if not args.reindex:
            print("usage: recall.py [--mode M] [--type T] [--top N] [--json] [--reindex] <query>", file=sys.stderr)
            sys.exit(1)
        return

    query = " ".join(args.query)

    # Pull a wider pool when fusing so RRF has signal beyond the final top_n.
    pool = max(args.top * 4, 20) if args.mode == "hybrid" else args.top

    # Stage capture for --explain. Populated below as each stage runs.
    # Each entry is None if the stage was skipped due to mode, [] if it ran
    # but returned nothing.
    bm_rows: list | None = None
    sm_rows: list | None = None
    rrf_rows: list | None = None

    if args.mode == "bm25":
        ranked = search(db, query, args.top, args.type)
        bm_rows = ranked
    elif args.mode == "semantic":
        ranked = semantic_search(db, query, args.top, args.type)
        sm_rows = ranked
    else:  # hybrid
        bm = search(db, query, pool, args.type)
        sm = semantic_search(db, query, pool, args.type)
        bm_rows = bm
        sm_rows = sm
        if not sm and not bm:
            ranked = []
            rrf_rows = []
        elif not sm:
            print("(no embeddings available - falling back to BM25)", file=sys.stderr)
            ranked = bm[: args.top]
            args = argparse.Namespace(**{**vars(args), "mode": "bm25"})
        else:
            rrf_rows = rrf_merge(bm, sm, args.top)
            ranked = rrf_rows

    results = build_results(db, ranked, query, args.mode)
    recall_id = log_recall(db, query, args.type, args.mode, results)

    if args.explain:
        # Each stage is None if the chosen mode skipped it (rendered as
        # "[skipped - <mode>]"), [] if it ran but returned nothing.
        stages = {
            "bm25": _bm25_stage_entries(db, bm_rows) if bm_rows is not None else None,
            "semantic": _semantic_stage_entries(db, sm_rows) if sm_rows is not None else None,
            "rrf": _rrf_stage_entries(db, rrf_rows) if rrf_rows is not None else None,
        }
        if args.json:
            print(format_explain_json(stages, results, recall_id, args.mode))
        else:
            print(format_explain_human(stages, results, recall_id, args.mode))
        return

    if args.json:
        print(format_json(results, recall_id, args.mode))
    else:
        print(format_human(results, recall_id, args.mode))


if __name__ == "__main__":
    main()
