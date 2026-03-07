# Screenshot Assembly

How the README screenshot (`docs/vibecheck-screenshot-logo.png`) is built.

## Source Files

| File | Purpose |
|------|---------|
| `vibecheck-screenshot.png` | Base screenshot — terminal (left) + phone via scrcpy (right), trimmed |
| `vibecheck-logo.svg` | ASCII-art logo in SVG (gradient gold-to-red, monospace text) |
| `vibecheck-logo.png` | Pre-rendered PNG of the logo (2520x520) |
| `vibecheck-screenshot-logo.png` | Final composite — logo overlaid on screenshot |

## Live Preview

Use `feh` with auto-reload to watch the overlay file update as you iterate:

```bash
feh --auto-reload docs/vibecheck-screenshot-logo.png
```

Every time the file is overwritten, feh refreshes automatically.

## Assembly Process

### 1. Trim black bars from source screenshot

The raw screenshot may have black bars on left/right edges. Detect and trim them:

```python
from PIL import Image
import numpy as np

img = Image.open('docs/vibecheck-screenshot.png')
arr = np.array(img)

# Average brightness per column (RGB channels)
col_brightness = arr[:, :, :3].mean(axis=(0, 2))

# Find first/last non-black columns (threshold=10)
left = next(i for i in range(arr.shape[1]) if col_brightness[i] > 10)
right = next(i for i in range(arr.shape[1] - 1, -1, -1) if col_brightness[i] > 10)

trimmed = img.crop((left, 0, right + 1, img.height))
trimmed.save('docs/vibecheck-screenshot.png')
```

Current trim: 48px left, 47px right + 1px extra right for even width → 864x520.

### 2. Render logo at target size

The logo SVG is wide (2520x520). Scale it to ~48% of screenshot width so it fits within the terminal panel without bleeding into the phone panel:

```bash
# Requires librsvg
rsvg-convert -w 414 docs/vibecheck-logo.svg -o /tmp/logo-scaled.png
```

The phone panel starts around column 528 of the trimmed screenshot. Keep the logo under that.

### 3. Composite with drop shadow

```python
from PIL import Image, ImageFilter
import numpy as np

screenshot = Image.open('docs/vibecheck-screenshot.png')
logo = Image.open('/tmp/logo-scaled.png').convert('RGBA')

# Create black shadow from logo alpha
logo_arr = np.array(logo)
shadow_arr = np.zeros_like(logo_arr)
shadow_arr[:, :, 3] = logo_arr[:, :, 3]
shadow = Image.fromarray(shadow_arr)
shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))

overlay = screenshot.copy().convert('RGBA')
x, y = 6, 10

# Double-paste shadow for heavier effect
overlay.paste(shadow, (x + 3, y + 3), shadow)
overlay.paste(shadow, (x + 2, y + 2), shadow)
overlay.paste(logo, (x, y), logo)

overlay.convert('RGB').save('docs/vibecheck-screenshot-logo.png')
```

## Current Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Logo width | 48% of screenshot (414px) | Fits within terminal panel |
| Logo position | (6, 10) | Slight inset from top-left |
| Shadow blur | 6px Gaussian | Double-layered for heavier effect |
| Shadow offset | +2/+3 px | Two passes at slightly different offsets |
| Screenshot size | 864x520 | After trimming black bars |

## Regenerating the Logo SVG

The logo is ASCII art rendered as monospace SVG text with a gold-to-red gradient (one color per line):

- Line 1: `#ffd700` (gold)
- Line 2: `#ffaf00`
- Line 3: `#ff8700`
- Line 4: `#ff5f00`
- Line 5: `#ff0000` (red)

Edit `vibecheck-logo.svg` directly. Re-render with `rsvg-convert`.
