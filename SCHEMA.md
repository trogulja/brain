# Brain - Unified Knowledge Store

A personal unified knowledge store. Single root, atomic markdown files, type-grouped layout, conversational lifecycle.

## Directory Structure

```
~/.brain/
├── SCHEMA.md           - This file. Common conventions across all types.
├── <type>/             - One directory per type.
│   ├── SCHEMA.md       - Type-specific schema (frontmatter, lifecycle, conventions).
│   ├── INDEX.md        - Auto-generated from frontmatter.
│   └── <slug>.md       - Single-file entry.
│   └── <slug>/         - Folder entry (when sub-artifacts are needed).
│       ├── <slug>.md   - Main content (folder note - same name as the folder).
│       ├── *.md        - Sibling sub-files (research, decisions, status, etc.).
│       └── attachments/ - Binaries (images, PDFs).
```

## Common Conventions

### Slug format

- kebab-case ASCII, lowercase, hyphenated
- No special chars beyond hyphens
- Slug is the filename (or folder name) - no separate `slug` frontmatter field
- Per-type uniqueness (slug `auth` may exist in multiple types)

### Storage unit (hybrid, per-instance opt-in)

- Default: single file (`<slug>.md`)
- Promote to folder when sub-artifacts are needed (`<slug>/<slug>.md` + siblings - Obsidian Folder Notes convention)
- Promotion mechanics: `mkdir <slug>/`, move file → `<slug>/<slug>.md`. Wikilink form `[[<type>/<slug>]]` is unchanged.
- Type doesn't dictate file vs folder - entries opt in based on need

### Wikilinks (explicit, Obsidian-compatible)

- All entries: `[[<type>/<slug>]]`
  - File entry → resolves to `~/.brain/<type>/<slug>.md`
  - Folder entry → resolves to `~/.brain/<type>/<slug>/<slug>.md` (folder note)
- Attachments: `[[<type>/<slug>/attachments/<filename>]]`
- Always use the explicit form. Never short-form `[[<slug>]]`.
- Wikilink form is uniform across file and folder entries - promoting from file to folder doesn't change any inbound link.

### Common Frontmatter

Every entry, regardless of type:

```yaml
---
type: <type-name>          # required - must match parent directory
title: <human-readable>    # required
created: <YYYY-MM-DD>      # required - never changes
updated: <YYYY-MM-DD>      # required - bumps on edit
tags: [<tag>, ...]         # optional - flat global namespace, used with discipline
---
```

Per-type schemas extend this. Type-specific fields are documented in `~/.brain/<type>/SCHEMA.md`.

### Tags discipline

- Tags are flat, global, kebab-case
- Use sparingly - only when the tag adds search value
- Don't tag with the type itself (e.g. don't tag a lore entry with `lore`)
- Avoid synonyms - pick one form (`auth`, not both `auth` and `authentication`)
- Tags TBD in detail; default behavior: use sparingly, prefer none over speculative

### Attachments

- Only allowed in folder entries
- Live at `~/.brain/<type>/<slug>/attachments/<filename>`
- File-form entries that need attachments must promote to folder form first

## INDEX.md Generation

- Per-type, located at `~/.brain/<type>/INDEX.md`
- Auto-generated from frontmatter - never hand-maintained
- Format is type-specific (grouped by phase, status, category, etc.)
- Regenerate after writes, or on demand via `/brain regenerate-index <type>`

No global INDEX.md - cross-type queries handled by search/grep across the tree.

## Lifecycle

**Schema-declared, LLM-executed.** Each type's `SCHEMA.md` documents its lifecycle:

- Valid states (if applicable)
- Valid transitions (if applicable)
- What to update on each transition
- What to ask the user
- Type-specific structural conventions

The LLM reads the per-type SCHEMA.md when working with a type. There are no per-type CRUD skills (`/<type> park`, `/<type> close`, etc.). Lifecycle operations are conversational - the user says "park context-assistant" and the LLM follows the type schema's instructions.

Skills (in `~/.claude/skills/`) exist only for high-frequency repeatable workflows that benefit from explicit invocation, not for every operation.

## Cross-Type Concepts

- Wikilinks span types: `[[lore/zfc-principle]]` from a `~/.brain/idea/foo/foo.md` works.
- Tags span types: `tags: [filtering]` may appear in lore, ideas, compasses.
- Search/grep work across the tree - `grep -r "view-setup" ~/.brain/`.

## Adding New Types

To add a new type (e.g. `compass`):

1. Create `~/.brain/<type>/` directory
2. Write `~/.brain/<type>/SCHEMA.md` defining frontmatter, lifecycle, conventions
3. The type is now usable - entries can be created, wikilinks resolve, INDEX generates
4. Optional: write a workflow skill if the create flow is high-frequency or non-trivial

No code changes to the brain itself. Types are data, not classes.

## Live Types

- `lore` - atomic durable knowledge (file entries)
- `idea` - pre-implementation thinking (folder entries with siblings)
- `job` - in-flight (and recently-finished) work units: recipe + status + free-form artifact siblings (collapses earlier `active-work` + `job-artifact`, decided 2026-04-27)
- `followup` - open commitments / things owed, cross-cutting "what am I on the hook for" (single-file by default; status open/done/dropped; no due dates by design - time-bound items migrate to Apple Reminders or calendar)
- `research-link` - URL to research later (file entries)

## Reserved Types

Names locked, full schema design deferred until needed:

- `compass` - task-keyed dense context files
- `digest` - output of read-later digest processing
