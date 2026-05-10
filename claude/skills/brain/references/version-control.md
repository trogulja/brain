# Version Control

`~/.brain/` is a git repository. Read this file when you've **written or changed** entries (remember, capture idea, save link, phase transition, cleanup edits) and need to commit.

Recall and other read-only operations don't touch git - skip this file.

## Cadence

One commit per logical operation, not per file. If a single `/brain remember` produces three lore entries plus a raw file, that's **one** commit. If a cleanup session touches twelve entries, that's still **one** commit. Group by user intent, not file count.

## Mechanics

Before committing, run `~/.brain/scripts/build-embeddings.py` if any entries were created or edited. It's incremental (only re-embeds changed files) and ensures the new content is searchable via hybrid/semantic recall immediately. Skip only if the operation was metadata-only (e.g. INDEX regen with no entry changes). Embeddings live in `search.db` which is gitignored - the script writes locally, no diff impact.

```bash
~/.brain/scripts/build-embeddings.py
cd ~/.brain && git add -A && git commit -m "<message>"
```

Stage with `-A` so renames/deletions are picked up. `INDEX.md` files are gitignored (auto-regenerated), so they won't appear in the diff.

## Message style

Short imperative, prefixed with the operation. Examples:

- `remember: 3 lore entries from brain-design session`
- `idea: capture knowledge-compasses (phase: Exploring)`
- `idea: park context-assistant - not the right time`
- `link: save Karpathy LLM Wiki gist`
- `cleanup: fix broken wikilinks in lore/`
- `lore: evolve flag-cleanup-checklist with TS-locally lesson`

Body optional - only add it when the *why* isn't obvious from the message and the diff (e.g. a non-trivial schema change or a destructive cleanup).

## Don't ask

Commits are local, private, and reversible. Just do it as the final step of the operation. No "should I commit?" prompts.
