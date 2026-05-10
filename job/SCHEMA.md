# Job Type Schema

In-flight (and recently-finished) work units. A `job` is a personal workspace for one chunk of work: typically what `/p-craft:pr` produces, or a smaller ad-hoc task. Folder entries by default. Lifecycle is short: `active` → `done` → `archived`.

Collapses earlier reserved types `active-work` (Stjepan's `task.md` pattern) and `job-artifact` (work-unit deliverables) into one. Decided 2026-04-27.

## Storage

Folder entry: `~/.brain/job/<slug>/`

Files inside:

- `<slug>.md`: **recipe** (folder note, frontmatter on this file). Stjepan's `task.md` pattern: what I'm doing, where I left off, next step. Same name as the folder (Obsidian Folder Notes convention).
- `status.md`: phase tracker + progress checkboxes + free-form notes. Workflow-driven (`/job` writes 7-phase progression; lightweight jobs may be 2-phase).
- *(any of)* `research.md`, `prd.md`, `qa-plan.md`, `plan/` (folder with `INDEX.md` + chunks), plus free-form additions like `decisions.md`: artifact siblings produced by the workflow. **Schema does not enumerate or restrict siblings.** Whatever the workflow needs lives here. The recipe `<slug>.md` doubles as the idea/folder note; there is no separate `idea.md`.
- `attachments/`: screenshots, diagrams, eval outputs, draft PR descriptions, etc.

The artifact set is **plug-in**, not fixed. Different workflows write different siblings; the schema only locks the recipe + status + frontmatter. See "Relationship with Implementation Skills" below for what each workflow writes.

## Frontmatter (on `<slug>.md`)

```yaml
---
type: job                                  # required
title: <title>                              # required
created: <YYYY-MM-DD>                       # required
updated: <YYYY-MM-DD>                       # required
tags: [<tag>, ...]                          # optional

# job-specific
status: active                              # required: active | done | archived
target-repo: <repo>                         # optional: set if the job targets a specific codebase
related-idea: [[idea/<slug>]]               # optional: wikilink to originating idea, if any
---
```

### `status` values

- `active`: work is in flight. Recipe and status reflect current progress.
- `done`: work completed (PR merged, milestone closed, task delivered). Lessons not yet extracted. Stays in-place at `~/.brain/job/<slug>/` and remains discoverable through recall.
- `archived`: followup happened (durable knowledge extracted to lore, anything else worth keeping pulled out). Folder moves to `~/.brain/job/.archive/<slug>/`.

**Phase** (e.g. p-craft's Idea/Research/Design/Plan/Execute/QA) is **not** a frontmatter field: it's tracked free-form in `status.md` because workflows differ.

## States and Transitions

```
active ──→ done ──→ archived
   │         │
   └─────────┴─→ (paused: stays active with note in status.md, no separate state)
```

### Transitions

| Operation | From | To | What happens |
|---|---|---|---|
| **Start** | n/a | `active` | Create folder + `<slug>.md` (recipe) + `status.md`. Capture goal, scope, target repo. Add to INDEX. |
| **Update** | `active` | (same) | Edit recipe and/or `status.md` to reflect new state. Bump `updated` on `<slug>.md`. Add/edit artifact siblings as workflow progresses. |
| **Complete** | `active` | `done` | Update `status: done` in frontmatter. Note completion summary in `status.md` (what shipped, where it lives, links to PR/merge). Stays at `~/.brain/job/<slug>/`. Move INDEX entry to Done section. |
| **Followup** | `done` | (still `done`) | Conversational pass: extract durable lessons to `lore` (via `/brain remember` or equivalent), pull anything else worth keeping. After this pass, **archive** is the next step. |
| **Archive** | `done` | `archived` | Update `status: archived`. Move folder: `~/.brain/job/<slug>/` → `~/.brain/job/.archive/<slug>/`. Update INDEX. Wikilinks `[[job/<slug>]]` should still resolve via the archive path (tooling-side concern). |
| **Reopen** | `done` \| `archived` | `active` | Update `status: active`. If archived, move folder back from `.archive/`. Note in `status.md` why reopening. Update INDEX. |

### Lifecycle invocations are conversational

The user says "complete the user-export job" or "archive lazy-output-tool: I've extracted everything worth keeping." The LLM:

1. Reads this SCHEMA.md to know transitions
2. Reads the entry's current state
3. Performs the transition (frontmatter, `status.md` summary, possible folder move, INDEX regen)
4. Asks any clarifying questions noted above (e.g. "anything in this job worth pulling into lore before archive?" on Followup)
5. Reports what changed

No `/job complete`, `/job archive`, etc. skills.

## Sub-file Conventions

### `<slug>.md` (recipe / folder note) format

```markdown
---
type: job
title: <title>
status: active
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
target-repo: <repo>           # optional
---
# <Title>

## Goal
What I'm doing and why. 1-3 sentences.

## Scope
- In: <what's in>
- Out: <what's explicitly out>

## Where I left off
Last meaningful state: enough for a fresh session to pick up without rereading the whole folder.

## Next step
The single next concrete action.

## Artifacts
- [[job/<slug>/research]]: short hook (if exists)
- [[job/<slug>/prd]]: short hook (if exists)
- [[job/<slug>/plan]]: short hook (if exists, points to plan/INDEX.md)
- [[job/<slug>/qa-plan]]: short hook (if exists)
- [[job/<slug>/decisions]]: short hook (if exists, free-form)
- [[job/<slug>/status]]: phase tracker

## Links
- Idea: [[idea/<slug>]] (if applicable)
- PR: <url>
- Task: <url>
```

### `status.md` format

```markdown
# <Title>
**Status:** active | done | archived
**Started:** <YYYY-MM-DD>
**Updated:** <YYYY-MM-DD>

## Phase
<workflow-specific. For `/job`: Idea | Research | Prototype | PRD | Plan | Implementation | QA | Done. For `/p-craft:pr`: Idea | Research | Prototype | Design | Plan | Execute | QA | Done.>

## Progress
- [x] <completed step>
- [ ] <next step>

## Notes
<free-form context, blockers, decisions to revisit, why paused, etc.>
```

### Artifact siblings

No fixed format. Each implementation skill writes its own shapes:

- `/job` writes `research.md`, `prd.md`, `plan/INDEX.md` + chunks, `qa-plan.md`. Recipe `<slug>.md` doubles as the idea note.
- `/p-craft:pr` (team-shared) writes `idea.md`, `research.md`, `design.md`, `plan.md`, `decisions.md`.

Both are workflow conventions, not schema requirements. Schema only requires that:

- Each sibling is a markdown file (or folder with markdown inside)
- Wikilinks `[[job/<slug>/<sibling>]]` resolve

Free-form additions (e.g. `decisions.md` outside the `/p-craft:pr` flow, or `notes.md`, etc.) are allowed at any time.

## Conventions

- **Recipe is the load-bearing file.** `<slug>.md` should always be enough for a fresh session to know what's going on. If it's getting stale, update it before adding new artifacts.
- **Don't pre-create empty siblings.** Add `prd.md`, `research.md`, etc. only when you actually have content.
- **`status.md` is the workflow log.** Phase progression, progress checkboxes, blockers, decisions to revisit. Bumps on every meaningful update.
- **One job per concrete chunk of work.** Roughly: one PR, or one tight feature spanning a few coordinated PRs. Larger scope → use `idea` (planning) or milestone tracking.
- **Cross-link to idea liberally.** If a job implements a decided idea, `<slug>.md` frontmatter should set `related-idea: [[idea/<slug>]]`.

## Relationship with Idea

Idea tracks the **what and why** before commitment. Job tracks the **how, where, and what-state** during execution.

- Typical flow: `idea` reaches `Decided` → spawn a `job` (or several) → on `In-Progress`, idea's `status.md` links to the job(s) → job completes → idea closes (`Done`) when the last job archives.
- A job may exist without an idea (small ad-hoc work).
- An idea may spawn multiple jobs (substantial work breaks into several).

## Relationship with Lore

- During job execution, the LLM may read relevant lore for context.
- On **Followup** (between `done` and `archived`), extract durable lessons into lore via `/brain remember` (or conversational equivalent). Things worth extracting:
  - Repo conventions or gotchas discovered
  - Patterns or anti-patterns surfaced during design
  - Project-specific behavior that isn't documented elsewhere
- Lore never references jobs. Provenance is via raw session files (`~/.brain/lore/raw/...`), not via job wikilinks.

## Relationship with Implementation Skills (`/job`, p-craft, milestone, etc.)

- **`/job`** (personal, primary): writes `research.md`, `prd.md`, `plan/INDEX.md` + chunks, `qa-plan.md`, plus `status.md` and the recipe. Replaces `/p-craft:pr` for personal work. See `~/.claude/skills/job/SKILL.md` for the full phase model.
- **`/p-craft:pr`** (team-shared): writes `idea.md`, `research.md`, `design.md`, `plan.md`, `decisions.md` into `~/.brain/job/<slug>/`. (Skill needs migration; currently writes to `<repo>/docs/features/<slug>/`.)
- **`/p-milestone:milestone`**: may produce a job-per-PR pattern.
- Other workflows can plug in: write whatever siblings make sense; the schema doesn't constrain.

## INDEX.md format

Auto-generated, grouped by `status`:

```markdown
# Job Index

## Active
- [[job/<slug>]]: <title>: one-line hook (target repo, current phase)

## Done (followup pending)
- [[job/<slug>]]: <title>: what shipped

## Archived
- [[job/.archive/<slug>]]: <title>: when archived
```

One line per job, under ~150 characters. Archive section can be collapsed/elided once it grows large.
