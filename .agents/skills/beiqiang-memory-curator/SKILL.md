---
name: beiqiang-memory-curator
description: Maintain Beiqiang memories when the user requests remembering, updating, consolidating, or removing obsolete entries. Preserve evidence and keep the index small; never capture ordinary conversation automatically.
---

# Beiqiang Memory Curator

## Required reads

- Read the [memory protocol](../../../07_知识库与Skills/05_项目记忆系统/README.md) and [index](../../../07_知识库与Skills/05_项目记忆系统/INDEX.md) for affected entries.

Read `07_知识库与Skills/05_项目记忆系统/README.md` and `INDEX.md`; reuse unchanged versions already read in the task. Read only affected entries unless the user asks for a full audit.

## Authorization

- For a new durable fact, classification or promotion, present concise candidates with source, actual scope, destination, privacy and exclusions; obtain confirmation before writing. AI output alone is not evidence.
- An explicit request to clean, consolidate or remove obsolete memories authorizes that maintenance within its stated scope. Do the review and edits without asking again. Do not use cleanup authorization to add unconfirmed facts or promote experiences into rules.
- Honor the user's latest scoped authorization. Routine conversation remains outside automatic memory capture.

## Maintain

- Keep one concise statement per fact and link the original SKU, CRM, SOP or project evidence. Remove duplicated instructions, stale status copies and conclusions fully covered by a retained entry.
- Do not infer obsolescence from age. Preserve useful historical evidence and unique accepted decisions; label dynamic facts by their actual last verification date.
- For confirmed obsolete content, delete directly without a new backup, as the owner requested on 2026-09-08. Resolve deletion targets and verify they stay within the authorized directory first.
- Use the single metadata protocol in the README: stable `id`, actual `scope`, honest `source`, status and the seven retained descriptive fields. Add `supersedes`, `verify_when` or `review_after` only when they affect reading. Do not create empty taxonomy branches.
- Treat `Authorization`, `Preference`, `Decision` and `Experience` differently. Do not infer global scope, fabricate a source, expand an old authorization or convert a candidate experience into a rule. Mark an unlocated original source `pending` and keep the uncertainty visible.
- When a retained entry explicitly replaces another, mark the old entry `superseded` and remove it from the default index; if it has no independent evidence value, delete it and avoid a dangling `supersedes` pointer.
- Update `INDEX.md` and affected active links in the same change. Keep existing timestamps unless facts or preferences were newly confirmed; formatting and deduplication are not new evidence.
- Verify IDs, index coverage, scope, source paths, replacement relations, references, metadata and depth. Report material merges/deletions and remaining uncertainties.
- Git 提交、推送与隔离边界统一执行根 [AGENTS.md](../../../AGENTS.md#记忆维护与-git)；本 Skill 不另设提交许可规则。
