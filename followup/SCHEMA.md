# Followup Type Schema

Open commitments and things I owe people (or myself) - context-recall, not time-based.

A `followup` is a single open thread that doesn't fit elsewhere:
- Something I committed to deliver (workshop, doc, ping).
- Something I'm waiting on from someone.
- Personal "vrati se na ovo" kad tema iskoči.

**What this is NOT:**
- Time-based reminders ("sutra u 9 zovi X") - use Apple Reminders or calendar.
- In-flight work units → `job/`.
- Pre-implementation thinking → `idea/`.
- Durable knowledge → `lore/`.
- Internal sub-tasks of an idea/job → keep them as checkboxes in that entry's `status.md`.

The followup is for the **cross-cutting** "what am I on the hook for" view that no other type provides.

## Storage

Single file by default: `~/.brain/followup/<slug>.md`.

Folder form (`<slug>/<slug>.md`) only if the followup grows attachments or sub-notes - usually it doesn't.

## Frontmatter

```yaml
---
type: followup                            # required
title: <human readable>                   # required
created: <YYYY-MM-DD>                     # required
updated: <YYYY-MM-DD>                     # required
tags: [<tag>, ...]                        # optional

# followup-specific
status: open                              # required: open | done | dropped
with: <person or team>                    # optional: who I owe / wait on
related: [[idea/<slug>]]                  # optional: link to originating idea/job/lore
---
```

### `status` values

- `open` - still on the hook.
- `done` - handled. Stays in place; recall can still surface it as historical context.
- `dropped` - explicitly decided not to do. Note WHY in body.

No `due` field by design. If something becomes time-bound, **migrate it out** to Reminders or calendar and either close the followup or leave a body note pointing where it lives.

## States and Transitions

```
open ──→ done
   └──→ dropped
```

| Operation | From | To | What happens |
|---|---|---|---|
| **Capture** | - | `open` | Create file. Note the commitment, who, why, any context. Bump INDEX. |
| **Update** | `open` | (same) | Edit body when state changes (e.g. "pingao Brunu, čekam odgovor"). Bump `updated`. |
| **Close** | `open` | `done` | Set `status: done`. Optional 1-liner what happened. Move INDEX entry. |
| **Drop** | `open` | `dropped` | Set `status: dropped`. Note WHY in body so future-self understands. Move INDEX entry. |
| **Migrate to Reminders/Calendar** | `open` | `done` or stays `open` | If the action becomes time-specific, create the reminder/event and either close the followup (if it's now fully tracked there) or leave it open with a body note pointing to the calendar/reminder. |

## Body conventions

Short. Followups grow stale fast - keep them scannable.

```markdown
# <title>

**Context:** 1-2 sentences why this exists, where it came from (Slack link, idea ref, conversation).

**Action:** what concretely needs to happen.

**State:** free-form notes as things move (e.g. "2026-05-08 - pingao Car, čeka launch").
```

When closing, a one-liner outcome is enough; don't write a postmortem here. Lessons go to `lore/`.

## INDEX

`~/.brain/followup/INDEX.md` - auto-generated, grouped by `status`:

```markdown
# Followup Index

## Open
- [[followup/<slug>]] - <title> (with: <person>)

## Done
- [[followup/<slug>]] - <title>

## Dropped
- [[followup/<slug>]] - <title>
```

## Relationship with other types

- **idea/job status.md checkboxes** - those are *internal* steps of that work unit. Followups are *external* commitments or cross-cutting "remember to come back". If a checkbox is really a commitment to someone, promote it: create followup, link via `related`, and remove the checkbox or replace it with a wikilink.
- **lore** - when a followup teaches a durable lesson on close, capture lore separately. Followup body shouldn't try to carry knowledge.
- **research-link** - if the followup is "read this URL when I have time", a research-link entry is closer in spirit. Use followup only if there's a commitment around it (someone asked, you promised, etc.).
