"""Shared loader for nomic-ai/nomic-embed-text-v1.5 with audit-trail enforcement.

The model uses trust_remote_code=True (custom architecture). Before loading,
we verify that the cached custom code matches the SHA-256 hashes recorded in
nomic-trusted-revision.txt. The code revision is pinned via code_revision so
HF will not silently pull a newer version.

Imported lazily: `import _nomic` is fast; `load_trusted_model()` does the
heavy work and is the only reason to depend on torch / sentence_transformers.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

BRAIN = Path(__file__).resolve().parent.parent
REVISION_FILE = BRAIN / "scripts" / "nomic-trusted-revision.txt"
MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
CODE_REPO_ID = "nomic-ai/nomic-bert-2048"
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

REMOTE_CODE_FILES: tuple[str, ...] = (
    "configuration_hf_nomic_bert.py",
    "modeling_hf_nomic_bert.py",
)


@dataclass(frozen=True)
class HashMismatch:
    """One mismatched file in the trust_remote_code audit."""

    fname: str
    path: Path
    expected: str
    actual: str  # full hash, ``"<missing>"`` if file absent, ``"<no expected>"`` if config gap.


def read_revision_config(path: Path = REVISION_FILE) -> dict[str, str]:
    cfg: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        cfg[key.strip()] = val.strip()
    return cfg


def compute_cache_dir(cfg: dict[str, str]) -> Path:
    revision = cfg["REVISION"]
    return (
        Path.home()
        / ".cache/huggingface/hub"
        / f"models--{CODE_REPO_ID.replace('/', '--')}"
        / "snapshots"
        / revision
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_remote_code_hashes(
    cfg: dict[str, str], cache_dir: Path
) -> list[HashMismatch]:
    """Pure hash check: returns mismatches (empty list = all OK)."""
    mismatches: list[HashMismatch] = []
    for fname in REMOTE_CODE_FILES:
        expected = cfg.get(f"SHA256_{fname}")
        path = cache_dir / fname
        if not expected:
            mismatches.append(
                HashMismatch(fname, path, expected="<no expected>", actual="<unknown>")
            )
            continue
        if not path.exists():
            mismatches.append(
                HashMismatch(fname, path, expected=expected, actual="<missing>")
            )
            continue
        actual = _sha256(path)
        if actual != expected:
            mismatches.append(HashMismatch(fname, path, expected=expected, actual=actual))
    return mismatches


def verify_remote_code(cfg: dict[str, str], *, quiet: bool = False) -> Path:
    """Audit-and-load helper used by build-embeddings.py and recall.py.

    Downloads the pinned revision if absent, then checks hashes. Exits ``2`` on
    mismatch. ``install.py audit-model`` uses the lower-level primitives
    (``compute_cache_dir`` + ``check_remote_code_hashes``) directly so it can
    refuse to download and produce its own richer error message.
    """
    revision = cfg["REVISION"]
    cache_dir = compute_cache_dir(cfg)
    if not cache_dir.exists():
        if not quiet:
            print(f"[verify] downloading pinned revision {revision[:12]}...", flush=True)
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=CODE_REPO_ID, revision=revision, allow_patterns=["*.py"])
        if not cache_dir.exists():
            raise RuntimeError(f"snapshot_download did not populate {cache_dir}")

    mismatches = check_remote_code_hashes(cfg, cache_dir)
    if mismatches:
        print("[verify] HASH MISMATCH - refusing to load model:", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m.fname}: expected {m.expected[:12]}..., got {m.actual[:12]}...", file=sys.stderr)
        print(
            "\nCached remote code does not match the audited version. "
            "Re-audit before continuing - see nomic-trusted-revision.txt.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not quiet:
        print(
            f"[verify] revision {revision[:12]} hashes OK "
            f"(audited {cfg.get('AUDITED_AT', '?')} by {cfg.get('AUDITED_BY', '?')})",
            flush=True,
        )
    return cache_dir


def load_trusted_model(*, device: str = "mps", quiet: bool = False):
    """Verify hashes, then load SentenceTransformer with code_revision pinned.

    Runs fully offline once the model + custom code are cached. The first
    call (cold cache) is allowed to hit the HF Hub to download both, after
    which we lock to local_files_only=True for every subsequent load.
    """
    cfg = read_revision_config()
    cache_dir = verify_remote_code(cfg, quiet=quiet)
    weights_cached = _weights_in_cache()

    # Once both code + weights are present, force fully offline operation:
    # no HEAD requests, no ETag checks, no telemetry leak.
    import os

    if weights_cached and cache_dir.exists():
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        MODEL_ID,
        trust_remote_code=True,
        device=device,
        local_files_only=weights_cached,
        model_kwargs={"code_revision": cfg["REVISION"], "local_files_only": weights_cached},
        config_kwargs={"code_revision": cfg["REVISION"], "local_files_only": weights_cached},
    )
    return model, cfg


def _weights_in_cache() -> bool:
    """Check whether the model weights repo has at least one local snapshot."""
    weights_dir = (
        Path.home()
        / ".cache/huggingface/hub"
        / f"models--{MODEL_ID.replace('/', '--')}"
        / "snapshots"
    )
    if not weights_dir.exists():
        return False
    for snap in weights_dir.iterdir():
        if (snap / "config.json").exists():
            return True
    return False
