# brain

A note-taking system I keep coming back to. Typed entries, searchable by what
you wrote and by what you meant, all local. Obsidian renders it like a person
would. A Claude Code skill lets agents recall what you've decided before.

This repo is the architecture, not the content. Clone it, run the installer,
get a working brain on a fresh machine. Your actual notes stay on your
machine and never enter the public repo.

## What you're installing

| Mode | Size | What lands on disk |
| --- | --- | --- |
| `python install.py` | under 1 MB | schemas, scripts, Claude skill, Obsidian config. BM25 keyword recall works. |
| `python install.py --with-semantic` | ~1.4 GB | The above plus a Python venv (~873 MB) and the Nomic embedding model (~523 MB) for semantic recall. |

The semantic install is opt-in. Skip it and recall still works in keyword
mode. Add it later by re-running with the flag.

## Prerequisites

- macOS on Apple Silicon. Linux likely works, no one tested it. No Windows.
- Python 3.10 or newer (developed against 3.14).
- `git` on PATH.
- About 1.4 GB of free disk if you go semantic.

## Install

### Default (BM25 only)

```sh
git clone https://github.com/trogulja/brain
cd brain
python install.py
```

This copies schemas, scripts, the Claude skill, and `.obsidian/` config into
`~/.brain/` and `~/.claude/skills/brain/`. Re-running is safe (idempotent) and
never touches your personal content (`lore/`, `idea/`, `research-link/`,
`job/`, `followup/`, `data/`).

### With semantic recall

```sh
python install.py --with-semantic
```

This adds: a Python venv at `~/.brain/.venv`, hash-pinned dependencies from
`requirements.txt` (pip refuses to install if a download doesn't match the
recorded SHA-256), an audit of the Nomic `trust_remote_code` files against
`scripts/nomic-trusted-revision.txt`, and a one-shot warm-up that pre-fetches
the model weights so your first `recall.py` call isn't a surprise download.

First run takes a few minutes (most of it is downloading wheels and the model).
Subsequent re-runs are fast.

### What about the cloned source?

After install, brain runs entirely out of `~/.brain/` and
`~/.claude/skills/brain/`. The cloned source is not read again at runtime.

Keep the clone if you want any of these workflows:

- `python install.py update` to pull and re-install when there's a new version
- `python install.py status` / `promote` to track drift between your live brain
  and the source, and push live experiments back to the source for committing
- `python install.py audit-model` to re-verify the Nomic
  `trust_remote_code` hashes against the pinned values in source
- Re-running `--with-semantic` after wiping `~/.brain/.venv`

If you don't want any of those, `rm -rf` the clone after install. Recall,
embeddings, and the Claude skill keep working. Re-clone later when you want
to update.

## Subcommands

| Command | What it does |
| --- | --- |
| `python install.py` | Default install. Copies architecture into live. Idempotent. |
| `python install.py --with-semantic` | Above plus venv, deps, audit, weight pre-fetch. |
| `python install.py audit-model` | Verify cached Nomic remote-code files against pinned SHA-256 hashes. Exits non-zero on mismatch with the re-audit recipe inline. Never modifies the trusted-revision file. |
| `python install.py status` | Drift report between repo and live. Classifies each managed file as `in-sync`, `repo-ahead`, `live-ahead`, or `both-changed`. Read-only. `--json` for machine output. |
| `python install.py promote` | Live to repo direction. Walks each drifted file, shows the diff, asks `y/n/q`. Copies confirmed files into the repo working tree. Never commits or pushes. |
| `python install.py update` | `git pull` then refresh the live install. Refuses on dirty working tree. Halts with a re-audit recipe if the pull bumps the Nomic trusted-revision file (the trusted-revision file is never auto-trusted). |

## Adding the Claude Code skill

The installer copied the skill into `~/.claude/skills/brain/`, but Claude
won't pick up `recall.py` unless your global config tells it to. Add this
section to `~/.claude/CLAUDE.md`:

```markdown
## Brain (Personal Knowledge Base)

- Brain lives at `~/.brain/`: a unified typed store. Types include lore
  (durable knowledge), idea (pre-implementation thinking), job (in-flight
  work units), followup (open commitments / things owed), research-link
  (URLs to read later). See the `/brain` skill for the authoritative list
  and per-type schemas.
- **Use `recall` to search the brain.** When the conversation touches a
  topic that may have prior context (debugging a recurring issue, an
  established convention, an ongoing idea, a prior decision), call
  `~/.brain/scripts/recall.py "<query>"` *early*, before guessing or
  leaning on training data. Default mode is **hybrid** (BM25 + local
  semantic embeddings via Nomic, RRF-merged), which surfaces matches even
  when the user's wording differs from what's stored. First call costs
  ~5s (model load); use `--mode bm25` for instant keyword-only when
  wording will match exactly. Read the entries it surfaces if relevant;
  ignore if not. Use it liberally: recall is cheap, missing context is
  expensive.
- **Embeddings are built separately.** `recall` searches whatever
  embeddings exist; new/edited notes only show up in semantic/hybrid
  results after `~/.brain/scripts/build-embeddings.py` runs (incremental,
  only re-embeds changed files). Run it after `/brain remember` or any
  note edit if you want the new content semantically searchable in the
  next recall.
- When you notice knowledge worth preserving during work (debugging
  insights, conventions, gotchas, decisions with non-obvious reasoning),
  suggest: "This seems worth remembering. Want me to capture it in
  `/brain`?"
```

The installer never touches your `~/.claude/CLAUDE.md`. You add the snippet
yourself, once.

## Drift between repo and live

The install copies files from the repo into your live `~/.brain/`. Nothing
links them after that, so you can edit the live versions freely without
polluting public history. When a live experiment is worth keeping, walk it
back into the repo:

```sh
python install.py status     # see what's drifted
python install.py promote    # walk drifted files, accept or skip each
git diff && git add -p && git commit && git push
```

Promote never auto-commits. The repo working tree is the only thing it
modifies, and you review before committing.

## Troubleshooting

**`audit-model` reports a hash mismatch.** Something changed in the cached
Nomic files. Either the cache got corrupted, or you bumped the pinned
revision and haven't completed the re-audit. The error message includes the
re-audit recipe. The trusted-revision file is never auto-updated; this is by
design.

**`recall.py` exits with "missing venv".** You ran it without the semantic
venv installed. Either re-run `python install.py --with-semantic`, or pass
`--mode bm25` to skip the model load entirely.

**Pip refuses to install with "hash mismatch".** A pinned wheel either
isn't available for your platform / Python version, or one of the recorded
hashes is stale. The most common cause is a Python version mismatch. The
pins in `requirements.txt` are tied to specific cpython ABIs (e.g. cp314).
If you're on a different Python version, regenerate `requirements.txt` from
`requirements.in` (`pip-compile --generate-hashes --allow-unsafe
--strip-extras`) and audit the new hashes before installing.

**Python can't find `_nomic`.** That import only resolves when the script
runs from `~/.brain/scripts/` (the directory is on `sys.path`). If you
relocated the scripts, the venv won't find the helper module.

**Custom venv location.** Set `BRAIN_VENV` to either a venv root or a
python binary path; `recall.py` and `build-embeddings.py` honor it ahead
of the default `~/.brain/.venv`.

## Audit

Two complementary checks live in this repo. The deterministic SHA-256 audit
(`audit-model` subcommand) covers the `trust_remote_code=True` execution
path. A Claude Code prompt for an LLM-readable second opinion lives in
[AUDIT.md](AUDIT.md).

## Out of scope

- Cross-platform support beyond macOS on Apple Silicon.
- A Claude plugin wrapper or hybrid distribution. Standalone repo first.
- Migrating existing personal content. Assume fresh install or layered
  install over an existing brain.
- Auto-installing system prerequisites. The installer fails clearly if
  Python or git is missing.
