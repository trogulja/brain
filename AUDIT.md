# AUDIT

Two layers of trust check the brain. They cover different things and have
different audiences.

## Layer 1: SHA-256 audit (deterministic, automated)

The Nomic embedding model uses `trust_remote_code=True` to load custom
architecture code. That code lives in two `.py` files inside the
`nomic-ai/nomic-bert-2048` repository on Hugging Face. We pin a specific
commit revision and record SHA-256 hashes of those two files in
`scripts/nomic-trusted-revision.txt`. Every load goes through
`scripts/_nomic.py`, which verifies the cached files against the pinned
hashes before any custom code executes. A mismatch refuses the load and
exits non-zero.

The audit can be re-run on demand:

```sh
python install.py audit-model
```

The trusted-revision file is never auto-updated. Bumping it requires
human review of the new code (the audit checklist is recorded in the file
itself). Automation here would defeat the security control.

This layer is deterministic and easy to verify: any reader can recompute
the hashes and confirm them against what's pinned. It does not, however,
say anything about the rest of the codebase.

## Layer 2: AI-readable code review (reproducible, manual)

This layer is for non-Python readers, or for anyone who wants a second
opinion that doesn't require reading every line of code. Run the prompt
below in a Claude Code session at the repo root. The model and the
codebase together are the artifact; anyone can re-run and compare.

```text
Audit this codebase for unexpected network behavior.

Context: this is a personal knowledge tool meant to run fully local after
install. The installer downloads pinned Python packages from PyPI (SHA-256
hash-verified) and one Hugging Face model (Nomic embeddings). Once the
model is cached, every subsequent run should be offline. No telemetry, no
version checks, no automatic model updates.

Verify:
1. The only files that initiate network calls are `install.py`,
   `scripts/_nomic.py`, and `scripts/_warmup.py`, and only during install
   or the first model load. Steady-state scripts (`recall.py`,
   `build-embeddings.py`) must not make network calls once the venv and
   HF cache are populated.
2. `trust_remote_code=True` execution is gated by a SHA-256 audit
   against `scripts/nomic-trusted-revision.txt`. Verify the gate fires
   BEFORE any custom remote code runs.
3. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set as soon as
   the weights cache is present.
4. No script reads from or writes to anywhere outside `~/.brain/` and
   `~/.cache/huggingface/` (and `~/.claude/skills/brain/` for the
   installer).

Report findings as: list of files that touch the network, what each call
does, whether it is in-scope (install or first-load) or out-of-scope
(steady state), and any ambiguous or surprising patterns. If you cannot
verify something conclusively from the code alone, say so explicitly.
```

This is not a substitute for the SHA-256 check. The hash audit guarantees
that the `trust_remote_code` files match what was reviewed at audit time;
the AI review checks that the rest of the codebase doesn't surprise you.
Different audiences, different blind spots, both worth running.

## What this audit does not cover

- Vulnerabilities in pinned dependencies. We pin and hash-lock so the
  bytes you install match what was last reviewed, not so they're free of
  CVEs. Bumping a top-level pin is the human's call.
- The Nomic model weights. The audit covers the architecture code that
  HF executes via `trust_remote_code`, not the trained weights. The
  weights repo (`nomic-ai/nomic-embed-text-v1.5`) is loaded with
  `local_files_only=True` once cached, but its tensors are trusted on
  faith.
- Anything outside this repo. Personal content in `~/.brain/lore/`,
  `~/.brain/idea/`, etc. is yours to manage.
