# `/brain cleanup` - Workflow

Run a structural health check across all types in `~/.brain/`. Find drift, gaps, and inconsistencies. **Report findings; never modify without user approval.**

## Before scanning: suppress read-logging

Cleanup reads are audit reads, not "I needed this knowledge" reads. Logging them would pollute recall analytics - entries inspected during cleanup would look popular, and real retrieve-no-read patterns would be masked.

Touch the sentinel before the first scan:

```bash
mkdir -p ~/.brain/.cache && touch ~/.brain/.cache/skip-log
```

Remove it at the end of the workflow:

```bash
rm -f ~/.brain/.cache/skip-log
```

The sentinel auto-stales after 30 min, so a crashed cleanup doesn't permanently disable logging - but always clean up explicitly when you're done.

### Concurrent-session caveat

The sentinel is global, not session-scoped. If you run cleanup while another Claude session is actively reading brain entries for real work, the other session's reads will *also* be suppressed - silent data loss for the duration of cleanup. Bounded to ~30 min by auto-stale, but real.

**Avoid running cleanup while another session is working in `~/.brain/`.** If you must, accept that you'll under-count reads in the concurrent session for the duration. The aggregate impact over weeks is small, but be aware.

(Proper session-scoped sentinels would require a PreToolUse hook + extra plumbing to capture session_id at sentinel-write time. Deferred - the current design is honest about its limitation.)

## Goals

1. Catch contradictions between entries before they propagate
2. Find concept gaps (mentioned but no entry exists)
3. Verify wikilinks resolve
4. Surface stale work (idle ideas, abandoned jobs, lingering open followups, unprocessed research-links)
5. Detect frontmatter problems (missing required fields, invalid values)

## Workflow

### 1. Lore checks

For `~/.brain/lore/*.md`:

- **Wikilink resolution**: every `[[lore/<slug>]]` and `[[idea/<slug>/index]]` must point to an existing file. List broken links.
- **Source resolution**: every entry's `sources: [raw/...]` reference must point to an existing file in `~/.brain/lore/raw/`. List broken sources.
- **Mentioned concepts without entries**: scan body text for terms that look like they should have their own lore entry (capitalized phrases, technical concepts referenced multiple times). Flag candidates without forcing creation.
- **Contradictions**: read entries by category; flag pairs where the body content disagrees about the same topic. Subjective - present pairs and let user judge.
- **Frontmatter completeness**: every entry must have `type`, `title`, `created`, `updated`, `category`. Optional but recommended: `last-reviewed`. List entries missing required fields.
- **Category sanity**: list any entry with a `category` value not in the canonical set (`pattern`, `convention`, `decision`, `lesson`, `anti-pattern`, `reference`, `behavior`).
- **No calendar-based staleness for lore.** Don't flag old entries - knowledge doesn't expire on a schedule. **No source-mtime staleness either** - raw files are append-only by convention, so a changed mtime would itself be a convention violation, not a useful staleness signal about the lore. Only flag if something else (broken sources via the existence check above, contradictions surfaced by reading) suggests review is warranted. `last-reviewed` is the user's own bookkeeping, not a trigger for automation.

### 2. Idea checks

For `~/.brain/idea/<slug>/<slug>.md`:

- **Wikilink resolution**: same rule as lore.
- **Phase validity**: `phase` must be `Exploring | Decided | In-Progress | Done | Parked`. List invalid values.
- **Stale Exploring**: ideas in `Exploring` phase with no updates in >60 days are candidates for parking. **Don't park automatically** - surface and ask.
- **In-Progress without target-repo**: if `phase: In-Progress` but `target-repo` is missing, flag it.
- **Folder structure**: every idea folder should have a folder note `<slug>.md` (same name as the folder) at minimum. Optional siblings: `research.md`, `decisions.md`, `status.md`. Flag missing folder note. Flag stray files that don't match the convention.

### 3. Job checks

For `~/.brain/job/<slug>/<slug>.md`:

- **Wikilink resolution**: same rule as lore.
- **Status validity**: `status` must be `active | done | archived`. List invalid values.
- **Archived not in `.archive/`**: if `status: archived` but the folder still lives at `~/.brain/job/<slug>/` (not `~/.brain/job/.archive/<slug>/`), flag the location drift.
- **`done` without followup pass**: jobs with `status: done` and `updated` >30 days ago - schema's "followup" pass (extract durable lessons to lore, archive) hasn't happened. Surface and ask whether to archive.
- **Stale active**: `status: active` with no `updated` bump in >30 days. Schema treats paused jobs as still-active with a note in `status.md`, so this is a soft prompt: still alive, paused, or done?
- **`related-idea` resolution**: if `related-idea: [[idea/<slug>]]` is set, the target must exist. List broken refs.
- **Folder structure**: every job folder needs the recipe (`<slug>.md`) and `status.md`. Flag missing. Other siblings are workflow-driven and not enforced.

### 4. Followup checks

For `~/.brain/followup/*.md` (or folder form when present):

- **Wikilink resolution**: same rule as lore.
- **Status validity**: `status` must be `open | done | dropped`. List invalid values.
- **`related` resolution**: if `related: [[<type>/<slug>]]` is set, the target must exist. List broken refs.
- **No `due` field**: schema explicitly forbids due dates. If any followup has a `due:` frontmatter field, flag it - it should migrate to Apple Reminders or calendar and either close or leave a body pointer.
- **Stale open**: `status: open` with no `updated` bump in >90 days. Soft prompt: still on the hook, or should this be dropped? Don't auto-drop - ask.
- **`dropped` without WHY**: schema requires a body note explaining why on drop. If a `dropped` entry has no body content beyond frontmatter, flag it.

### 5. Research-link checks

For `~/.brain/research-link/*.md`:

- **Status validity**: `status` must be `inbox | researching | researched | archived`. List invalid values.
- **Stale inbox**: items in `inbox` for >30 days that haven't been touched. Either process or archive. Surface and ask.
- **Researching items**: items in `researching` for >7 days. Probably stuck - ask whether to revert to inbox, complete, or abandon.
- **Empty researched bodies**: if `status: researched` but the body has no takeaways or cross-links, the research wasn't actually captured. Flag it.

### 6. Cross-cutting checks

- **Slug collisions**: same slug across different types (e.g. `lore/auth` and `idea/auth/`). Allowed by the schema, but flag them so the user is aware. Wikilinks are explicit so no actual conflict, just potential confusion.
- **INDEX freshness**: regenerate `INDEX.md` for each type via `node ~/.brain/scripts/regenerate-indices.mjs --apply` and compare. If the regenerated INDEX differs from the existing INDEX, flag the drift (entries added or removed without index regen).
- **Tag inconsistency**: scan all `tags: [...]` across entries. Flag suspected synonyms (e.g. both `auth` and `authentication`, both `ai-agent` and `ai-agents`). Don't auto-merge - ask the user which form to canonicalize.

### 7. Recall analytics (aggregate review)

Run `python3 ~/.brain/scripts/analyze.py --days 30`. Two append-only logs (`recall_log`, `read_log`) get aggregated independently - no per-event correlation. Aggregate is what's actionable.

What to flag from the report:

- **Dead queries** (zero results, ≥2×) → knowledge gap. Suggest capturing lore or research-link on the topic.
- **Retrieve-no-read** (surfaced ≥3×, read <30% of the time) → content stale, name misleading, or BM25 over-ranking. Open the article and judge: rewrite title/tags? Demote via better-named alternative? Delete?
- **Read but never surfaced** → entry reached via wikilink or direct path, but recall never returned it. Often means BM25 score is too low for relevant queries - the entry's title/tags don't match how Claude searches for it. Consider rewording the title or adding tags.
- **Top read paths** → most-used entries. Stable + heavily-read entries are candidates for L0 promotion (Phase 3).
- **Top surfaced paths with low read count** → similar to retrieve-no-read but at the high-volume end.

Don't auto-act on this section. Surface findings; let the user decide what to fix in content vs accept as noise.

## Output format

Present findings as a structured report. Group by type, then by severity. Example:

```markdown
# Brain Cleanup Report - <date>

## Summary
- Lore: <N> entries scanned, <N> issues
- Idea: <N> entries scanned, <N> issues
- Job: <N> entries scanned, <N> issues
- Followup: <N> entries scanned, <N> issues
- Research-link: <N> entries scanned, <N> issues

## Lore findings

### Broken wikilinks (1)
- `lore/foo` references `[[lore/missing-slug]]` - target doesn't exist.

### Missing required frontmatter (1)
- `lore/bar` is missing `category`.

### Possible contradictions (subjective)
- `lore/x` says "always use X". `lore/y` says "X is deprecated, use Y". Reconcile?

## Idea findings

### Stale Exploring (>60 days) (2)
- `idea/foo` last updated 2026-02-01. Park or revive?
- `idea/bar` last updated 2026-01-15. Park or revive?

## Job findings

### Done without followup pass (1)
- `job/baz` done 2026-02-20, no lessons extracted. Archive?

## Followup findings

### Stale open (>90 days) (1)
- `followup/ping-x-about-y` open since 2026-01-10. Still on the hook, or drop?

## Research-link findings

### Stale inbox (>30 days) (3)
- `research-link/x` saved 2026-03-01. Process or archive?
- ...

## Cross-cutting

### INDEX drift
- `lore/INDEX.md` is missing 1 entry that exists on disk. Run regenerate-indices.

### Tag synonyms suspected
- `auth` (12 entries) vs `authentication` (3 entries). Canonicalize?
```

## After the report

Wait for user direction. The user picks what to act on. For each chosen action:

- **Fix wikilinks**: update the body, bump `updated`, verify the link resolves.
- **Add missing frontmatter**: update file, bump `updated`.
- **Resolve contradictions**: merge or supersede entries, edit one to reference the other.
- **Park stale ideas**: follow `~/.brain/idea/SCHEMA.md` Park transition.
- **Archive stale jobs**: follow `~/.brain/job/SCHEMA.md` Followup → archive flow (extract lore first, then move to `.archive/`).
- **Drop or close stale followups**: follow `~/.brain/followup/SCHEMA.md` Close/Drop transition. Capture WHY on drop.
- **Archive stale research-links**: follow `~/.brain/research-link/SCHEMA.md` Archive transition.
- **Regenerate INDEXes**: `node ~/.brain/scripts/regenerate-indices.mjs --apply`.
- **Canonicalize tags**: bulk-rewrite the chosen form, bump `updated` on each affected entry.

After applied changes, regenerate INDEXes once at the end.

Then commit everything that changed in a **single** commit:

```bash
cd ~/.brain && git add -A && git commit -m "cleanup: <short summary of what was fixed>"
```

One commit per cleanup session, no matter how many entries were touched. The cleanup report serves as the natural commit unit. See `references/version-control.md` for the full convention.

## What cleanup does NOT do

- **Auto-modify content.** Always ask. The user is the source of truth on resolution.
- **Delete entries.** Never. Use `status: deprecated` or move to a parked equivalent.
- **Force a cadence.** Cleanup is invoked when the user wants it. No "you should run cleanup every week" reminders.
