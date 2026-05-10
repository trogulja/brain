# Research-Link Type Schema

URLs to research later. One file per URL. Lightweight inbox model - capture fast, process later, archive when stale.

## Storage

File entry: `~/.brain/research-link/<slug>.md`

Slug: short kebab-case identifier derived from the URL or its content (`meta-tribal-knowledge`, `obsidian-folder-notes`).

## Frontmatter

```yaml
---
type: research-link                        # required
title: <title-of-the-target>                # required
created: <YYYY-MM-DD>                       # required
updated: <YYYY-MM-DD>                       # required
tags: [<tag>, ...]                          # optional

# research-link-specific
url: <full-url>                             # required
status: inbox                                # required: inbox | researching | researched | archived
---
```

## States and Transitions

```
inbox ──→ researching ──→ researched ──→ archived
   │                          │
   └──── (skip directly) ─────┘
```

### Transitions

| Operation | From | To | What happens |
|---|---|---|---|
| **Capture** | - | `inbox` | Create entry. URL + title required. Body may be empty or hold a one-liner about why saved. |
| **Start research** | `inbox` | `researching` | When you sit down to read. Update `status`, bump `updated`. |
| **Complete research** | `researching` | `researched` | After reading: write key takeaways into body. Cross-link to relevant lore/ideas. Update `status`, bump `updated`. |
| **Skip-process** | `inbox` | `researched` | If reading and writing takeaways happens in one go (common for short articles). |
| **Archive** | `researched` | `archived` | When entry no longer actively useful (knowledge extracted, no longer being referenced). Keep for history. |

### Lifecycle invocations are conversational

- "drop this URL into research" → `/research <url>` skill OR conversational "remember this link to read later"
- "I just read X, here's what I got from it" → LLM updates entry to `researched` with takeaways
- "archive the meta tribal knowledge link" → LLM moves to `archived`

## Conventions

### On capture

- Title can be derived from the URL (page title, or short slug-based name)
- Body initially empty or one-liner is fine - don't over-structure unread content
- Tags are optional; usually applied at `researched` step when the topic is clearer

### For video URLs (YouTube)

When the URL is a YouTube video (`youtube.com/*`, `youtu.be/*`), the body content can't be skimmed directly. At **research-complete time** (not capture), fetch the transcript:

```
~/.brain/scripts/fetch-yt-transcript.sh <url>
```

Prints a metadata header (title, uploader, duration) and the full deduped transcript on stdout. Read it, then write takeaways into the entry the same way you would for an article. Exits non-zero if no captions are available (live streams, music videos); note that in the entry and skip.

### On research-complete

Body grows to include:

- Key takeaways (bullet points)
- Cross-references to lore/ideas where the content connects (`[[lore/<slug>]]`)
- Optional: full quotes worth preserving
- Optional: action items ("worth turning into a lore article", "obsoletes [[lore/X]]")

### Recommended body structure for `researched` state

```markdown
# <Title>

[<URL>](<url>)

## Key takeaways
- <bullet>
- <bullet>

## Connections
- [[lore/<slug>]] - how it relates
- [[idea/<slug>]] - informs this idea

## Notes
<freeform - quotes, observations, why this matters>
```

For `inbox` state, the body can be empty or just a single sentence.

## Slug generation

Recommended approaches (use whichever makes sense):

- Page title → kebab-case (`meta-tribal-knowledge-mapping`)
- Domain + key words (`fb-tribal-knowledge`, `arxiv-2510-04618`)
- Topic-based (`obsidian-folder-notes`)

Slugs should be human-readable. Don't auto-generate from raw URLs (no `httpsexamplecomarticle12345`).

## Promotion to folder

Almost never needed. Research-links are intentionally lightweight. If an entry needs attachments (a saved PDF of an article, e.g.), promote to folder; otherwise keep as file.

## INDEX.md format

Auto-generated, grouped by `status`:

```markdown
# Research-Link Index

## Inbox (unread)
- [[research-link/<slug>]] - <title>

## Researching (in progress)
- ...

## Researched (key takeaways captured)
- ...

## Archived
- ...
```

Within each group, sorted by `updated` descending (most recent first) - recently-touched stuff is likely most relevant.
