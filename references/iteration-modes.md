# Iteration Modes — "another round" or "go deeper on #N"

After the first batch is generated, the user usually does one of two things:

| User says (CN / EN) | Mode | What you do |
|---|---|---|
| "再来一组" / "再来几个不一样的" / "换几个方向" / "show me other directions" / "more, but different" / "what else have you got?" | **A. Fresh-different** | Generate a new batch of N styles that have NOT appeared in any prior batch for this product |
| "继续 #2 衍生" / "02 这个方向再多看几版" / "在 Brutalism 上再来几个" / "go deeper on Bento" / "dial in #3" / "more variations of [name]" | **B. Refinement** | Generate N variations *of the picked style(s)*, varying along style-specific axes |
| 用户给 1+ 个 URL / 截图 / 现成产品名 + "我要这种风格" / "做成 [Stripe / Linear / Apple] 这样" / "give me 5 in this style" + reference link | **C. Reference-driven** | Fetch and analyze the references; extract the design DNA; generate N variants that all live within that DNA but vary along family-internal sub-axes |

Detect the mode from natural language. When ambiguous, ask one short clarifying question — don't guess wrong.

---

## State tracking

Maintain a single file at `<output-dir>/state.json`:

```json
{
  "product": {
    "name": "Custom RPC Gateway",
    "description": "Middleware between dApp and blockchain RPC nodes.",
    "audience": "Web3 backend / infra engineers"
  },
  "batches": [
    {
      "n": 1,
      "kind": "fresh",
      "based_on": [],
      "dir": "batch-1",
      "styles": ["Modern Dark", "Bento Grid", "Cyberpunk HUD", "Neubrutalism", "Terminal"],
      "user_picks": []
    },
    {
      "n": 2,
      "kind": "fresh-different",
      "based_on": [],
      "dir": "batch-2",
      "styles": ["Glassmorphism", "Aurora UI", "Editorial Grid", "Y2K", "Bauhaus"],
      "user_picks": ["Bento Grid"]
    }
  ]
}
```

Read this on every iteration. The flat list of all `batches[*].styles` is your **exclusion list** for Mode A. The latest `batches[*].user_picks` tells you what to refine for Mode B.

---

## Directory layout

```
<output-dir>/
  state.json
  batch-1/
    01-modern-dark/index.html
    02-bento-grid/index.html
    ...
    index.html              ← per-batch comparison page
    SUMMARY.txt
  batch-2/
    01-glassmorphism/index.html
    ...
    index.html
  index.html                ← top-level TOC linking to each batch (optional)
```

For first-run output that was created flat (no `batch-1/` wrapper, no `state.json`), do this on first iteration:

```bash
mkdir -p <output-dir>/batch-1
mv <output-dir>/[0-9]*-* <output-dir>/batch-1/
mv <output-dir>/index.html <output-dir>/batch-1/index.html
mv <output-dir>/SUMMARY.txt <output-dir>/batch-1/SUMMARY.txt   # if exists
```

Then create `state.json` recording batch-1 by inspecting the moved subdirs.

---

## Mode A — Fresh-different

Goal: keep showing the user new design space until they find something that resonates.

1. **Read** `state.json` and collect all styles ever shown across all batches. Call this `seen[]`.
2. **Re-pick** 3–5 styles for this batch using the same logic as the first run (`product-style-mapping.md` + `style-catalog.md`), but exclude `seen[]` from the candidate pool.
3. **If the candidate pool runs out** (after ~4 batches the appropriate styles for a given product type get exhausted), do one of:
    - Tell the user honestly: "We've covered the natural fits. Want me to push into less obvious territory?" — then offer styles from the "Wildcards" row.
    - Or stop and say: "I think we've explored the appropriate design space. Time to pick one and refine." Don't generate weak variants just to hit a quota.
4. **Lock the same shared content** as previous batches (headline, sub, features, CTA). Do NOT rewrite the copy — that breaks the comparison across batches.
5. **Output** to `<output-dir>/batch-N/`.
6. **Update** `state.json` with the new batch entry (kind=`fresh-different`).
7. Run `serve_preview.py` on the **output ROOT** (not the batch dir) — it auto-detects state.json and rebuilds the tabbed top-level index so the user sees all batches in one tab on the same port. Reuse the same port number every time.

---

## Mode B — Refinement

**Required setup before dispatching refinement subagents:**

Refinement only works if the subagent can SEE what it's refining. Every Mode B subagent prompt MUST include this line:

> `Reference variant (read first): <output-dir>/batch-N/<source-variant-slug>/index.html`

Without this, the subagent is guessing at "what makes this variant tick" instead of inheriting from a real example. Result: refinements drift away from the family they were supposed to deepen.

If the user picked multiple variants to refine ("01 and 03 are both good, give me 4 more in each direction"), each subagent gets the reference for ITS specific source variant — not a list of all picked variants.

Goal: take a style the user liked and explore the variations within it.

The user names which variant(s) to refine. Examples:
- "Bento 那个再来 4 版" → refine **Bento Grid** alone
- "Modern Dark 和 Bento 都不错，再各来几个" → refine **both** Modern Dark and Bento Grid (split N variants between them)
- "go deeper on #3" → look up batch-1.styles[2] and refine

For each style being refined, pick **3–5 variation axes** from the table below and generate one variant per axis combination. The point is the user can feel which axis matters most to them.

### Variation axes per style

#### Modern Dark
| Axis | Choices |
|---|---|
| **Accent color** | electric blue / violet / emerald / amber / coral |
| **Type system** | Inter geometric / Geist mono-tinged / Söhne refined / serif headline (Söhne + Söhne Serif) |
| **Density** | spacious & generous (Linear-style) vs dense & data-heavy (Datadog-style) |
| **Hero pattern** | text-only hero / hero with small terminal block / hero with live metric / hero with provider mesh diagram |
| **Surface depth** | flat (single bg color) / layered (multiple slightly-lighter surfaces) / occasional glow |

→ **For 4 Modern Dark variants**: vary 2 axes per variant, keep others constant. E.g., (a) blue + Inter spacious / (b) violet + Geist dense / (c) emerald + Söhne with metric hero / (d) amber + serif headline.

#### Bento Grid
| Axis | Choices |
|---|---|
| **Base palette** | warm cream / pure white / dark / soft pastel washes |
| **Tile shape** | uniform large radius (24px) / mixed radii (some 8, some 32) / pill-shaped tiles |
| **Tile rhythm** | symmetric (every tile same size) / wildly asymmetric / Apple-product-page anchored (one giant + many small) |
| **Tile content focus** | metric-heavy (numbers everywhere) / illustration-heavy (custom SVGs each tile) / code-heavy / quote-heavy / mixed |
| **Color use** | monochromatic (one accent) / multi-color tiles (each tile its own tint) |

#### Cyberpunk / HUD
| Axis | Choices |
|---|---|
| **Dominant neon** | cyan-led / magenta-led / green-led / split (two equally) |
| **Mono face** | JetBrains Mono / IBM Plex Mono / Berkeley Mono / Geist Mono |
| **Chrome density** | lots (HUD panels, brackets, scanlines, ticker) / restrained (clean dark + glow only) |
| **Animation level** | static / subtle (cursor + slow pulse) / busy (RGB glitch + tickers + radar) |
| **Hero device** | typewriter decode / live status panel / rotating ASCII art / mock terminal session |

#### Neubrutalism
| Axis | Choices |
|---|---|
| **Color block primary** | yellow-dominant / pink-dominant / blue-dominant / multi-block |
| **Corner radius** | 0px hard / 16px aggressive rounded |
| **Display type** | Archivo Black chunky / Space Grotesk condensed / all-monospace / mixed (display + mono) |
| **Attitude tone** | comparison-led ("not Alchemy") / manifesto-led ("RPC should be free") / playful / understated brutalism |
| **Shadow weight** | 4px / 6px / 8px hard offset (and matching hover snap distance) |

#### Editorial / Magazine
| Axis | Choices |
|---|---|
| **Serif face** | Fraunces / Playfair Display / GT Sectra / Cormorant |
| **Issue framing** | "Issue 01" masthead / "Volume" framing / no framing (just article) |
| **Image vs spec** | photo-led (placeholder gradient blocks) / spec-sheet led (numbers, specs, dossier) |
| **Drop cap** | with / without |
| **Column structure** | single column long-read / 2-col article / asymmetric grid |

#### Terminal / E-Ink
| Axis | Choices |
|---|---|
| **Background** | paper cream (e-ink) / pure black (terminal) / amber CRT |
| **Mono face** | IBM Plex Mono / JetBrains Mono / Berkeley Mono |
| **Document framing** | man page / README / spec / changelog / RFC |
| **Accent color** | terminal blue link / yellow highlight / phosphor green / no accent at all |
| **Density** | spacious (lots of breathing room) / RFC-dense (every line packed) |

For styles not listed here, **derive variation axes from the style's vocabulary in `style-catalog.md`**. The 5 universal axes that almost always work:
1. Color palette (which accent / which background base)
2. Typography (which display face / body face)
3. Layout density (spacious vs dense)
4. Hero device (how the hero is constructed)
5. Tone of voice in micro-copy (formal / cheeky / technical / poetic)

### Important rules for refinement

- **Lock the headline / sub / features / CTA** — same as Mode A. The whole point is the user can isolate "did the variation work" without being distracted by changed copy.
- **Keep variants distinguishable in 1 sentence.** If you can't say "this one is the spacious-Inter-with-metric-hero version", you didn't vary clearly enough.
- **Be willing to pick 3 instead of 5.** If the style only has 3 meaningfully-different variations worth showing, don't pad with redundant ones.
- **Save in `batch-N/`** with descriptive slugs: `01-bento-cream-asymmetric`, `02-bento-dark-symmetric`, etc. The slug should encode the axis combination so the user can skim names and know what they're seeing.

---

## Mode C — Reference-driven

Goal: replicate the *design language* of an external reference (URLs, screenshots, named products) — applied to the user's product.

1. **First step is always:**
   ```bash
   python3 <skill-path>/scripts/extract_brand_dna.py <url> [<url>...] --output <output-dir>/dna.json
   ```

   Do NOT try to extract colors by manually grepping HTML, asking WebFetch to summarize the page, or guessing from screenshots. The `extract_brand_dna.py` script (a) curls raw HTML preserving inline styles, (b) extracts both solid hex AND linear/radial gradients, (c) identifies which solids are gradient stops vs independent colors, (d) filters out social-brand and theme-boilerplate noise.

   Hand-grepping for `style="..."` will miss gradients. WebFetch will prose-summarize and give you "approximately #0066FF" instead of the actual `#5B7FFF` that's a stop in `linear-gradient(135deg, #5B7FFF, #A78BFA)`. We've made both mistakes in production. Don't repeat them.

   If the user named a brand without a URL ("make it like Linear"), check `references/visual-signatures.md` first — common brands are catalogued there with their DNA. Only fall back to extract_brand_dna.py if the brand isn't in that catalog.

   - From each reference extract: dominant colors (hex if visible), typography (face / weight / hierarchy), background treatment, layout structure, button & card styling, decorative elements (gradients / glow / mesh / orbs / particles), density, and overall mood (e.g. "fintech + Web3 enterprise SaaS").
   - Synthesize a one-paragraph **design DNA summary** that captures what makes this style this style.
   - Save the DNA summary to `state.json` under `batches[N].reference_summary` so future iterations know what was being targeted.

2. **Pick 4–5 sub-axes** that vary INSIDE the DNA (don't break out of it). Universal sub-axes that work for almost any reference:
   - **Tonal range**: pure dark / deep dark with one alt color / lighter alternative / mostly light
   - **Hero device**: text-led centered / split text+illustration / animated SVG mock / dashboard mock / glassmorphism orb
   - **Density**: spacious-marketing (Stripe.com) / dense-product (Datadog) / editorial-prose (Linear blog)
   - **Decorative weight**: clean & restrained / one signature decorative move (orbs, mesh, gradient strip) / heavy decorated (multiple effects layered)
   - **Trust positioning**: enterprise-trust (logos, SOC2, big numbers) / dev-first (code, install command, GitHub) / Web3-native (chains supported, on-chain proof)

3. **Generate one variant per axis combination**. Lock the same shared product copy as all other batches.

4. **Anchor every variant with the same DNA elements** so the family is recognizable:
   - Same primary accent color across all 5 (variations only in saturation/treatment)
   - Same typeface family (variations only in weight/serif-vs-sans)
   - Same rounded-corner philosophy
   - Same button/CTA visual identity (color, gradient, shadow)
   - The differences should feel like "5 designers in the same studio" not "5 different studios"

5. **Save in `batch-N/`** with slugs that name the sibling product or sub-aesthetic the variant leans into:
   - `01-stripe-clean` (closest to pure reference)
   - `02-coinbase-confident` (deeper / more financial-grade)
   - `03-alchemy-glow` (more Web3 / more dynamic)
   - `04-stripe-light` (light-mode interpretation)
   - `05-datadog-enterprise` (more data-dense)
   - These slugs are illustrative — name them after siblings actually relevant to the reference's category.

6. **Update state.json**: `kind: "reference-driven"`, `based_on: [<URLs/names>]`, `reference_summary: "<your DNA paragraph>"`, `styles: [<slug list>]`.

### When the reference doesn't quite fit the product
If the reference's mood is wildly off for the product (e.g. user gives a Stripe URL but is building a Brutalist meme-coin landing page), DO NOT silently produce a Stripe-style page anyway — surface the mismatch in one sentence and ask whether they want literal style replication or a "translated" version that keeps the structural ideas but pulls toward a more product-appropriate register.

---

## Decision tree

```
user prompt arrives
  │
  ├─ output dir exists with state.json?
  │    │
  │    ├─ NO  → first run, normal flow (skill main steps 1-6)
  │    │
  │    └─ YES → iteration:
  │           │
  │           ├─ user gave URL(s) / screenshot / "做成 X 这样" reference?
  │           │    └─ YES → Mode C (Reference-driven). Fetch & analyze first.
  │           │
  │           ├─ user names specific variants to refine (#N, "the Bento one", "Modern Dark")?
  │           │    └─ YES → Mode B (Refinement). Read named picks from latest batch.
  │           │
  │           ├─ user says "more / different / other directions / 再来一组"?
  │           │    └─ YES → Mode A (Fresh-different). Use exclusion list from state.json.
  │           │
  │           └─ AMBIGUOUS → ask one short question:
  │                "想看几个完全不同的方向，还是在 [latest picks or candidates] 上再衍生？"
  │
  └─ generate → write to batch-N/, update state.json, run serve_preview.py on batch-N/
```
