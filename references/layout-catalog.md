# Layout Catalog — page structures for Mode D (Layout exploration)

After the user has picked a winning **style** (visual language: palette, typography, decoration), this catalog supplies the **layouts** (page structure: section order, grid recipe, density, anchor element). Mode D variants hold style constant and vary layout.

Each entry below names a layout, declares its skeleton + grid recipe + content requirements, and indicates good-fit and bad-fit product types. Pick 4–6 entries per Mode D batch that are **structurally distinct** from each other — don't ship five flavors of long-scroll.

---

## single-column-long-scroll

- **Name**: Single-column long scroll
- **Skeleton**: hero → social-proof logos (optional) → 3 features (stacked vertically) → testimonial → secondary CTA → FAQ → footer
- **Grid recipe**: `max-width: 720px; margin: 0 auto;` single column, 96–128px vertical rhythm between major sections
- **Density**: spacious
- **Anchor**: text-anchored
- **Requires**: `headline`, `subhead`, `features >= 3`, `cta_primary`. Optional: `testimonials >= 1`, `logos`, `faq`
- **Good fit**: editorial / newsletter / writer products, dev-tool changelog pages, indie SaaS, founder pages
- **Bad fit**: dashboard-heavy products, multi-feature SaaS, e-commerce with many SKUs
- **Reference brands**: Stripe Press, Linear blog, Pieter Levels' pages, Substack landing pages

## bento-9-tile

- **Name**: Bento 9-tile
- **Skeleton**: hero (one banner) → 3×3 bento grid (one giant + eight small tiles) → CTA strip → footer
- **Grid recipe**: `grid-template-columns: repeat(3, 1fr); grid-auto-rows: minmax(220px, auto); gap: 16px`. First tile spans 2 cols × 2 rows. Each remaining tile shows one feature/metric/quote.
- **Density**: medium-dense
- **Anchor**: mock-anchored (giant tile usually carries a product mock or signature illustration)
- **Requires**: `features_extended >= 9` OR a mix totalling 9 tiles (e.g., `features >= 3` + `stats >= 3` + `testimonials >= 3`)
- **Good fit**: AI products, design tools, multi-feature SaaS, developer platforms
- **Bad fit**: single-feature products, products requiring sequential narrative
- **Reference brands**: Apple product pages, Vercel home, Linear features grid, Raycast

## sidebar-workspace

- **Name**: Sidebar + workspace
- **Skeleton**: top nav → split (left rail: feature index | right pane: live product mock or tabbed feature deep-dive) → CTA strip → footer
- **Grid recipe**: `grid-template-columns: 240px 1fr; min-height: 80vh;` for the split section. Left rail is sticky. Right pane swaps content as the user scrolls or clicks rail items.
- **Density**: medium (visually rich on the right, restrained on the left)
- **Anchor**: mock-anchored (the workspace IS the page)
- **Requires**: `headline`, `subhead`, `features >= 3` (each becomes one rail item), `cta_primary`
- **Good fit**: developer tools, IDE-like products, dashboards, products where the UI itself is the value prop
- **Bad fit**: marketing-led products, mobile-first products, products without a real UI to show
- **Reference brands**: Linear features page, Notion enterprise page, Cursor home, Raycast

## tab-based

- **Name**: Tab-based product tour
- **Skeleton**: hero → tab strip (3–5 tabs, each = one major capability) → tab pane showing screenshots/code/diagram → CTA → footer
- **Grid recipe**: tabs use `display: flex; gap: 4px` for the strip; each pane is `grid-template-columns: 1fr 1.2fr; gap: 48px` (text + visual). Pane swaps via JS, scroll-snap optional.
- **Density**: medium
- **Anchor**: mock-anchored (each tab pane carries a visual)
- **Requires**: `headline`, `subhead`, `features >= 3` (one per tab), `cta_primary`. Optional: per-feature code snippets or screenshots described in copy.
- **Good fit**: products with 3–5 distinct capabilities, dev tools with multiple workflows, SaaS with persona-segmented value props
- **Bad fit**: products with one dominant feature, content-led pages, brutalist/raw aesthetics (tabs feel polished)
- **Reference brands**: Stripe products page, Vercel platform tour, Plaid use-cases

## card-waterfall

- **Name**: Card waterfall (masonry)
- **Skeleton**: hero → masonry grid of mixed-height cards (features, testimonials, stats, screenshots interleaved) → CTA strip → footer
- **Grid recipe**: CSS columns (`column-count: 3; column-gap: 16px`) OR `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` with cards of varying internal height. Cards have visible borders/shadows per the chosen style's vocabulary.
- **Density**: dense
- **Anchor**: text-anchored (each card is a small story; no single hero pulls focus inside the waterfall)
- **Requires**: at least 9 distinct items mixing `features_extended`, `testimonials`, `stats`, optional `logos`. Items can be heterogeneous (some quote, some metric, some feature, some screenshot caption).
- **Good fit**: showcase-style pages (portfolios, design tools), products with diverse social proof, "look how much value we have" framing
- **Bad fit**: minimalist products, products with single clear value prop, narrative-led pitches
- **Reference brands**: Framer marketplace pages, Pinterest, Webflow showcase, Awwwards

## hero-pricing-comparison

- **Name**: Hero + pricing comparison
- **Skeleton**: hero (concise — one line each) → 3-tier pricing comparison table → FAQ → footer
- **Grid recipe**: pricing uses `grid-template-columns: repeat(3, 1fr); gap: 24px` for tier cards. Middle ("recommended") card scales 1.04× and uses the brand accent color. Each card has ~8 feature rows with check/cross icons.
- **Density**: dense (every tier surfaces ~8 feature rows; FAQ is dense by nature)
- **Anchor**: pricing-anchored — the whole page is structured to drive plan selection
- **Requires**: `headline`, `subhead`, `pricing_tiers >= 3` (each with `{tier, price, features[], cta}`), `faq >= 3`, `cta_primary`. The original 3 `features` may be condensed into the hero subhead or compressed onto each pricing card.
- **Good fit**: SaaS with self-serve plans, transactional products, products where pricing IS the conversion lever
- **Bad fit**: enterprise (custom pricing only), exploration-stage products without firm pricing, brand-led marketing pages
- **Reference brands**: Linear pricing, Notion pricing, Vercel pricing, Resend pricing

---

## Universal layout axes

When you need a layout not in this catalog, derive a new one along these 5 axes. Almost every page layout is some combination:

1. **Section count** — 3 sections (focused) ↔ 8+ sections (comprehensive)
2. **Sequence** — sequential (vertical scroll forces order: hero → features → CTA) ↔ lateral (tabs, sidebar, masonry — user picks their own order)
3. **Density** — spacious (Linear) ↔ dense (Datadog)
4. **Anchor element** — text-anchored (copy carries weight) / mock-anchored (UI screenshot or illustration) / pricing-anchored (tier comparison is the page) / comparison-anchored ("vs competitor" tables)
5. **Navigation pattern** — pure scroll / scroll + sticky nav / tab strip / left sidebar / progressive disclosure (accordion)

A new layout = a specific choice along each axis + a memorable name + a grid recipe.

---

## Rules for picking a Mode D batch

1. **Pick layouts that are structurally distinct** — different `sequence`, different `anchor`, different `density`. Don't ship two long-scroll variants.
2. **Each layout MUST preserve `headline`, `subhead`, `cta_primary`** verbatim. This is the spine that lets the user compare across batches and tells them the same story; only the structure changes.
3. **Check `requires:` against current `shared_copy` before generating.** If a layout needs `pricing_tiers >= 3` and `shared_copy` doesn't have them, EITHER extend `shared_copy` once (preferred — see SKILL.md §7.5) OR drop that layout from the batch.
4. **Pick 4–6 layouts per batch.** Fewer if the product genuinely doesn't support more (e.g., a single-feature CLI doesn't need a pricing comparison layout).
5. **Name variants by layout slug** in `state.json.batches[N].styles[]`: `["Single-column long scroll", "Bento 9-tile", "Sidebar workspace", ...]`. The `layout_axes[]` field holds the machine-readable slugs.
