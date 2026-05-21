# Job Type Schema

A `job` is the long-lived personal workspace for **a feature or initiative** — typically multiple milestones, multiple PRs, persisting across many sessions until the feature is genuinely complete (or abandoned). Folder entries by default. Lifecycle: `active` → `done` → `archived`.

**Job ≠ single PR.** A job that ships one PR and never reopens is a degenerate case, not the default. The normal flow: M1 ships → job stays `active` with M1 added to Links and "Where I am now" noted as *between milestones* → M2 picked up → M2 ships → repeat. The recipe is the **source of truth** for "what's the state of this feature?" — current iteration, what's queued, multiple PRs accumulated in Links.

The schema compactions (chunks absorbing prose, soft caps on parents, supersession layer) exist *because* the recipe must stay readable across many milestones without bloat. Don't fight that — leverage it.

## Storage

Folder entry: `~/.brain/job/<slug>/`

```
<slug>/
  <slug>.md          # recipe — L0, always loaded
  log.md             # work log (one-liners → chunks)
  notes.md           # research + findings (one-liners → chunks)
  design.md          # acceptance + decisions + plan (one-liners → chunks)
  testing.md         # test scenarios + eval prompts + gates
  discarded.md       # supersession layer — what we backed away from
  chunks/            # single folder, all chunk prose lives here
    01-<slug>.md
    02-<slug>.md
    ...
  attachments/       # screenshots, eval outputs, draft PR descriptions
```

`INDEX.md` is auto-generated. Never edit by hand. Regenerate via `~/.brain/scripts/regenerate_indices.py --apply`.

Don't pre-create empty parent files or `chunks/`. Create them when content exists.

## Frontmatter (on recipe `<slug>.md`)

```yaml
---
type: job                          # required
title: <title>                      # required
status: active                      # required: active | done | archived
created: <YYYY-MM-DD>               # required
updated: <YYYY-MM-DD>               # required
target-repo: <repo>                 # optional
related-idea: [[idea/<slug>]]       # optional
tags: [<tag>, ...]                  # optional
---
```

Don't add: `last-commit`, `last-cleanup`, `phase` (phase lives in the recipe body "Where I am now").

Set `related-idea` when the job implements a decided idea.

## Recipe structure (`<slug>.md`)

Soft cap: ~80 lines. This is L0. Every line reloads on session start.

```markdown
---
<frontmatter>
---
# <Title>

## Goal
1-3 sentences. What and why.

## Invariants
- INV-1 MUST <constraint>. See [[chunks/NN-<slug>]]
- INV-2 MUST NOT <constraint>. See [[chunks/NN-<slug>]]

## Where I am now
≤3 sentences. Current phase + most recent meaningful state.

## Next step
One concrete action.

## Scope
- In: <bullets>
- Out: <bullets>

## Links
- Idea: [[idea/<slug>]] (optional)
- PRs: <url1>, <url2>, ... (accumulate over milestones)
- Worktree: <path> (current active worktree, if any)
- Target repo: <name>
```

**Multi-milestone recipes.** When a job spans multiple milestones, the recipe accumulates without bloating: each shipped milestone gets a one-line entry in Links (PR URL + log chunk reference); the planned-next milestone goes in "Where I am now" and "Next step"; future-milestone design space (the roadmap of what's queued) lives either inline as a short bullet list in the recipe OR in a dedicated chunk (e.g. `chunks/NN-roadmap.md`) referenced from "Where I am now". The roadmap is *part of the job*, not a sibling `idea/` entry.

Spawned TODOs that outlive the job move to `~/.brain/followup/<slug>.md` at chunk-close, not into the recipe.

## Invariants

The truth layer. The small set (typically 3-10) of locked decisions the rest of the job operates under.

**Format.** ADR-style one-liner in the recipe + rationale in a chunk file:

```
INV-3 MUST keep flag-OFF path byte-identical to develop. See [[chunks/12-flag-off-byte-identity]]
```

The chunk file holds the "why" — can be long.

**Granularity.** Invariants are the load-bearing set, not every decision. "We picked TypeScript" is a decision (lives in `design.md`). "MUST preserve flag-OFF byte-identity" is an invariant (silent compliance with a contradicting instruction would damage the job).

**When checked.** Direction-change moments, not session-start:

- Before writing a chunk file
- Before flipping a chunk to `superseded`
- Before any tool call that modifies code/repo state
- When the user's instruction appears to reframe scope (judgment call)

**Warning shape.** Conversational. When Claude detects a conflict:

> "This conflicts with INV-7 (no append-across-pagination). Intentional update, or did I misread?"

Three outcomes:

- **False alarm** → proceed, no file change.
- **Update the invariant** → trigger supersession (below).
- **User misspoke** → adjust the instruction.

Warnings should stay rare. If they fire on every clarification they lose signal.

**Supersession.** When an invariant changes:

1. Recipe line updated in place.
2. Old rationale chunk gets `status: superseded, superseded-by: chunks/NN-<slug>` in frontmatter.
3. New invariant gets a fresh rationale chunk.
4. Old chunk's one-liner moves from `design.md` → `discarded.md`'s `## Invariants superseded` section.

## Parent files

Soft cap: ~150 lines each. Contents are one-liners + chunk pointers. Prose lives in chunks.

### `log.md`

Flat chronological list of work events (commits, branches, PRs, milestones).

```markdown
# Work log

- [[chunks/01-bootstrap]] 2026-04-28 — bootstrap branch + LazyOutputStore skeleton
- [[chunks/02-schema-redesign]] 2026-04-29 — query_resources schema redesign
- ...
```

### `notes.md`

Flat list of research + findings. Tag each one-liner.

```markdown
# Notes

- [[chunks/05-handle-survey]] [research] handle-architecture industry survey (MCP, Claude Code, LangChain, RubyMine)
- [[chunks/06-jq-subset]] [finding] jq subset supports `as $var` — original two-call recipe was wrong
- ...
```

### `design.md`

Flat list of acceptance criteria, decisions, plan chunks. Tag each one-liner.

```markdown
# Design

- [[chunks/03-flag-off-byte-identity]] [acceptance] flag-OFF path byte-identical to develop
- [[chunks/04-per-call-interception]] [decision] per-call interception, NOT append-across-pagination
- [[chunks/07-pr-split-system-instructions]] [plan] PR-1 system-instructions split
- ...
```

### `testing.md`

Sub-sections by type (scenarios, eval prompts, acceptance gates have different shapes).

```markdown
# Testing

## Scenarios
- [[chunks/10-bulk-intent-prompt]] bulk-intent vs mirror-engage-tom (7,434 records, 8 lazy calls)

## Eval prompts
- [[chunks/11-regression-smoke]] regression-smoke carry-overs

## Acceptance gates
- [[chunks/12-input-budget]] re-run chunk-34 prompt: per-turn input < 0.5K
```

### `discarded.md`

Sub-sections by reversal type. Captures things that were *committed-to* and then *reversed*. Upfront rejections (considered and not picked) belong inside the deciding chunk, not here.

```markdown
# Discarded

## Decisions reversed
- [[chunks/01-handle-architecture]] handle architecture (superseded 2026-05-15 by [[chunks/04-per-call-interception]])

## Scope changes
- [[chunks/02-read-file-from-url-in-scope]] read_file_from_url in-scope (dropped 2026-05-03; revived as [[job/read-file-from-url]])

## Plan retired
- [[chunks/25-pr2-description-rewrite]] PR-2 description rewrite (retired 2026-05-07; replaced by chunks 32-35)

## Invariants superseded
- [[chunks/15-no-append-across-pagination]] INV-2 append-across-pagination (superseded 2026-05-15 by [[chunks/40-per-call-only]])
```

## Chunks

Single folder. All chunk prose lives here. No size cap on individual chunks (archival layer; load by id).

**Numbering.** Global, monotonic across the job's lifetime. `chunks/01-<slug>.md`, `chunks/02-<slug>.md`, ... Don't renumber on supersession or retirement — the sequence is append-only.

**Filename slug.** Short, kebab-case, descriptive. The number anchors order; the slug aids recall.

**Frontmatter.**

```yaml
---
type: chunk                         # required
chunk-type: log | research | finding | acceptance | decision | plan | testing | invariant-rationale  # required
title: <short title>                # required
status: accepted | superseded | retired  # required
created: <YYYY-MM-DD>               # required
updated: <YYYY-MM-DD>               # required
superseded-by: chunks/NN-<slug>     # required iff status == superseded
respected: [INV-3, INV-7]           # optional — invariants this chunk operated under
deferred: [INV-5]                   # optional — invariants this chunk consciously did not enforce
commit: <sha>                       # log chunks only
---
```

**Body.** Free-form prose.

## Chunk-close ritual

User invokes conversationally. Claude executes the steps below (in order):

1. **Invariant check.** Does the proposed chunk content conflict with any active INV? If yes, warn conversationally. Halt unless the user resolves (false alarm / supersede / adjust).
2. **Write the chunk file.** `chunks/NN-<slug>.md`. Body + full frontmatter.
3. **Add one-liner to parent.** Picks the right parent file from `chunk-type` (log → log.md, decision → design.md, etc.). ≤80 chars of context after the wikilink.
4. **Handle supersession.** If this chunk replaces prior ones: flip their frontmatter (`status: superseded, superseded-by: chunks/NN-<slug>`); move their one-liners from parent → correct sub-section of `discarded.md`.
5. **Update recipe.** Bump `updated:`. Refresh "Where I am now" + "Next step". Update phase line if it changed.
6. **Soft budget check.** If recipe > ~80 lines or any parent > ~150, call it out (no hard block).

## Supersession

One mechanism applied uniformly across decisions, scope, plan, and invariant rationale (see chunk-close step 4). Superseded chunks stay in `chunks/` and remain readable; nothing is deleted, wikilinks never break.

## Lifecycle transitions

```
active ──→ done ──→ archived
   │
   └─→ (between-milestones: STAYS active. Note in "Where I am now". This is the normal flow for multi-milestone jobs.)
```

**Key principle: `status: done` means "the feature is complete — no further milestones planned."** It does NOT mean "the most recent PR shipped." Most jobs spend most of their lifetime in `active`, walking through multiple milestone arcs. The `done` transition is the rare one.

| Operation | From | To | What happens |
|---|---|---|---|
| **Start** | n/a | `active` | Create folder + recipe. Goal + initial scope + first invariants. |
| **Update** | `active` | (same) | Edit recipe + parent files + chunks via chunk-close ritual. Bump `updated:`. |
| **Milestone ship** | `active` | (same — STAYS active) | A PR shipped, but more milestones are planned. Add PR URL to recipe Links. Write a log chunk for the PR-open event. Update "Where I am now" + "Next step" to point at the next milestone. Do NOT flip `status` unless the whole feature is concluded. |
| **Complete** | `active` | `done` | Frontmatter `status: done` ONLY when no further milestones are planned and the feature is genuinely concluded. Recipe Links section already has accumulated PR URLs from prior milestones. |
| **Followup** | `done` | (still `done`) | Extract durable lessons → `lore`. Push spawned TODOs → `followup`. After this pass, archive. |
| **Archive** | `done` | `archived` | Frontmatter `status: archived`. Folder moves to `~/.brain/job/.archive/<slug>/`. |
| **Reopen** | `done` \| `archived` | `active` | Rare. Only when a job marked `done` needs unexpected new work (e.g. discovered a follow-on milestone we didn't anticipate). If archived, move back. Note in recipe why reopening. Normal milestone-to-milestone flow should never need this — it's the escape hatch for misclassified completions. |

Always regenerate the job INDEX after status changes: `~/.brain/scripts/regenerate_indices.py --apply`.

### Anti-pattern: flipping `done` after every milestone

If a job's history shows a status oscillation `active → done → active → done → active → ...`, the prior `done` flips were wrong. Each milestone-ship should have kept the status `active` with an update to "Where I am now". The `done` state should be entered at most once per job lifetime (barring genuine reopen-for-unexpected-work cases).

Symptom that catches this in review: the recipe says `status: done` but a sibling `idea/<related-roadmap>` (or any forward-looking design) contains queued milestones. That state is incoherent — fix it by setting status back to `active` and folding the roadmap content into the job.

## Relationship with Idea / Lore / Followup

- **Idea** tracks the what-and-why **before** commitment. Once a feature has a live job, the job *is* the source of truth — including its forward-looking roadmap of queued milestones. Idea should NOT be used to hold "milestones we're going to do next on a feature that already has an active job" — that's a job-internal concern (recipe + chunks). Idea is for pre-commitment exploration, not active-feature roadmapping. Typical: idea reaches `Decided` → spawn job → idea closes (or stays as the historical "why we started this"); the job carries the feature forward from there.
- **Lore** absorbs durable lessons at Followup. Repo conventions, anti-patterns, project-specific gotchas. Via `/brain remember` or conversational equivalent.
- **Followup** (the brain type) absorbs spawned TODOs that outlive the job. Open follow-ups don't live in the job recipe — they move to `~/.brain/followup/<slug>.md` at chunk-close when surfaced.

## Relationship with Implementation Skills

- **`/job`** (personal, primary): writes the v2 shape. See `~/.claude/skills/job/SKILL.md`.
- **`/p-craft:pr`** (team-shared): writes the v2 shape.
- **`/p-milestone:milestone`**: may produce a job-per-PR pattern.
- Other workflows can plug in: write chunks of the relevant types; the schema doesn't constrain.

## v1 → v2 migration

Existing active jobs migrate to v2. Done jobs stay as-is in v1 shape (nothing to gain from rewriting). Migration steps (per active job):

1. Extract invariants from existing `decisions.md` + recipe Scope. Write as INV-N one-liners in recipe + one rationale chunk each.
2. Walk closed work items. Each becomes a chunk in `chunks/` with appropriate `chunk-type`. Add one-liner to the right parent file.
3. Walk current `decisions.md`. Live decisions → chunks (chunk-type: decision) + one-liner in `design.md`. Superseded content → chunks (status: superseded) + one-liner in `discarded.md`.
4. Slim recipe to L0 (~80 lines). Move all narrative out.
5. Delete v1 artifacts (`status.md`, `prd.md`, `decisions.md`, `findings.md`, `research.md`, `qa-plan.md`, `plan/`) once their content is fully redistributed into v2 shape.
6. Bump recipe `updated:`. Regenerate INDEX.
