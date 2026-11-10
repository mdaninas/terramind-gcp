# Terramind dark-background logo generation

Edit target: [selected Neural Cube logo](terramind-option-3-neural-cube.png).

Result: [dark-background logo](terramind-logo-dark.png), a 2172 x 724 RGBA PNG.

Generation method: built-in image generation in edit mode, with transparent
background enabled. The light wordmark supports the README's dark color scheme.

## Final generation prompt

```text
Use case: precise-object-edit.
Asset type: dark-background wordmark variant of the selected Terramind Neural Cube logo.
Input image: selected logo is the edit target.
Primary request: change ONLY the color of the "Terramind" wordmark from dark charcoal to very light neutral #F5F7F7 so it is clearly readable on dark website or repository backgrounds.
Invariants: preserve the selected Neural Cube symbol exactly, including its violet top and left faces, teal right face, three connected transparent node cutouts, proportions and geometry. Preserve the exact word "Terramind", capitalization, letter shapes, typeface, weight, kerning, baseline, wordmark size, alignment and spacing relative to the icon. Preserve the same wide horizontal layout and overall canvas proportions.
Backdrop: keep the existing background truly transparent with alpha, including the node cutouts and channels. Do not paint a dark background.
Constraints: recolor the wordmark only. No redesign, no additional text, no shape or position changes, no border, shadow, glow, texture, gradient, checkerboard, or watermark.
```
