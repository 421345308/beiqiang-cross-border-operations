# Prompt Framework

## Structure

Write prompts in this order:

1. Platform, audience, duration, and style.
2. Product identity lock.
3. One primary product message.
4. Time-coded shot plan.
5. Camera and editing language.
6. Original music and synchronized sound effects.
7. Caption-safe negative space.
8. Negative constraints.

## TikTok Pattern

- `0.0-1.2s`: Pattern interrupt showing the product benefit immediately.
- `1.2-3.5s`: Close visual proof.
- `3.5-7.0s`: On-foot or hand interaction.
- `7.0-10.0s`: Second proof or contrast.
- Final seconds: Hero frame or loop transition with CTA space.

Use cuts every 1.5-3 seconds. Keep the product large in frame.

## Wide-Toe Visual Proof

Prefer visible evidence instead of written claims:

- Top-down forefoot silhouette.
- Hand tracing or lightly pressing the forefoot width.
- Natural on-foot toe-area close-up.
- Stable comparison framing only when both compared objects are real references.

Do not show transparent feet, internal anatomy, pain acting, measurements, or medical claims.

## Product Identity Lock

Describe exact visible features from the references:

- Color.
- Knit or textile pattern.
- Lace color and routing.
- Collar and heel tab.
- Outsole color, texture, and profile.
- Logo placement when present.

Repeat that these features must remain identical in every shot.

## Music Prompt

Specify:

- Original instrumental.
- BPM range.
- Genre blend.
- Main percussion and bass.
- Energy level.
- No vocals or recognizable melody.
- Beat-synchronized actions and realistic product sounds.

Example direction:

```text
Original 112 BPM upbeat indie-pop with light nu-disco and subtle UK-garage percussion, crisp kick, soft handclaps, bright clean bass, airy synth pluck, no vocals, no recognizable copyrighted melody.
```

## Negative Constraints

Always reject:

- Text generation.
- Product redesign or color drift.
- Changing laces, outsole, logo, or stitching.
- Extra or duplicated shoes.
- Deformed hands, feet, or gait.
- Impossible bending or floating.
- Fake factories, tests, reviews, certificates, prices, and claims.

## Lessons From BQ017

- A slow product turntable is too simple for TikTok.
- Add a first-second pattern interrupt, multiple proof shots, on-foot movement, and beat-synchronized editing.
- Verify the returned model ID; the first trial accidentally used Mini instead of full Seedance 2.0.
- Multiple clean references improve identity, but avoid detail images containing text or unrelated graphics.
- Generated text should be avoided; add captions in post-production.

## Lessons From BQ001

- Even with a `no text` instruction, the model may add fake typography in the final hero frame. Require an entirely blank background with no signs, labels, letters, symbols, or graphics.
- A foot-entering-shoe action can deform the heel collar and foot. Prefer shots where the shoe is already worn, or use real footage for the slip-on demonstration.
- One reference angle is insufficient for a product with a distinctive knit pattern and sculpted outsole. Use clean same-color top, side, three-quarter, and outsole references.
- The wide-forefoot hook and hand-press proof read clearly; retain those structures.
- Front-facing on-foot walking can enlarge or simplify the white toe bumper. Prefer low side or three-quarter walking angles and keep identity-critical claims on exact product-only footage.
- Use lifestyle generation as a short insert between accurate product shots, not as the sole product proof.
