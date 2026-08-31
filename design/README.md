# Baton design system

Sage base, amber for attention, red reserved for urgency. Two postures — a field app used
one-handed outdoors, and a portal used at a desk — sharing one set of tokens.

## Files

| Path | What it is |
|---|---|
| `tokens.css` | The single source of truth. Color, type scale, spacing, radius, tap targets, motion. Light and dark. |
| `build.py` | Generates the standalone previews, inlining tokens so each renders on its own. |
| `preview/` | Generated. Do not edit by hand — edit `tokens.css` or `build.py` and rebuild. |

```bash
python design/build.py
```

## Rules this system enforces

- Every text pair is measured at **4.5:1 or better**; every interactive boundary at **3:1 or
  better**. Ratios are printed on the foundations page so they can be checked, not trusted.
- Tap targets are **56px in the field app** and 44px in the portal — deliberately above the WCAG 2.2
  floor of 24px, because volunteers work one-handed, outdoors, and many are over 60.
- Body text is **18px in the field app**.
- Status is never carried by color alone. Every state has a word and a shape beside it.
- Motion is structural. All of it collapses under `prefers-reduced-motion`.
- Saturation is a scarce resource. Most of the interface is neutral; red means a human must look now.

Rationale for each of these is in [`../docs/design-principles.md`](../docs/design-principles.md).
