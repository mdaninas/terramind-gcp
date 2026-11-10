# Terramind icon generation

Edit target: [selected Neural Cube logo](terramind-option-3-neural-cube.png).

Result: [isolated symbol](terramind-icon.png), a 1254 x 1254 RGBA PNG.

Generation method: built-in image generation in edit mode, with the selected logo
supplied as a local reference and transparent background enabled. The runtime
512 pixel icon, 180 pixel touch icon and multi-resolution ICO are format and size
exports of this symbol.

## Final generation prompt

```text
Use case: precise-object-edit.
Asset type: square web icon and favicon source for Terramind.
Input image: the selected Terramind Neural Cube logo, used as the edit target.
Primary request: extract only the existing cube emblem from the left side of this logo and remove the entire "Terramind" wordmark. Preserve the cube design faithfully: the same diamond-shaped violet top face, deeper-violet left face, teal right face, overall hexagonal isometric silhouette, transparent face-separation channels, and three round negative-space nodes connected through the center. Do not redesign, rotate, mirror, or change the number of faces or nodes.
Composition: a single isolated icon on a square canvas, centered both horizontally and vertically, filling about 84 percent of the canvas height, with equal practical transparent margins on all sides. The cube must not be cropped. Keep the top and bottom vertices intact.
Style: crisp clean flat vector-style edges and simple solid-color facets, suitable for favicon downsampling.
Backdrop: actual transparent background with alpha. Node holes and face-separation channels must remain transparent, not black or white paint.
Constraints: edit only by isolating the symbol, removing the wordmark and reframing it for a square icon. Keep the selected logo's visual identity and palette. No text, labels, extra shapes, border, shadow, glow, gradient, texture, checkerboard, mockup, or watermark.
```
