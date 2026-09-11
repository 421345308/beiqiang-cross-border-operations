---
name: remotion-best-practices
description: Create, edit, preview, render or upgrade Remotion videos in the Beiqiang workspace. Select only the relevant mode reference; this project entry retains the newer local guidance alongside the installed Remotion plugin.
metadata:
  upstream-version: "4.0.522"
---

# Remotion workspace routing

Use this single project entry for Remotion work. Its mode documents are references, not separately installed skills. Read only the row needed for the current task; do not load the whole bundle or the plugin's equivalent instructions again.

Preserve user edits and inspect the target project's dependencies before using version-specific APIs. This bundle came from Remotion 4.0.522; the installed plugin inspected on 2026-09-11 contains 4.0.506 guidance. Local package versions and current official documentation decide compatibility.

| Task | Read |
| --- | --- |
| New video or composition, including an existing project | [Create](remotion-create/REFERENCE.md) |
| React markup, scenes, timing, media, effects or text | [Markup](remotion-markup/REFERENCE.md) |
| Maps, routes, geographic animation or flyovers | [Maps](remotion-maps/REFERENCE.md) |
| Media metadata, trimming or cropping through Mediabunny | [Multimedia](remotion-multimedia/REFERENCE.md) |
| Elements editable in Studio | [Interactivity](remotion-interactivity/REFERENCE.md) |
| Video export or transparent rendering | [Render](remotion-render/REFERENCE.md) |
| Starting or opening Studio | [Studio](remotion-studio/REFERENCE.md) |
| Transcription, subtitle import, timing or display | [Captions](remotion-captions/REFERENCE.md) |
| Player, rendering service or Remotion application | [SaaS](remotion-saas/REFERENCE.md) |
| Current API documentation | [Docs](remotion-docs/REFERENCE.md) |
| Package or skill upgrade requested by the user | [Upgrade](remotion-upgrade/REFERENCE.md) |

Work inside the selected video project, never scaffold Node projects at the Beiqiang workspace root. Open Studio at its actual returned URL. Package upgrades can recreate duplicate skills; inspect the result and keep one project entry with mode references.
