#!/usr/bin/env python3
"""build-embeddings - generate semantic embeddings for ~/.brain/ notes.

Stores 768-dim float32 vectors in search.db, keyed by absolute file path
(matching recall.py's existing `files.path` convention) so a hybrid search
can join cleanly. Re-runs are incremental: only files whose mtime changed
get re-embedded.

The model loader (with code_revision pinning + SHA-256 audit verification)
lives in _nomic.py.
"""
from __future__ import annotations

# Defensive bootstrap: re-exec under the brain venv python if invoked with
# any other interpreter. numpy / torch / sentence-transformers live only in
# the brain venv.
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

import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

import _nomic

BRAIN = Path(__file__).resolve().parent.parent
DB = BRAIN / "search.db"
EMBED_SCHEMA_VERSION = "2"  # bumped when changing embeddings table layout


def discover_notes() -> list[Path]:
    out: list[Path] = []
    for sub in ("lore", "idea", "research-link"):
        for p in (BRAIN / sub).rglob("*.md"):
            if p.name in {"INDEX.md", "SCHEMA.md", "MEMORY.md", "README.md"}:
                continue
            if any(part.startswith(".") or part == "raw" for part in p.relative_to(BRAIN).parts):
                continue
            out.append(p)
    return sorted(out)


def init_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    row = con.execute(
        "SELECT value FROM embedding_meta WHERE key = 'schema_version'"
    ).fetchone()
    current = row[0] if row else None
    if current != EMBED_SCHEMA_VERSION:
        con.execute("DROP TABLE IF EXISTS embeddings")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL
        )
        """
    )
    con.execute(
        "INSERT OR REPLACE INTO embedding_meta(key, value) VALUES ('schema_version', ?)",
        (EMBED_SCHEMA_VERSION,),
    )


def needs_embed(con: sqlite3.Connection, path: str, mtime: float) -> bool:
    row = con.execute("SELECT mtime FROM embeddings WHERE path = ?", (path,)).fetchone()
    return row is None or abs(row[0] - mtime) > 1e-3


def make_doc_text(path: Path) -> str:
    body = path.read_text(errors="replace")
    title = path.stem.replace("_", " ").replace("-", " ")
    headings = [
        line.lstrip("# ").strip()
        for line in body.splitlines()
        if line.startswith("# ") or line.startswith("## ")
    ][:3]
    heading_str = " | ".join(headings) if headings else ""
    prefix = f"{_nomic.DOC_PREFIX}Title: {title}"
    if heading_str:
        prefix += f" | Sections: {heading_str}"
    return f"{prefix}\n\n{body[:4000]}"


def prune_deleted(con: sqlite3.Connection, alive_paths: set[str]) -> int:
    stored = {row[0] for row in con.execute("SELECT path FROM embeddings")}
    dead = stored - alive_paths
    if dead:
        con.executemany("DELETE FROM embeddings WHERE path = ?", [(p,) for p in dead])
    return len(dead)


def main() -> int:
    notes = discover_notes()
    alive = {str(p) for p in notes}

    con = sqlite3.connect(DB)
    init_table(con)

    pending: list[tuple[Path, str, float]] = []
    for p in notes:
        abs_path = str(p)
        mtime = p.stat().st_mtime
        if needs_embed(con, abs_path, mtime):
            pending.append((p, abs_path, mtime))

    pruned = prune_deleted(con, alive)
    print(
        f"[scan] {len(notes)} notes, {len(pending)} need embedding, "
        f"{len(notes) - len(pending)} cached, {pruned} pruned",
        flush=True,
    )

    if not pending:
        con.commit()
        con.close()
        return 0

    print("[load] importing model + verifying audit hashes...", flush=True)
    t0 = time.time()
    model, cfg = _nomic.load_trusted_model()
    print(f"[load] ready in {time.time() - t0:.1f}s, dim={model.get_embedding_dimension()}", flush=True)

    texts = [make_doc_text(p) for p, _, _ in pending]
    t0 = time.time()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 10,
        batch_size=8,
    )
    elapsed = time.time() - t0
    per = elapsed / len(texts) * 1000
    print(f"[embed] {len(texts)} docs in {elapsed:.1f}s ({per:.0f}ms/doc)", flush=True)

    rows = [
        (path, mtime, vectors.shape[1], np.asarray(v, dtype=np.float32).tobytes())
        for (_, path, mtime), v in zip(pending, vectors)
    ]
    con.executemany(
        "INSERT OR REPLACE INTO embeddings(path, mtime, dim, vector) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.execute(
        "INSERT OR REPLACE INTO embedding_meta(key, value) VALUES ('model', ?)",
        (f"{_nomic.MODEL_ID}@{cfg['REVISION']}",),
    )
    con.execute(
        "INSERT OR REPLACE INTO embedding_meta(key, value) VALUES ('built_at', ?)",
        (str(int(time.time())),),
    )
    con.commit()

    total = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    con.close()
    print(f"[done] {total} embeddings stored in {DB}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
