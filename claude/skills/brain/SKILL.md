---
name: brain
description: Personal unified knowledge store at ~/.brain/. Use when the user mentions remembering, recalling, capturing, or referencing personal knowledge - including lore (durable knowledge), idea (pre-implementation thinking), job (in-flight work units), followup (open commitments / things owed), research-link (URLs to read later), and other typed entries. Triggers on phrases like "remember this", "what do we know about", "capture this idea", "park this", "save this link", "check our notes", "what's in my brain", "I owe X", "track this commitment", "what am I on the hook for".
argument-hint: remember | cleanup
---

# Brain

A personal unified knowledge store at `~/.brain/`. Replaces separate `~/.lore/` and `~/.ideas/` folders. Single root, typed entries, conversational lifecycle.

## Setup

- **Top-level schema:** `~/.brain/SCHEMA.md` - common conventions (root, layout, slugs, wikilinks, common frontmatter, attachments, lifecycle model). Read this first when working with the brain.
- **Per-type schemas:** `~/.brain/<type>/SCHEMA.md` - type-specific frontmatter, lifecycle states/transitions, conventions. Read the relevant one when working with a specific type.
- **Per-type INDEX:** `~/.brain/<type>/INDEX.md` - auto-generated entry list grouped by status/phase.

## Types

### Live

- **`lore`** - atomic durable knowledge (patterns, conventions, decisions, lessons, anti-patterns, references). File entries.
- **`idea`** - pre-implementation thinking (problem, solution, research, decisions, status). Folder entries with siblings. Phased lifecycle.
- **`job`** - in-flight (and recently-finished) work units. Folder entries with siblings. Collapses earlier reserved `active-work` and `job-artifact` (decided 2026-04-27).
- **`followup`** - open commitments / things owed (cross-cutting "what am I on the hook for"). Single-file by default. Status lifecycle (open/done/dropped). No due dates by design - time-bound items migrate to Apple Reminders or calendar.
- **`research-link`** - URLs to research later. File entries. Status lifecycle.

### Reserved

Type names locked, schema design deferred: `compass`, `digest`.

## Lifecycle Model: Schema-Declared, LLM-Executed

There are no per-type CRUD skills. Lifecycle operations are conversational:

1. User says "park context-assistant - not the right time"
2. Read `~/.brain/idea/SCHEMA.md` to learn how to park an idea
3. Read the entry's current state
4. Perform file updates following the schema's transition recipe
5. Ask any clarifying questions noted in the schema (e.g. "why parking?")
6. Regenerate the type's INDEX.md via `node ~/.brain/scripts/regenerate_indices.py --apply`

This applies to all types. Read the schema, follow the convention, execute conversationally.

## Subcommands

### `/brain remember [description]`

Add knowledge to lore. With argument, compile directly. Without argument, review the conversation and extract honestly. **For full workflow guidance, read `references/remember.md`.**

### `/brain cleanup`

Run a structural health check across all types - find stale entries, broken wikilinks, contradictions, gaps. Reports findings; never modifies without user approval. **For full workflow guidance, read `references/cleanup.md`.**

### L0 curation (CLAUDE.md)

When the user asks to add, update, audit, or remove a rule in `~/.claude/CLAUDE.md`, follow the workflow in `references/curate-l0.md`. Rules can have backing lore in `category: behavior`; provenance is computed via BM25 at audit time, not stored. CLAUDE.md stays clean (no wikilinks, no metadata).

Audit script: `python3 ~/.brain/scripts/audit-l0.py` - token count, BM25 provenance candidates per rule, merge candidates, stale lore.

## Common Operations (conversational)

### Recalling something

User: *"What do we know about filter operations?"*

Search `~/.brain/` (grep + INDEX), synthesize from relevant entries, cite slugs. No need to save the answer - recall is ephemeral by design.

### Capturing an idea

User: *"I want to capture an idea for X."*

Read `~/.brain/idea/SCHEMA.md`, slug it, create `~/.brain/idea/<slug>/<slug>.md` + `status.md` (phase: Exploring), discuss problem/solution/scope.

### Saving a URL

User: *"Save this link: https://..."*

Read `~/.brain/research-link/SCHEMA.md`, slug it, create `~/.brain/research-link/<slug>.md` with `status: inbox`.

### Capturing a followup / commitment

User: *"I owe Car a workshop"* / *"Track that I need to ping Bruno"* / *"What am I on the hook for?"*

For capture: read `~/.brain/followup/SCHEMA.md`, slug it, create `~/.brain/followup/<slug>.md` with `status: open`. Link via `related: [[idea/<slug>]]` if it ties to an existing idea/job. If the commitment is really an internal step of an ongoing idea/job, leave it as a checkbox in that entry's `status.md` instead - followup is for cross-cutting items.

For the "on the hook for" view: open `~/.brain/followup/INDEX.md` (Open section).

If the followup becomes time-bound, migrate to Apple Reminders or calendar and either close the followup or leave a note pointing where it lives.

### Updating phase

User: *"Let's start knowledge-compasses, target repo is cli-toolbox."*

Read `~/.brain/idea/SCHEMA.md`, find the entry, transition Decided → In-Progress, set `target-repo`, update `status.md`, regenerate INDEX.

### Cross-references

When you see `[[<type>/<slug>]]` in any entry's body, follow it. The wikilink resolves to either `~/.brain/<type>/<slug>.md` (file entry) or `~/.brain/<type>/<slug>/<slug>.md` (folder entry - folder note). The form is uniform across both.

## Adding New Types

To add a new type:

1. Create `~/.brain/<type>/` directory
2. Write `~/.brain/<type>/SCHEMA.md` defining frontmatter, lifecycle, conventions
3. The type is now usable. Run `regenerate_indices.py` to seed the INDEX.

No code changes needed. Types are data.

## Important Conventions

- **Wikilinks are explicit and uniform**: `[[<type>/<slug>]]` for both file and folder entries. Resolver finds `<slug>.md` or `<slug>/<slug>.md`. Never short form.
- **Slugs are kebab-case ASCII**, lowercase, hyphenated.
- **Type-grouped layout**: entries live under `~/.brain/<type>/`, never at the root.
- **Per-instance file vs folder**: default to file; promote to folder when sub-artifacts emerge.
- **No global INDEX.md** - per-type INDEXes only.
- **No calendar-based staleness on lore** - review-driven, not time-driven.
- **Tags discipline**: flat global namespace, kebab-case, used sparingly. Don't tag with the type itself. Avoid synonyms.

## Scripts

- `~/.brain/scripts/recall.py` - hybrid (BM25 + semantic) search over the brain. Default `--mode hybrid` merges keyword and embedding ranks via RRF (k=60); `--mode bm25` skips the model load for instant keyword-only queries; `--mode semantic` is embedding-only. Logs to `recall_log` for analytics. First hybrid/semantic call costs ~5s for cold model load.
- `~/.brain/scripts/build-embeddings.py` - generates/refreshes semantic embeddings for all entries. **Run after creating or editing notes** if you want them surfaced in hybrid/semantic recall - embeddings are not auto-built. Incremental: only re-embeds files whose mtime changed. Stores 768-dim float32 vectors in `search.db` alongside the FTS5 index.
- `~/.brain/scripts/_nomic.py` - shared loader for `nomic-ai/nomic-embed-text-v1.5`. Pins `code_revision`, verifies SHA-256 of cached `trust_remote_code` files against `nomic-trusted-revision.txt` before each load, forces fully offline mode (`HF_HUB_OFFLINE=1` + `local_files_only=True`) once cache is populated.
- `~/.brain/scripts/nomic-trusted-revision.txt` - audit trail for the Nomic remote-code files: pinned commit hash, expected SHA-256s, audit date and auditor. Bumping the revision requires re-auditing the new code; the loader fails loud on hash mismatch. Background: `lore/audit-remote-code-execution.md`.
- `~/.brain/scripts/log-read.py` - PostToolUse hook on Read tool. Logs brain Reads to `read_log`.
- `~/.brain/scripts/analyze.py` - aggregate analytics over recall + read logs.
- `~/.brain/scripts/regenerate_indices.py` - regenerate per-type INDEX.md from frontmatter. Run after entries are added/changed/transitioned.

## Audit-mode reads (skip-log sentinel)

When a workflow Reads brain entries for **inspection** rather than **use** (cleanup audits, dedupe checks during remember, analytics-driven content review), those reads should not pollute `read_log` - otherwise inspected entries look popular and quality signals get masked.

The convention: touch `~/.brain/.cache/skip-log` before the first audit Read, remove it at the end:

```bash
mkdir -p ~/.brain/.cache && touch ~/.brain/.cache/skip-log
# ... audit Reads happen here ...
rm -f ~/.brain/.cache/skip-log
```

The `log-read.py` hook checks for this marker and bails without logging when present. Marker auto-stales after 30 min, so a crashed workflow doesn't permanently disable logging - but always clean up explicitly.

Use this in any new skill that walks brain entries for meta-purposes.

**Limitation:** the sentinel is global. While set, *all* sessions' reads are suppressed, not just the one running the audit. Don't run audit-mode workflows concurrently with another Claude session that's doing real work in `~/.brain/`, or you'll silently under-count that session's reads. Bounded to 30 min by auto-stale.

## Version control

`~/.brain/` is a git repository. Any operation that **writes or changes** entries (remember, capture, save link, phase transition, cleanup edits) ends with a commit. **For full convention, read `references/version-control.md`.** Read-only operations (recall, search) skip this entirely.
