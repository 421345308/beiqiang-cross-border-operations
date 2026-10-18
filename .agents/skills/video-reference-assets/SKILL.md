---
name: video-reference-assets
description: Prepare and review reusable character, animal, product, prop and location references before AI video generation. Use for multi-view identity or wardrobe assets, separate empty scenes and shot composites; not ordinary one-image posters or video editing.
---

# Video Reference Assets

Use this project capability when preparing references for AI video, including a new story or repairing inconsistent characters, clothing, props or scenes.

Read the [video entry](../../../05_内容与视频/AGENTS.md) and the current PROJECT.md. The user's story, style, product, model/provider and authorization come from that project; this skill does not select them.

## Asset and shot preparation

Read the [asset preparation protocol](../../../07_知识库与Skills/04_AI视频知识体系/ai-video-learning-system/references/reference-assets.md) when creating or revising a reference package. It owns the asset/shot distinction, manifest fields, continuity checks and validator usage; do not maintain a second copy here.

- Separate identity/wardrobe, actual product, prop structure, empty location and composed shot references. A pleasing shot is not by itself a reusable character asset.
- Use sufficient views for the intended turns, occlusions and product angles. Keep one identity across those views and distinguish observed product details from invented hidden surfaces. Multi-view references reduce missing information; they do not establish deformation-free video.
- Use the installed imagegen skill for generated raster assets. Inspect supplied local references before editing, label their roles, and persist selected outputs inside the video project. Keep original product evidence read-only.
- Before a composite, define its actor/object states and the input mapping: who, wardrobe, old/new product, where, time/light, object orientation, gaze, contact and intended action. Exclude grids/labels/studio backgrounds from output.
- Review the resulting pixels against the source references, then record visual_review. A filesystem or manifest pass is not visual or video acceptance.
- Maintain one current asset manifest and one current shot manifest linked by PROJECT.md. Replace obsolete active selections and repair their consumers; preserve original evidence or inputs only when they still have a stated purpose.

## Supported execution and checks

Use [validate_reference_assets.py](../../../08_工具链/02_视频工具/资产准备/validate_reference_assets.py) on the asset manifest, and add --shots for the shot manifest. Read --help on first use. It checks references, hashes, metadata, role use, continuity-state conflicts and missing review fields. It cannot inspect anatomy, identity, light, physical contact or commercial appeal.

For Seedance, the chosen-version official guide and actual provider schema control input limits, reference roles and keyframes. A multi-view sheet used as identity is not a first frame or a storyboard. Do not assume a grid will be cropped or interpreted correctly without explicit mapping.

Prepare paid execution only after the reviewable package and actual quote exist; the root/video entry governs authorization. This skill adds no permission to generate, upload or publish.

## Output

Update the project's stable entry with the selected assets, shots, exact prompts, known defects and next step. Keep shared methods here/in the protocol; individual faces, garment designs, products and model results stay in that project.
