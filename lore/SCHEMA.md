# Lore Type Schema

Atomic, durable knowledge compiled from work experience. One concept per entry. Default: file entries (`~/.brain/lore/<slug>.md`). Promote to folder if an entry grows attachments or sub-notes.

## Frontmatter

```yaml
---
type: lore                                 # required
title: <title>                              # required
created: <YYYY-MM-DD>                       # required
updated: <YYYY-MM-DD>                       # required
tags: [<tag>, ...]                          # optional

# lore-specific
category: pattern | convention | decision | lesson | anti-pattern | reference | behavior
status: recommended | deprecated | experimental | avoid   # optional
repos: [<repo-name>, ...]                   # optional - relevant repos
sources: [<wikilink-or-url>, ...]           # optional - provenance
last-reviewed: <YYYY-MM-DD>                 # optional - bookkeeping for when you last re-read and verified
---
```

### `category` values

- `pattern` - a code pattern or technique. Includes when to use it AND when NOT.
- `convention` - a team/repo convention or rule. Includes the "why."
- `decision` - a specific decision we made, with context and reasoning.
- `lesson` - something we learned the hard way. Includes what went wrong and how to avoid it.
- `anti-pattern` - a pattern to avoid. Includes what to do instead.
- `reference` - a factual reference (command, config, API). Just the facts.
- `behavior` - a personal preference or behavioral rule for Claude - "how I want you to behave". Litmus: would this be true for a different user? If no → `behavior`. If yes → one of the above. These entries are L0 candidates: they back rules in `~/.claude/CLAUDE.md`. Provenance is computed via BM25 at audit time, not stored.

### `status` values

Include when applicable:

- `recommended` - this is the way. Use it.
- `deprecated` - still in code but migrating away.
- `experimental` - trying it. Not yet proven.
- `avoid` - don't use. See article for what to use instead.

### `sources`

Provenance - where this knowledge came from. Two forms:

- Wikilinks to other brain entries: `[[idea/context-assistant]]`, `[[research-link/meta-tribal-knowledge]]`
- External URLs: `https://...`

Source pointers should be stable - they're what you re-read when reviewing the lore. They make manual review possible; they're not an automated drift signal. Raw files in `~/.brain/lore/raw/` are append-only by convention, so source-file mtime drift is not a meaningful staleness check anyway.

## States and Transitions

Lore doesn't have a phase-style lifecycle. Implicit states based on `status` field:

- **(no status)** - current; assumed correct
- `recommended` - explicitly endorsed
- `experimental` - provisionally true
- `deprecated` - still relevant historically; superseded
- `avoid` - known wrong; kept as warning

### Transitions

| Operation | What happens |
|---|---|
| **Create** | Write entry with `created`, `updated`, `last-reviewed` set to today. Add to INDEX. |
| **Update content** | Edit body, bump `updated`, add new sources if the update came from a new source. |
| **Review** | Re-read for staleness. If still correct, bump `last-reviewed`. If stale, edit or set `status: deprecated`. |
| **Mark stale** | Set `status: deprecated` or `status: avoid`. Add note explaining why. Don't delete. |
| **Delete** | Rare. Only when entry was wrong from the start. Prefer `status: avoid` over deletion. |

## Conventions

- **One concept per note.** If an entry covers two distinct things, split it.
- **Title is descriptive, not generic.** "Frontend filter operations have per-type API semantics" not "Frontend filters."
- **Body is concise.** Details that don't fit the principle go in `sources` (linked) or get spun off into a separate entry.
- **Cross-link liberally** to other lore, ideas, research-links. `[[type/slug]]` form.
- **No calendar-based staleness.** Lore doesn't expire on a schedule. Review-driven, not time-driven.

## Body Structure (recommended)

```markdown
# <Title>

<Brief description - 1-2 sentences capturing the principle.>

## Context

<When this applies. What problem it addresses.>

## Detail

<The actual knowledge. Code snippets, examples, gotchas.>

## Related

- [[lore/other-article]] - how it relates
- [[idea/some-idea]] - the idea this came from
```

The "Detail" section is type-flexible - anti-patterns include "what to do instead", patterns include "when not to use it", references are just facts.

## Promotion to folder entry

Lore is almost always file-form. Promotion to `<slug>/<slug>.md` (folder note) is appropriate when:

- The entry needs attached images/diagrams
- The entry has sub-artifacts (e.g. example code, data files) that don't fit inline

Promote conservatively - most lore should stay file-form.

## INDEX.md format

Auto-generated, grouped by `category`:

```markdown
# Lore Index

## Patterns
- [[lore/<slug>]] - <title>

## Conventions
- ...

## Lessons
- ...

## Anti-patterns
- ...

## Decisions
- ...

## References
- ...
```

Within each group, sorted alphabetically by slug.
