# Terramind brand assets

The selected project identity is the Neural Cube: violet and teal infrastructure
faces with three connected nodes. The full logo appears in the project README
and in the report page header. The isolated symbol supplies the browser favicon
and touch icon.

| Asset | Purpose |
| --- | --- |
| [terramind-logo.png](terramind-logo.png) | Selected full logo, 2172 x 724 transparent PNG |
| [terramind-logo-dark.png](terramind-logo-dark.png) | Light wordmark variant for dark README backgrounds |
| [terramind-icon.png](terramind-icon.png) | Generated isolated symbol, 1254 x 1254 transparent PNG |
| [Packaged logo](../../src/terramind/api/assets/terramind-logo.png) | Same full logo served at /assets/terramind-logo.png |
| [Packaged icon](../../src/terramind/api/assets/terramind-icon.png) | 512 x 512 PNG for browser icons |
| [Favicon](../../src/terramind/api/assets/favicon.ico) | ICO with 16, 32, 48, 64 and 256 pixel sizes, served at /favicon.ico |
| [Touch icon](../../src/terramind/api/assets/apple-touch-icon.png) | 180 x 180 PNG for saved browser shortcuts |

Use the matching wordmark variant for light or dark backgrounds. Keep its
proportions and preserve the transparent background. The web page uses local
assets with no external image requests.

Generation used the built-in image tool. The selected design and exact prompts
are recorded in [logo options](logo-options-generation.md),
[icon generation](icon-generation.md) and
[dark-background variant](logo-dark-generation.md). Runtime icon exports use
resampling and ICO encoding without changing the generated design. Earlier
concepts are retained as design references.

## Local verification

The full quality gate (`uv run --locked python scripts/check.py`) passed with
297 tests. Package builds passed, and the four runtime image files were verified
inside the wheel with matching hashes.

Browser checks at 1440 x 1080 and 390 x 844 confirmed the header image loads with
no horizontal overflow. The synthetic preview-to-report flow still works, with
no browser console errors on the report pages. The ICO, PNG browser icon and touch
icon all returned HTTP 200 and decoded in the browser. A local README layout
preview selected and rendered the correct logo in both light and dark modes.

These checks used offline synthetic data. The branding changes have not been
deployed to the cloud.
