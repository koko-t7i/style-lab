# Visual Signatures — "What Makes Brand X Look Like Brand X"

Quick-reference catalog of the minimum visual DNA an agent needs to render
something on-brand for the ~10 brands users most frequently name in
style-lab. Each entry is intentionally short: just the identity-defining
moments, not a full design system.

If the user names one of these brands in **Mode C** (brand-tracking), look
here first. If found, skip the brand-DNA-extraction step and use the DNA
below directly. If the brand is **not** in this list, run:

```
python3 scripts/extract_brand_dna.py <official-url> --output /tmp/<brand>-dna.json
```

and use the resulting JSON's `summary` field as your starting point.

---

### Aurpay
- **Palette**: brand gradient `#5B7FFF → #A78BFA` at 135° (blue → purple, primary identity), `bg #FFFFFF`, ink `#121437` (purple-tinted, NOT pure black), muted `#4F507D` (purple-grey).
- **Type**: Inter (sans, all weights). JetBrains Mono for metric numerals and inline code only.
- **Signature visual move**: the blue→purple gradient lives on CTAs, on the literal letters of the wordmark (text-clipped), and as a halo behind the dashboard mock — three placements, always those three.
- **Mood**: confident fintech-Web3, light-native, gradient-led identity that crosses color families instead of staying monochromatic-blue.
- **Reference URL**: https://aurpay.net/

### Stripe
- **Palette**: single saturated indigo-blue `#635BFF` primary, ink `#0A2540`, paper `#FFFFFF`, signature mesh gradient (blue → pink → purple) on big marketing hero backgrounds.
- **Type**: Söhne (display + body) — Inter is the close-enough open-source substitute. Generous tracking on display.
- **Signature visual move**: oversized typographic hero + a realistic product-screenshot mock immediately under it, with the gradient mesh leaking from behind the hero text.
- **Mood**: restrained, confident, "this is serious infrastructure dressed up beautifully" — Stripe never feels like a marketing site.
- **Reference URL**: https://stripe.com/

### Linear
- **Palette**: purple primary `#5E6AD2`, dark surfaces `#0A0A0F → #1C1C24`, ink-on-dark `#E0E0E5`, accent gradients used sparingly (purple → pink on landing).
- **Type**: Inter Display + Inter Body. Berkeley Mono / JetBrains Mono for technical bits.
- **Signature visual move**: very small corner radii (4–6px), almost zero shadow elevation, dense typography, monospace accents for keyboard shortcuts and code-like UI strings.
- **Mood**: "designed by engineers, for engineers" — tight, considered, dark-mode-native.
- **Reference URL**: https://linear.app/

### Vercel
- **Palette**: pure black `#000000` background, pure white `#FFFFFF` text, rainbow / mesh gradient on the wordmark + hero accent (Geist Gradient).
- **Type**: Geist Sans (display + body), Geist Mono for terminal/code blocks.
- **Signature visual move**: black canvas + the geometric triangle logo + gradient chrome on otherwise-monochrome page. Terminal/code blocks are prominent first-class UI.
- **Mood**: minimalist developer-tools aesthetic, "the deploy is the product".
- **Reference URL**: https://vercel.com/

### Coinbase
- **Palette**: Coinbase Blue `#0052FF` primary, paper `#FFFFFF`, ink `#0A0B0D`, neutral grey scale (`#F5F8FA`, `#D8DCE0`), trust-green `#05B169` for positive numerics.
- **Type**: Söhne / Inter (display + body). Big legible numerics with tabular-nums.
- **Signature visual move**: 8–12px rounded corners on every container, very large balance numbers ($X,XXX.XX) as the visual centerpiece, prominent trust signals (insured, regulated badges).
- **Mood**: serious-money UI, restrained palette, "your custody, our chrome".
- **Reference URL**: https://coinbase.com/

### Datadog
- **Palette**: Datadog purple `#774AFF` primary, dark dashboard surface `#1B1C2A → #2D2D44`, accent colors for chart series (green, blue, yellow, red — high-contrast on dark), light mode also ships with paper `#FAFAFA`.
- **Type**: Söhne / Inter (display + body). Mono for log lines, metric values, sparkline labels.
- **Signature visual move**: 4-column data dashboards filled with multi-panel mock layouts, sparklines everywhere, density that looks like a real production observability tool (not a marketing site).
- **Mood**: technical density signals "this can handle your scale", earned legitimacy through information density.
- **Reference URL**: https://datadoghq.com/

### Notion
- **Palette**: cream/off-white `#F7F6F3` background, ink `#37352F` (warm dark, NOT pure black), tiny accent palette (red, orange, yellow, green, blue, purple, pink, brown, grey — Notion's named highlight colors).
- **Type**: Inter (body) often paired with a serif for editorial / headline moments. Lots of emoji used as page icons.
- **Signature visual move**: cream background + 8px+ rounded corners + hand-drawn/sketch-style illustrations + emoji-as-page-marker convention. Sometimes serif headlines mixed with sans body.
- **Mood**: warm, friendly, document-feel — "your workspace is a piece of paper".
- **Reference URL**: https://notion.so/

### Apple
- **Palette**: pure black `#000000` or pure white `#FFFFFF` (one or the other, never beige); a single accent (often Product Blue `#0066CC`) used sparingly; product photography supplies all other color.
- **Type**: SF Pro Display + SF Pro Text. Oversized: 96px+ headline sizes are the norm on marketing pages.
- **Signature visual move**: brutal restraint — a single product photo dominates, surrounded by huge type and nothing else. No decoration, no patterns, no gradients on UI chrome.
- **Mood**: "the product is the hero, everything else gets out of the way".
- **Reference URL**: https://apple.com/

### Arc Browser
- **Palette**: mesh gradients (purple → pink → orange, sometimes cyan/blue accents), paper `#FAF8F5`, ink `#1A1A1A`, no single brand "primary" — the gradient is the brand.
- **Type**: a custom display sans (proprietary) + a body sans. Playful, slightly rounded letterforms.
- **Signature visual move**: oversized rounded corners (24px+), playful illustrations, browser-window mocks displayed at angles or with overlaps, gradient-mesh backgrounds on hero sections.
- **Mood**: "browsing is a creative act" — feels like a Figma file, not a utility.
- **Reference URL**: https://arc.net/

### Anthropic
- **Palette**: caramel/orange `#D97757` accent, paper `#FAF9F5` (warm off-white), ink `#191919`, restrained secondaries (sage, slate).
- **Type**: Tiempos / Source Serif (serif headlines) + Styrene (sans body). Generous line-height (1.7+) on prose.
- **Signature visual move**: document-publication layout — lots of white space, narrow column widths for prose, serif headlines, restrained iconography. Reads like a literary journal more than a tech site.
- **Mood**: thoughtful, considered, "we are publishing ideas, not shipping product".
- **Reference URL**: https://anthropic.com/

---

## How to use

1. **Mode C (brand-tracking) start.** The user names a brand they want to look like ("make it look like Stripe", "Aurpay-style", etc.).
2. **Check this catalog first.** If the brand name appears above, copy the DNA into your working notes and skip step 3.
3. **Fall back to live extraction.** If the brand is not listed, run:
   ```bash
   python3 scripts/extract_brand_dna.py <official-url> --output /tmp/<brand>-dna.json
   ```
   Read the `summary` field of the output JSON — it is composed to be paste-ready into a design brief.
4. **Translate into the variant brief.** For each entry, the *signature visual move* is the non-negotiable: if the rendered variant doesn't carry it, the variant doesn't look like the brand. Everything else (exact hex, exact font weights) is permitted to vary.
5. **When the user wants to *add* a brand to this catalog**, run `extract_brand_dna.py` against the official URL, then hand-edit a new entry following the same 5-bullet format above. Reserve the *signature visual move* line for the single thing that, if removed, breaks brand recognition.
