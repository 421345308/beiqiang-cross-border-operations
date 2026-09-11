---
name: ai-video-learning-system
description: Maintain a layered memory system for AI video projects. Use when starting, continuing, reviewing, or documenting an AI video project; separating project-specific facts from reusable guidance; recording candidate lessons; or deciding whether an observed result is mature enough to promote into shared knowledge. Do not use as a substitute for model-specific prompting or editing instructions.
---

# AI Video Learning System

Build useful memory without turning every past failure into a universal constraint.

## Read in layers

1. Read the current project's record first. It contains the creative goal, approved assets, current baseline, project-specific decisions, results, and next step.
2. Read the technical facts for the model or tool actually being used. Load H3 guidance only for H3 work; do not import it into unrelated video models.
3. Read shared creative guidance only when it affects the present decision.
4. Search the experience ledger for relevant candidate lessons. Treat confidence and scope as evidence, not as commands.

See [knowledge-layers.md](references/knowledge-layers.md) when creating or restructuring a project memory system.

## Write back at the right level

- Record project facts and iteration outcomes in that project's own record.
- When an outcome may generalize, add or update an experience card in [experience-ledger.md](references/experience-ledger.md). Do not copy the entire project history.
- Promote an experience into shared guidance only when its causal mechanism is clear, its scope is stated, and it has either repeated across independent projects or passed a controlled comparison strong enough to justify reuse.
- Keep exact model compatibility, safety, licensing, and cost invariants in the relevant technical guide. These may use firm language because violating them has a concrete failure mode.
- Remove superseded active guidance rather than stacking the new statement beside the old one. Preserve only the evidence needed to explain the current conclusion.

Use [project-record-template.md](references/project-record-template.md) when a new AI video project needs a durable record.

## Keep generation editable and inspectable

For node-based or API-driven generation, read [workflow-transparency.md](references/workflow-transparency.md). Before a paid or long-running generation is submitted, preserve an inspectable generation package containing the exact prompt, the canonical workflow identity, all exposed parameters, reference-asset roles, and the intended single-variable change. A rendered video without this package is a preview, not a reproducible project candidate.

Keep model-specific node compatibility in the model's central technical guide. Project folders point to that canonical workflow and store only the exact prompt, resolved run manifest, candidate output, and review result; they do not become competing workflow authorities.

## Prefer causal guidance

Write reusable knowledge in this shape:

`Observed condition → likely mechanism → likely consequence → preferred approach → scope or exception → evidence/confidence.`

Prefer “A tends to cause B, so start with C when D matters” over “never do A.” Do not paste the whole knowledge base into a generation prompt. Use knowledge to choose assets, mode, shot design, and a small number of relevant positive instructions.

When multiple approaches remain reasonable, preserve creative choice. A prior failure in one project is not a universal rule unless evidence supports that promotion.

## Close each iteration

Before ending a material video iteration:

- identify the accepted baseline and what changed;
- record observable results, including unchanged strengths and regressions;
- separate confirmed cause from hypothesis;
- update or reject any affected experience cards;
- leave one concrete next step in the project record;
- keep generated media and technical logs out of shared guidance unless they are evidence linked from a concise card.
