---
name: beiqiang-memory-recall
description: Read the smallest relevant Beiqiang memory set when a task depends on company context, accepted preferences, or prior decisions. Read-only; ordinary tool tasks do not require business memories.
---

# Beiqiang Memory Recall

The sole library is `07_知识库与Skills/05_项目记忆系统/`.

1. Read its `README.md` and `INDEX.md` at task start. Reuse unchanged content already read in this task.
2. Select by task signal and description; load relevant identity first, then necessary active memories in L1 → L5 order. Do not read the whole library unless explicitly auditing it.
3. Historical context is a pointer to evidence. Verify volatile platform, SKU, CRM, GPU and price facts at the linked source before acting; never present an old snapshot as current.
4. Preserve source boundaries and privacy. Memory weights guide attention, not authority over evidence or the user's latest instruction.
5. Mention only memories that materially changed the decision. Do not restate unrelated memories.

This skill never writes. Use `beiqiang-memory-curator` only when memory maintenance is requested; do not turn ordinary task results into durable entries.
