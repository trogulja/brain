# `/brain` - L0 Curation (CLAUDE.md)

Workflow for adding, updating, auditing, or pruning rules in `~/.claude/CLAUDE.md` - your personal behavioral layer.

L0 = behavioral rules ("how I want Claude to behave"). Distinct from knowledge (lore) and from project context (project CLAUDE.md). Scope of L0 is **only** `~/.claude/CLAUDE.md`.

## Conventions

- **CLAUDE.md stays clean.** Pure rules. No wikilinks, no metadata, no provenance markers - that bloats every session's initial context for zero runtime benefit.
- **Behavioral lore lives in `~/.brain/lore/` with `category: behavior`.** Litmus: "would this be true for a different user?" If no → `behavior`. If yes → one of the knowledge categories.
- **Provenance is a query result, not a stored relationship.** Audit runs BM25 between each rule and behavioral lore to surface likely backing entries. Fuzzy by design - wording drift doesn't break anything.
- **Soft token cap ~2K.** Audit warns over. No hard refusal - conversation decides what to cut.
- **Many-to-one synthesis is normal.** A rule can be supported by multiple lore entries. Some rules are pure preference with no lore at all (fine - middle ground).

## When the user asks to add a rule

User says: "let's add a rule about X" or "remember to do Y" or similar.

1. **Clarify scope.** Is this a personal behavior (true for this user, not necessarily others) → L0? Or universal knowledge (true for any user) → lore (non-behavior category)?
2. **Search for existing lore.** Run `~/.brain/scripts/recall.py "<topic>"` to surface anything already captured. If a behavioral lore exists, the rule may just need wording from it. If a non-behavioral lore exists that's relevant, consider whether the rule and the lore should both exist.
3. **Draft the rule.** Concise, imperative, one bullet. Match the voice of existing CLAUDE.md.
4. **Capture backing lore (if there's a real lesson).** If the rule comes from an incident or learned pattern, write a `category: behavior` lore entry capturing the origin. Skip if it's pure preference.
5. **Show the diff.** Propose the addition (and lore if applicable). User approves or redirects.
6. **Apply.** Edit CLAUDE.md, write lore. Commit lore to `~/.brain` (`~/.claude/` isn't versioned).

## When the user asks to update a rule

1. **Find the rule** in CLAUDE.md.
2. **Find backing lore** via `recall` for the rule's topic. Read the top behavioral candidates.
3. **Draft the revision** considering original lore context.
4. **If wording diverges meaningfully from lore, also revise the lore** (bump `updated`).
5. **Show the diff.** User approves.
6. **Apply.** Commit lore.

## When the user asks to audit / clean up CLAUDE.md

Run `python3 ~/.brain/scripts/audit-l0.py`. Surfaces:

- **Token count vs ~2K soft cap.** If over, prioritize merging or trimming.
- **Provenance candidates** per rule (top-3 BM25 from behavioral lore). Rules with no behavioral matches: either pure preferences (leave alone) or backing-missing (capture next time the rule is revised).
- **Merge candidates** (BM25-similar rule pairs in CLAUDE.md). Worth considering whether two rules should be one.
- **Stale behavioral lore** (>6 months unchanged). Ask: still relevant? Should the behavior have evolved?

Walk through findings with the user. Apply changes only on approval.

## When the user asks to remove a rule

1. **Confirm** which rule.
2. **Delete the bullet** from CLAUDE.md.
3. **Backing lore stays** as historical record. No "deprecated" marker; the absence of a current rule speaks for itself. Lore can still inform Claude via `recall` for related future work.

## What this workflow does NOT do

- **No automatic compilation.** CLAUDE.md is written by Claude in conversation, not by a script. Voice, wording, and judgment are conversational.
- **No enforcement of provenance.** Rules without backing lore are reported, not rejected.
- **No automated rule merging.** Audit surfaces candidates; conversation merges (or doesn't).
- **No staleness expiration.** Old lore is flagged for review, never auto-deleted.

## Why no compiler?

A compile-from-lore approach was considered and rejected. Reasons:
- CLAUDE.md is *behavioral* - voice and nuance matter. Auto-merge can't preserve them.
- Auto-merging "when semantically related" requires LLM judgment at compile time - slow, expensive, non-deterministic.
- Compile-time loses the conversational moment where the user actually decides what they mean.

The conversational approach uses Claude's existing intelligence. The "compiler" is just Claude doing what it already does, with the right inputs (audit output + recall-surfaced lore) and the user in the loop.
