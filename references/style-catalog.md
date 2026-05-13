# Style Catalog (fallback)

Use this when `ui-ux-pro-max` is **not** installed. If it is installed, prefer it — it has 80+ styles with richer metadata. This file is a curated short list optimized for "pick a direction fast", not exhaustive coverage.

Each entry tells you the visual vocabulary, the colors, the type, the kind of motion, and what product/audience it's actually good for. Use this to render the variant faithfully — not generic "modern" with a different accent.

---

## Safe & Professional

### Minimalism / Swiss Modernism
- **Vocabulary**: white space, geometric grid, sans-serif, sharp edges, no shadows, single accent color
- **Palette**: white #FFFFFF, black #111111, neutral grey #6B7280, **one** strong accent (e.g., red #DC2626 or cobalt #2563EB)
- **Type**: Inter, Helvetica, Söhne. Tight letter-spacing on headlines. Body 16–18px.
- **Layout**: 12-col grid, generous gutters, big margins, hero text-left, features in a clean 3-col row
- **Motion**: subtle 200ms fade/slide on scroll, nothing flashy
- **Best for**: SaaS, B2B, enterprise tools, documentation, professional services
- **Don't use for**: lifestyle, gaming, kids products, anything that needs to feel "fun"

### Editorial Grid / Magazine
- **Vocabulary**: serif headlines, asymmetric grid, image-heavy, clear hierarchy, "this is a publication"
- **Palette**: cream #FAF7F2 or off-white, deep ink #1A1A1A, one muted accent (terracotta, navy)
- **Type**: serif display (Playfair, Fraunces, GT Sectra) + clean sans body (Inter)
- **Layout**: oversized headline, drop-cap-style intro, multi-column body, large pull quotes
- **Best for**: media, premium brands, agencies, content platforms, longform products

---

## Modern & Trendy

### Glassmorphism
- **Vocabulary**: frosted blur panels, layered translucent cards, soft glow behind content, vibrant gradient background
- **Palette**: gradient backgrounds (purple→blue, pink→orange), glass panels with `backdrop-filter: blur(20px)` and 10–15% opacity white/black
- **Type**: clean sans, medium weight, white or near-white
- **Effects**: `backdrop-filter: blur(20-30px); background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2)`
- **Motion**: hover lifts panels, parallax on background gradient
- **Best for**: AI products, fintech, modern consumer apps, anything that wants to feel "of the moment"
- **Don't use for**: enterprise, accessibility-critical (low contrast issues)

### Bento Grid
- **Vocabulary**: large rounded rectangles in an asymmetric grid, each tile shows one feature with a custom illustration/animation, Apple-style
- **Palette**: light or dark base, each tile can have its own subtle tint
- **Type**: large, friendly sans (SF Pro vibe — Inter or Geist work)
- **Layout**: 2–4 column irregular grid, tiles span 1–2 cols and 1–2 rows, heavy use of `border-radius: 24px+`
- **Best for**: feature-rich products, AI tools, modern SaaS landing pages, hardware product pages
- **Don't use for**: text-heavy products, anything where the "feature ≠ visual" mapping is hard

### Aurora UI / Gradient Mesh
- **Vocabulary**: soft animated gradient washes, dreamy atmospheric backgrounds, bright but not loud
- **Palette**: blended pastels (lavender, mint, peach, sky) flowing into each other via radial gradients
- **Type**: rounded geometric sans (Geist, Söhne, General Sans)
- **Effects**: large blurred radial gradients positioned absolutely, subtle drift animation
- **Best for**: AI products, creative tools, wellness, calm/serene brands

---

## Bold & Opinionated

### Brutalism / Neubrutalism
- **Vocabulary**: thick black borders (3–5px), hard offset shadows (no blur), saturated primary colors (yellow, magenta, cyan), monospace or condensed sans, no rounded corners (or aggressively rounded), raw HTML feel
- **Palette**: white background, black ink, blocks of pure yellow #FFEB3B, hot pink #FF2D87, electric blue #2563EB
- **Type**: monospace (JetBrains Mono, Space Mono) for headlines, or chunky condensed sans (Archivo Black, Space Grotesk)
- **Effects**: `border: 3px solid #000; box-shadow: 6px 6px 0 #000; border-radius: 0` (or 16px)
- **Motion**: instant snaps, no eases, hover offsets the shadow
- **Best for**: indie tools, dev products with attitude, creative agencies, anti-corporate brands
- **Don't use for**: enterprise, healthcare, finance, anything that needs to feel safe

### Cyberpunk / HUD / Sci-Fi FUI
- **Vocabulary**: thin neon strokes, monospace, scanlines, terminal aesthetic, glowing accents, dark base
- **Palette**: near-black background (#0A0A0F), neon cyan #00F0FF, neon magenta #FF006E, terminal green #00FF88
- **Type**: monospace everywhere (JetBrains Mono, IBM Plex Mono, Berkeley Mono)
- **Effects**: thin glowing borders (`box-shadow: 0 0 12px currentColor`), text-shadow glow, animated scanlines, occasional glitch
- **Best for**: dev tools, crypto/web3, gaming, cybersecurity, anything that wants "powerful & technical"

---

## Dark & Serious

### Modern Dark (OLED-friendly)
- **Vocabulary**: deep neutral background, high-contrast white text, subtle elevation via slightly-lighter cards, single saturated accent
- **Palette**: bg #0A0A0A, surface #1A1A1A, text #F5F5F5, dim text #A1A1A1, accent (electric blue #3B82F6 or violet #8B5CF6)
- **Type**: clean sans (Inter, Geist), medium weights, generous line-height
- **Best for**: developer tools, premium consumer products, late-night use cases (music, video), AI chat

### Terminal / E-Ink
- **Vocabulary**: monospace everywhere, no chrome, almost text-only, "this is a tool not a brand"
- **Palette**: paper #F5F1E8 (e-ink) or pure black (terminal), high-contrast text, optional single hyperlink-blue
- **Type**: IBM Plex Mono or JetBrains Mono, body text in mono too
- **Best for**: dev tools, CLI products, writing apps, hacker-audience products

---

## Wildcards (use sparingly, but they're informative)

### Y2K Aesthetic
- Glossy plastic, chrome, beveled buttons, candy colors, MSN Messenger energy. Best for Gen-Z brands, music, fashion.

### Memphis Design
- Geometric shapes scattered, squiggle lines, polka dots, bold primary colors. Best for kids, fun consumer brands, festival/event sites.

### Claymorphism
- Soft 3D rounded shapes that look like Play-Doh, pastel colors, soft shadows. Best for kids apps, casual games, friendly utilities.

### Organic / Biophilic
- Soft curves, leaf/water shapes, earth tones, blob backgrounds. Best for wellness, sustainability, food, nature brands.

---

## How to use this catalog when picking variants

1. **Identify the product's risk profile.** A B2B compliance tool needs to look credible; a meme-coin needs to look feral. Don't suggest Brutalism to a hospital.
2. **Always include one "safe" option** — it's the floor the user can fall back to.
3. **Always include at least one "loud" option** — even if they reject it, contrast helps them articulate what they want.
4. **Pick from different rows of this catalog.** Don't pick three from "Modern & Trendy" — that's three flavors of the same thing.
5. **Skip styles whose "Don't use for" matches the product.** It will waste a slot.
