---
name: beiqiang-seedance-video
description: Create, generate, review, and iteratively improve Beiqiang footwear product videos with the Volcengine Ark Doubao Seedance API. Use when Codex needs to turn a Beiqiang SKU's local product images into TikTok or Alibaba.com videos, write Seedance prompts, add original overseas-facing music, verify the exact Seedance model and cost, download results, or record post-generation quality lessons for the next video.
---

# Beiqiang Seedance Video

Create B2B footwear videos from real Beiqiang product evidence. Optimize for overseas importers, wholesalers, online sellers, sourcing agents, and private-label buyers.

## Required Inputs

- Identify the SKU and locate its final-upload product folder.
- Read confirmed product facts before writing claims.
- Use `beiqiang-positioning` and `tiktok-b2b-content` as guardrails.
- Read `references/prompt-framework.md` before creating a new prompt.
- Read `references/review-template.md` before reviewing a generated video.
- Use `video-use` and its `references/video-visual-qa.md` for the actual contact-sheet, focused-candidate, original-resolution, and time-range QA mechanics. This Skill adds footwear/product truth; it does not duplicate the model-agnostic review procedure.

## Workflow

1. Inspect the SKU's main image, color images, detail images, and confirmed listing facts.
2. Define one primary visual message. Do not combine more than two product benefits in one short video.
3. Choose platform:
   - TikTok: `9:16`, native creator pacing, strong first-second hook.
   - Alibaba.com: `16:9`, slower inspection pacing, product and order evidence.
4. Use real product images as strict identity references.
5. Write an English Seedance prompt using the prompt framework.
6. Use original instrumental music and realistic sound effects. Do not imitate known songs or artists.
7. Submit with the workspace generator:

```powershell
python .\08_工具链\02_视频工具\seedance_video\seedance_generate.py create `
  --prompt-file "<PROMPT_FILE>" `
  --image-file "<LOCAL_IMAGE>" `
  --model "doubao-seedance-2-0-260128" `
  --ratio "9:16" `
  --resolution "720p" `
  --duration 12 `
  --generate-audio
```

8. Poll until success and download the MP4 immediately.
9. Verify the returned JSON before reporting success:
   - `model` must equal the intended model.
   - Confirm resolution, ratio, duration, FPS, audio, token use, and file existence.
10. Run the `video-use` whole-video scan, inspect suspicious focused candidates at original resolution, complete the QA artifacts, and save the retrospective with the current SKU video project's deliverables. Do not recreate a generic output folder at the workspace root.
11. Convert concrete failures into the next prompt's explicit constraints.
12. When a publishable edit is requested, use `video-use` for trimming, real English overlays, music mixing, platform-safe subtitles, final rendering, and cut-boundary QA. Seedance generates source clips; `video-use` performs post-production.

## Model Gate

- Default to full `doubao-seedance-2-0-260128`.
- Never silently use Mini, Fast, 1.5, or 1.0.
- Use another model only when the user explicitly requests it.
- Before a paid generation, run a no-cost empty-content permission probe when model access is uncertain.
- After generation, verify the actual returned model ID. Do not rely on the requested command alone.

## Product Truth Rules

- Preserve shoe silhouette, outsole, upper texture, stitching, laces, logo, color, and proportions.
- Do not invent factories, workers, tests, certificates, reviews, capacity, materials, packaging, prices, MOQ, or delivery promises.
- Use AI for product motion, lifestyle, camera movement, backgrounds, and transitions.
- Use real footage for factory, inspection, packing, warehouse, and compliance proof.
- Avoid medical, orthopedic, pain-relief, waterproof, or certification claims without evidence.

## Music Rules

- Prefer original instrumental music with a clear beat for TikTok.
- Specify BPM, percussion, bass, energy, transitions, and synchronized product sound effects.
- Use no lyrics by default so the video works across the US and Europe.
- Do not request a recognizable melody or imitation of a known artist.
- For paid TikTok advertising, replace generated music with a properly licensed Commercial Music Library track when needed.

## Mandatory Review

Score every generated video for:

- Product identity consistency.
- First-second stopping power.
- Visual proof of the intended benefit.
- Human anatomy and physical realism.
- Editing rhythm and music synchronization.
- B2B relevance and CTA space.
- Platform fit.

Record defects even when the overall result is acceptable. Each defect must link to a time range and use the shared `PASS` / `MINOR` / `MODERATE` / `SEVERE` / `CRITICAL` severity and `KEEP` / `TRIM` / `REGENERATE` action vocabulary. Each next prompt must address the highest-impact two defects without turning the entire QA list into prompt bloat.

## Output Contract

Return:

```text
SKU:
Platform:
Primary message:
Actual model:
Video specifications:
Token use and estimated cost:
Output file:
What worked:
Problems found:
Next prompt improvements:
Suggested English caption and hashtags:
```
