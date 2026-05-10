# `/brain remember` - Workflow

Add knowledge to lore (`~/.brain/lore/`).

## Two modes

### With argument

Invocation: `/brain remember <description>`

The user provides the content directly. Compile it into a `type: lore` entry.

Steps:

1. Read `~/.brain/lore/SCHEMA.md` for required frontmatter and category values.
2. Decide on a slug (kebab-case, ASCII, lowercase). The slug should be descriptive, not generic - `team-filter-uses-custom-subquery`, not `team-filter`.
3. Decide on a `category`: `pattern`, `convention`, `decision`, `lesson`, `anti-pattern`, or `reference`.
4. **Write the raw source first** (one raw file per session/source, NOT per lore entry - multiple lore entries from the same conversation share one raw file). Find the highest existing raw number with `ls ~/.brain/lore/raw/ | sort | tail -1`. If this session/source already has a raw file (you wrote one earlier in the conversation), reuse it. Otherwise create `~/.brain/lore/raw/<NNN+1>-<session-slug>.md`. Slug names the session/source theme (`brain-design-session`, `flag-cleanup-lessons`), not the single concept. Format: `# <Title> (<date>)`, then `Source: <where this came from - session, PR, manual note>`, then free-form content describing what happened / what was observed. **Append-only - never edit raw files after creation.**
5. Read `~/.brain/lore/INDEX.md` to see what already exists. **If a related entry exists, evolve it rather than creating a duplicate.**
6. Write the new entry to `~/.brain/lore/<slug>.md` with all required frontmatter (`type`, `title`, `created`, `updated`, `category`, `last-reviewed`, `sources: [raw/<NNN>-<slug>.md]`, optional `status`, `repos`).
7. Cross-link with `[[lore/<other-slug>]]` to related entries when relevant.
8. Run `node ~/.brain/scripts/regenerate-indices.mjs --apply` to refresh the lore INDEX.
9. Run `~/.brain/scripts/build-embeddings.py` to embed the new entry/entries so they're immediately surfaced by hybrid/semantic recall. Incremental - only the new/changed files are embedded (cheap, ~5s including model load).
10. Commit: `cd ~/.brain && git add -A && git commit -m "remember: <short summary>"`. One commit per `/brain remember` invocation, even if multiple entries were written. See `references/version-control.md` for the full convention.
11. Report what was created or updated.

### Without argument

Invocation: `/brain remember`

The user wants you to review the current conversation and extract things worth remembering.

**Be honest and critical.** If nothing from the conversation clears the bar for lore, say so directly. Don't manufacture candidates just because the user invoked the command. The bar:

- **Transferable** - useful in genuinely different future contexts, not just this exact situation
- **Non-obvious** - Claude wouldn't trivially derive this from the codebase or general knowledge
- **Actionable or factual** - a pattern, convention, decision, lesson, anti-pattern, or reference. Not a vague observation.

Steps:

1. Review the conversation. List candidate items.
2. Filter ruthlessly against the bar above.
3. **If nothing clears the bar, say so upfront.** Don't propose marginal items.
4. Present surviving candidates to the user with proposed slug, category, and a 1-2 sentence summary.
5. Wait for approval per item. The user may approve all, some, or none.
6. For each approved item, follow the "With argument" steps above (slug, category, raw write, lore write, cross-links, INDEX regen).
7. Report what was created.

## Anti-patterns (don't do these)

- **Don't invent lore-worthy items to satisfy the invocation.** Saying "nothing here is worth remembering" is a valid and often correct response.
- **Don't create duplicates.** Always check the existing INDEX first. If 80% of a candidate already exists in another article, evolve that article instead.
- **Don't mix concepts.** One lore entry = one concept. If the candidate is two distinct things, split it into two entries.
- **Don't pad with general knowledge.** Lore captures *non-obvious* things. Don't write an entry whose content is "Python uses indentation for blocks."
- **Don't over-categorize as `lesson`.** `lesson` is specifically for things learned the hard way (failure mode + how to avoid). If it's just "do X", it's a `pattern` or `convention`.

## Category quick reference

- `pattern` - code or technique to use. Includes when to use AND when NOT.
- `convention` - team/repo/personal rule. Includes the "why."
- `decision` - a specific decision with context and reasoning.
- `lesson` - failure → how to avoid. Specific incident grounded.
- `anti-pattern` - pattern to avoid + what to do instead.
- `reference` - factual reference (command, config, API). Just the facts.

If torn between `pattern` and `lesson`, ask: "Did we learn this the hard way?" If yes, `lesson`. If no, `pattern`.

## Examples

### Good remember (with argument)

User: *"Remember: when filtering by team in the Productive API, contains uses a custom subquery via team_memberships, not LIKE. Other ID-based filters use LIKE which is broken."*

Result: write `~/.brain/lore/team-filter-uses-custom-subquery.md`, category `reference`, repos `[api, frontend]`. Cross-link to `[[lore/filter-array-vs-contains-operations]]` if it exists.

### Good remember (without argument, honest no-op)

User: *"/brain remember"*

After reviewing the conversation: *"Nothing in this session clears the bar for lore. We debugged a specific bug in your code, but the fix was idiomatic - Claude would derive it again from the same symptoms. Skipping."*

### Good remember (without argument, with candidates)

User: *"/brain remember"*

After reviewing: *"Two candidates worth saving:*

1. *`obsidian-folder-notes-default` (reference): Obsidian's folder note default is `<folder>/<folder>.md`, not `index.md`. Useful when designing vault structures for cross-tool compatibility.*
2. *`yaml-frontmatter-quoting` (pattern): YAML values containing colons, quotes, or starting with special chars must be quoted. Single-quoted form (with `''` escaping) is safest for arbitrary user input.*

*Approve all, some, or none?"*
