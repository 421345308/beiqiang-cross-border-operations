---
name: beiqiang-seedance-video
description: Prepare, generate and review Beiqiang footwear videos with a user-selected Seedance version and execution platform. Use for product-reference planning, model research, prompts, generation and footwear QA; channel, language and model come from the current project.
---

# Beiqiang Seedance Video

## Scope and required context

Applies to Beiqiang footwear work using Seedance. It does not select the version, provider, channel, audience, language, style or runtime for a new project. The old overseas TikTok / English / Seedance 2.0 Ark setup was a project configuration, not a continuing default.

Read the [video entry](../../../05_内容与视频/AGENTS.md), current `PROJECT.md` and exact SKU/source evidence. Use [positioning](../beiqiang-positioning/SKILL.md) only when resolving a buyer-facing claim or audience decision; use [short-video content](../tiktok-b2b-content/SKILL.md) when writing that content. Adjacent skill links do not require loading unrelated workflows.

Take confirmed audience, channel, language, model and execution platform from the current user instruction and project. Ask only for consequential missing choices. Put these choices in the project record, not back into this general skill.

## Preparation and model selection

- Inspect real product references before assigning shoes to scenes. Confirm which visible structures and product facts can support the intended message.
- Research the chosen version through current primary documentation and the actual provider's schema/help: supported reference modes, control granularity, durations, ratio, resolution, sound, cost and material restrictions. A provider's display name alone does not prove the exact upstream build.
- Separate documented capability, project observations and untested creative risks. Historical success or failure on another version/provider does not establish current behavior.
- Design characters, settings, actions and camera work together with the available product evidence. Preserve room for creative alternatives; neither a previous shot pattern nor the model's maximum duration dictates the film structure.
- Before writing generation prompts, read [prompt guidance](references/prompt-framework.md). Consult [template mapping](references/template-mapping.md) only when borrowing a template.

## Execution routing and authorization

Use the execution platform selected for the current task:

- **LibTV selected:** use the configured official `libtv-cli` skill and CLI. Discover the chosen model with `libtv model search`, then read its full schema. Keep canvas operations and assets in that route; do not substitute Ark or raw HTTP.
- **Volcengine Ark selected:** inspect `08_工具链/02_视频工具/seedance_video/seedance_generate.py --help` and current Ark documentation before using that client. Confirm it supports the chosen version and input mode. A historical command containing `doubao-seedance-2-0-260128` is not authority to run 2.0 now.
- **Another provider selected:** verify its current tool/interface and supported model identity before submitting. Do not silently change model, variant, provider or price tier.

Paid video authorization follows the workspace/video entry. Research approval or choosing a model does not authorize paid generation. Before submission, preserve the exact prompt, reference roles, exposed settings, intended model and available cost evidence in the project package. Use a draft/test only when appropriate and authorized; its result is not final-quality acceptance.

## Product truth and review

Apply the root `AGENTS.md` product/source/claim rules. Preserve the intended shoe's silhouette, texture, laces, stitching, sole, color and proportions. Lifestyle acting and concept visualization may serve a commercial story; they do not prove factory operations, customer testimony or performance. Footage offered as real manufacturing or testing evidence must have that provenance.

Define acceptance for the current purpose: attractive moving images and rhythm, product readability and identity, believable anatomy/contact, coherent scenes, sound, brand communication and platform fit. Do not equate render success or one good frame with a usable ad.

For generated-video review, read [review guidance](references/review-template.md) and the available `video-use` visual-QA reference. Inspect the full timeline and suspicious actions, link time ranges and source IDs, and separate observations from creative preferences. Check sound explicitly; do not infer it from stills or an audio stream's existence.

Record the requested and returned model identity, actual specifications, output, usage/cost evidence, defects and next decision in the project. If the provider does not disclose a field, mark it unverified. Use the requested language for narration/captions; choose licensed or authorized sound appropriate to that channel. Editing and export use the task's selected tool; `video-use` is an available route, not a mandatory replacement for a chosen editor.
