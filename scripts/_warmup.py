"""Warm up the Nomic embedding pipeline at install time.

Invoked by ``install.py --with-semantic`` after deps are installed and the
brain target's ``scripts/`` is in place. Runs inside the brain venv so it has
access to torch / sentence_transformers.

Effects:
    1. Audits the cached Nomic ``trust_remote_code`` files against pinned hashes
       (via ``_nomic.load_trusted_model``).
    2. Pre-fetches the ~1.4 GB model weights (via ``SentenceTransformer`` load).
    3. Validates the full pipeline end-to-end with a one-shot encode.

This does NOT keep the model resident. The process exits and weights unload.
The point is to surface install errors at install time and avoid surprising
the user with a 1.4 GB download on first ``recall.py`` call.
"""
from __future__ import annotations

import sys

import _nomic


def main() -> int:
    print(
        "[warmup] downloading model weights (~1.4 GB; pre-fetch so first recall isn't a surprise)...",
        flush=True,
    )
    model, _ = _nomic.load_trusted_model(quiet=False)
    print("[warmup] one-shot encode of test string...", flush=True)
    emb = model.encode("warmup", prompt=_nomic.QUERY_PREFIX, show_progress_bar=False)
    dim = emb.shape[-1] if hasattr(emb, "shape") else len(emb)
    print(
        f"[warmup] OK - pipeline validated end-to-end (embedding dim {dim}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
