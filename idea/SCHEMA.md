# Idea Type Schema

Pre-implementation thinking - capturing problems, solutions, research, and decisions before code. Folder entries by default (multi-file structure). Phased lifecycle from first spark through implementation and closure.

## Storage

Folder entry: `~/.brain/idea/<slug>/`

Files inside:

- `<slug>.md` - main entry (problem, solution, scope, who benefits). Frontmatter on this file. Same name as the folder (Obsidian Folder Notes convention).
- `research.md` - date-stamped research findings (optional, created when needed)
- `decisions.md` - resolved/open decisions (optional)
- `status.md` - current phase + progress checklist + notes (optional but recommended)
- Ad-hoc siblings - any other `<topic>.md` when a working artifact doesn't fit the three canonical buckets (locked schema specs, phase contracts, transcript dumps, etc.). Use a descriptive kebab-case name. Cleanup will not flag these.

Sub-files are siblings, not embedded. Each grows independently.

## Frontmatter (on `<slug>.md`)

```yaml
---
type: idea                                 # required
title: <title>                              # required
created: <YYYY-MM-DD>                       # required
updated: <YYYY-MM-DD>                       # required
tags: [<tag>, ...]                          # optional

# idea-specific
phase: Exploring                            # required
target-repo: <repo>                         # optional - set when In-Progress
---
```

### `phase` values

- `Exploring` - loose idea, maybe some research. No commitment.
- `Decided` - we're going to do this. Approach chosen, scope defined.
- `In-Progress` - handed off to implementation (`/p-craft:pr`, `/p-milestone:milestone`, etc.)
- `Done` - completed. Lessons extracted into lore.
- `Parked` - deprioritized but not dead. Can revive.

## States and Transitions

```
Exploring ─┬─→ Decided ──→ In-Progress ──→ Done
           │       │            │
           └───────┴────────────┴─→ Parked ──→ (revive to Exploring)
```

### Transitions

| Operation | From | To | What happens |
|---|---|---|---|
| **Capture** | - | `Exploring` | Create folder + `<slug>.md` + `status.md`. Discuss problem/solution/scope. Add to INDEX. |
| **Research** | any | (same phase) | Append to `research.md` with date stamp. Bump `updated` on `<slug>.md`. |
| **Record decision** | any | (same phase) | Append to `decisions.md`. Bump `updated`. |
| **Decide** | `Exploring` | `Decided` | Update `phase: Decided` in frontmatter. Status note: approach chosen. Move INDEX entry. |
| **Start** | `Decided` | `In-Progress` | Set `target-repo`, update `phase`. Note implementation approach in `status.md`. Move INDEX. Suggest implementation tool (`/p-craft:pr`, `/p-milestone:milestone`). |
| **Close** | `In-Progress` | `Done` | Update `phase`. Summarize what was done in `status.md`. Ask user about lessons → write to lore. Move INDEX. |
| **Park** | any | `Parked` | Update `phase`. Capture WHY in `status.md` Notes. Move INDEX. |
| **Revive** | `Parked` | `Exploring` | Update `phase`. Note in `status.md` why reviving. Move INDEX. |

### Lifecycle invocations are conversational

The user says "park context-assistant - not the right time" or "let's start knowledge-compasses, target repo is `cli-toolbox`". The LLM:

1. Reads this SCHEMA.md to know the transitions
2. Reads the entry's current state
3. Performs the transition (update frontmatter, edit `status.md`, regenerate INDEX)
4. Asks any clarifying questions noted above (e.g. "what's the target repo?" on Start, "why park?" on Park)
5. Reports what changed

No `/ideas park`, `/ideas close`, etc. skills.

## Sub-file Conventions

### `status.md` format

```markdown
# <Title>
**Phase:** <current>
**Started:** <YYYY-MM-DD>
**Updated:** <YYYY-MM-DD>

## Progress
- [x] <completed step>
- [ ] <next step>

## Notes
<free-form context, why decisions were made, why parked, etc.>
```

### `research.md` format

Date-stamped sections, free-form content:

```markdown
# Research: <Title>

## <YYYY-MM-DD> - <Topic>
<findings, links, comparisons>

## <YYYY-MM-DD> - <Topic>
...
```

### `decisions.md` format

```markdown
# Decisions: <Title>

## Resolved
- **<question>** - <decision> *(reasoning)*

## Open / Deferred
- **<question>** - <why deferred>
```

## Conventions

- **Capture early, structure later.** First version of an idea can be one paragraph in `<slug>.md`. Add `research.md`/`decisions.md` only when content warrants.
- **Date-stamp research entries.** Findings are time-bounded; date stamps preserve the snapshot.
- **Decisions are durable.** Once a decision is resolved, don't silently change it - record a new decision that supersedes the old one.
- **Cross-link to lore liberally.** When research uncovers durable knowledge, link to existing lore or note that lore should be created.

## Relationship with Implementation

Idea tracks the **what and why**. Implementation tools handle the **how**.

- **Decided → In-Progress**: handoff to `/p-craft:pr` (single PR) or `/p-milestone:milestone` (multi-PR).
- Implementation can read `~/.brain/idea/<slug>/` for context.
- Implementation produces its own artifacts in the target repo (`docs/features/...`, etc.) - those don't live in the brain.

## Relationship with Lore

- During research, the LLM may read relevant lore for context.
- On **Close** (Done), extract durable lessons into lore via `/lore remember` (or conversational equivalent).
- Lore never references ideas. If a lore article was born from a closed idea, the `sources:` field can note `[[idea/<slug>]]` for provenance.

## INDEX.md format

Auto-generated, grouped by `phase`:

```markdown
# Idea Index

## Exploring
- [[idea/<slug>]] - <title> - one-line hook

## Decided
- ...

## In-Progress
- ...

## Done
- ...

## Parked
- ...
```

One line per idea, under ~150 characters.
