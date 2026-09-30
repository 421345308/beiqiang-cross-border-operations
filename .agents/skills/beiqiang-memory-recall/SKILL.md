---
name: beiqiang-memory-recall
description: Read the smallest relevant Beiqiang memory set for accepted preferences or prior decisions not already covered by AGENTS, SOP or project records. Read-only; ordinary tool tasks do not require project memories.
---

# Beiqiang Memory Recall

## Required reads

- None. Memory lookup is conditional on a task needing an unstated prior decision; then read the protocol and index below.

The sole library is `07_知识库与Skills/05_项目记忆系统/`.

1. When the task needs an unstated preference, authorization or prior decision, read `README.md` and `INDEX.md`; reuse unchanged content already read. Ordinary tool tasks need neither.
2. Select by task and object, then read only entries whose `scope` matches. Use only `active` entries for current guidance; `superseded`, `disputed` and `archived` are traceability material, not default instructions. Follow `supersedes` to prevent an older entry from re-entering the current set.
3. Check `type` and `source` before applying a claim. Facts need source evidence; preferences need a confirmed choice; authorizations require the exact action and recipient; experiences remain conditional advice. `source: pending` never justifies broadening external or paid action. Apply `verify_when` or `review_after` as a prompt to recheck, not automatic invalidation.
4. Use root and applicable local `AGENTS.md` for shared identity, claims and present boundaries. Verify volatile platform, SKU, CRM, GPU and price facts at the business source before acting; old snapshots are not current state.
5. Mention only entries that materially changed the decision. Keep private and unrelated memories out of output.

This skill never writes. Use `beiqiang-memory-curator` only when memory maintenance is requested; do not turn ordinary task results into durable entries.
