---
name: style-lab
description: Use this skill whenever the user wants to explore visual design directions for a product they are building or pitching — phrases like "看看这个产品适合什么风格", "design exploration", "style options", "批量出几版设计稿", "prototype a few looks", "I'm not sure what direction to take", "moodboard", or any time they hand over a product description / PRD / one-pager and ask for visual ideas before committing to one. ALSO use this skill when the user provides a reference URL or names a brand and asks for that visual style ("做成 Stripe / Linear / Aurpay 这样", "I want it to look like X", "match this brand", "use these design references"); the skill extracts brand DNA (colors, gradients, fonts, components) from URLs and applies it to generated variants. Given a product description and product definition, batch-generates 3–5 self-contained single-page HTML mockups in distinctly different visual styles, plus a side-by-side comparison index.html, so the user can open one URL and decide a direction in minutes instead of weeks. Supports iterating: "more, but different" generates fresh styles excluded from prior batches; "go deeper on #N" generates variations of a picked style; reference-driven mode pulls brand DNA from URLs. After the user commits to a winning variant, the skill emits a DESIGN.md (Google Stitch's open spec) so downstream coding agents (Cursor / Claude Code) can stay on-brand on every future prompt. Trigger this even when the user does not explicitly say "skill" or "style-lab" — if they are exploring directions, asking for visual options, naming a brand to imitate, or pasting design reference links, use it.
---

# style-lab

Help the user pick a visual design direction for a product by generating several runnable HTML landing pages in distinctly different styles, then giving them one comparison page to flip through.

## Why this exists

Picking a visual direction early is high-leverage but slow. Designers usually mock up 2–3 directions, the founder reacts, they iterate. This skill compresses that loop: you take a product description, generate 3–5 real HTML pages each committed to a distinct visual language, and present them side-by-side. The user clicks through, points at the one that resonates, and you have a direction.

The output is **runnable HTML**, not screenshots and not React. HTML opens in any browser with no build step, which is the whole point — the user has to be able to *feel* the design within seconds of you finishing.

## Workflow

### 1. Gather just enough about the product

Read what the user gave you. If they hand you a one-pager or PRD, that is enough. If all you have is a one-line pitch, ask one or two pointed questions — *only* what you actually need to make style choices:

- What is it? (product type — SaaS dashboard, marketing site, mobile app, e-commerce, etc.)
- Who is it for? (audience tone — developers vs. luxury shoppers vs. teens changes everything)
- What is the one feeling you want a visitor to walk away with? (trust / excitement / calm / awe / "this is serious" / "this is fun")

Do not interview them. Three answers max.

### 2. Pick 3–5 distinct styles

The styles you pick must be **distinct from each other**, not three flavors of the same idea. The point of the comparison is to let the user feel the difference. If you generate "minimalism", "exaggerated minimalism", and "Swiss modernism", you have wasted three slots.

A good set covers the design space. For example, for a dev-tool SaaS you might pick:

- one **safe / professional** option (Minimalism, Swiss Modernism 2.0)
- one **modern / trendy** option (Bento Grid, Glassmorphism, Aurora UI)
- one **bold / opinionated** option (Brutalism, Neubrutalism, Cyberpunk UI)
- optionally one **dark / serious** option (Dark Mode OLED, HUD/Sci-Fi)
- optionally one **wildcard** that probably won't win but is informative (Y2K, Memphis, E-Ink)

For getting style metadata (color palettes, AI prompt keywords, CSS hints, do-not-use-for warnings), use the `ui-ux-pro-max` skill if it is installed. It has 80+ styles in a CSV that you can search:

```bash
python3 <ui-ux-pro-max-path>/scripts/search.py "<style name>" --domain style -n 1
```

If `ui-ux-pro-max` is not available, fall back to `references/style-catalog.md` in this skill — it has a curated short list with enough detail to render each style faithfully.

For mapping product types → recommended style sets, see `references/product-style-mapping.md`.

**If the user named a known brand for inspiration** ("做成 Stripe 这样", "give me Linear-style"), check `references/visual-signatures.md` first — ~10 commonly-referenced brands are catalogued there with their full DNA (palette, typeface, signature visual move, mood). If the brand is in the catalog, use that DNA directly; you've saved a network round trip.

**If the user gave a reference URL** (or named a brand not in the catalog), run `scripts/extract_brand_dna.py <url> [<url>...]` BEFORE picking style sub-axes. It curls raw HTML and produces a structured JSON containing solid hex values, full gradient declarations, Google Fonts families, and CSS custom properties — preserving the brand's gradient identity that WebFetch's prose-summarization would lose. See Mode C in `references/iteration-modes.md` for the full reference-driven flow.

### 3. Decide the output directory and shared content

Pick an output directory — default to `./style-lab-output/<product-slug>/` (relative to the user's CWD).

**If `<output-dir>/state.json` already exists, STOP and jump to step 6.5** — this is an iteration, not a first run, and the iteration logic decides where variants go.

For first runs, create a `batch-1/` subdirectory inside the output directory. Each variant goes in `batch-1/01-style-slug/`, `batch-1/02-style-slug/`, etc. Also create `<output-dir>/state.json` recording this first batch (see `references/iteration-modes.md` for the schema).

Before generating variants, write down two pieces of **shared content** so every variant tells the same story with different visuals:

- The **headline + subhead** (the actual product pitch, in the user's words where possible)
- A short list of **3 features / value props** (1 sentence each)
- A **CTA label** (e.g., "Start free trial", "Get early access")

Lock these. Don't let yourself rewrite the copy per variant — the comparison only works if the only thing changing is the visual treatment.

### 4. Generate one HTML page per style

For each style, write `<output-dir>/<style-slug>/index.html` as a single self-contained HTML file. Rules:

- **Inline everything.** All CSS in `<style>`, all JS in `<script>`. The user opens the file with `file://` and it has to just work — no fetch, no CDN that might be down, no build step. Google Fonts via `<link>` is OK because it is the standard way and degrades to system fonts.
- **Single landing page only.** Hero, 3-feature section, secondary CTA, footer. That's it. Don't sprawl.
- **Commit to the style.** The whole point is to feel the difference. If you are doing Brutalism, do Brutalism — sharp edges, thick borders, raw type. Don't soften it because you're worried the user won't like it. They will tell you. A timid Brutalism page tells them nothing.
- **Use the style's actual visual vocabulary.** When the style metadata says "soft pastels, multiple shadow layers" (Neumorphism), use that. When it says "deconstructed grid, asymmetric, raw HTML aesthetic" (Brutalism), do that. Don't generate generic "modern SaaS" with a different accent color and call it five styles.
- **Real responsive layout.** Test that it doesn't break at 375px wide. Mobile is where most people will look.
- **No lorem ipsum.** Use the locked headline/features/CTA from step 3. Real copy makes it 10× more evaluable.

#### Subagent prompts must reference state.json — never paste locked copy

When you dispatch subagents to write each variant, your prompt should INSTRUCT THEM TO READ state.json, not paste the locked copy into N prompts.

❌ Wrong (fragile):
```
Write a landing page with this copy:
Headline: Route, retry, observe — so your app doesn't have to.
Sub: Custom RPC Gateway sits between your app and any blockchain provider...
Features:
  1. Multi-provider routing — Auto-failover across...
  ...
```
Repeating across 5 subagent prompts means one typo breaks the comparison.

✓ Right (single source of truth):
```
Locked copy: read /home/dev-koko/style-lab-output/<product>/state.json,
use the `shared_copy` block verbatim (headline, subhead, features, cta_primary,
cta_secondary, footer). Do NOT paraphrase any text from that block.
```
One state.json edit propagates to all subagents next batch.

**State.json must always be written before dispatching any variant subagent.** If you're about to dispatch and state.json doesn't have shared_copy populated, write it first.

#### Validate every variant before moving to step 5

After each subagent finishes, run:

```bash
python3 <skill-path>/scripts/validate_variant.py <output-dir>/batch-N/<variant-slug>
```

It auto-checks: no lorem ipsum, headline + subhead + brand name appear verbatim (text-content match, ignoring inline `<em>` styling), HTML parses cleanly, file is non-trivial size (≥5KB), at least one `<style>` block, primary CTA text present. If state.json's `reference_summary` mentions specific hex values (Mode C), it warns when none of them appear in the variant — catches "agent forgot to use the brand palette" failures.

If any error-severity check fails, **regenerate that variant before going to step 5**. Don't ship "mostly works" — broken or off-copy variants poison the whole comparison and waste user attention. The script writes `<variant-dir>/validation.json` with full evidence, and exits non-zero on failure for easy scripted gating.

#### Layout / CSS pitfalls

The comparison-page layout (sidebar TOC + scrollable feed of full-height variants) was chosen after several wrong attempts. Specific layout patterns to avoid (`flex: 1` + `min-height: 100vh` + nested iframe collapses to 0 height; `scroll-snap-type` on long sections locks scroll position; lazy-loading the FIRST iframe causes blank-page flicker) are catalogued in `references/comparison-page-tradeoffs.md`. Read that doc before changing the comparison index template.

### 5. Generate the comparison index AND start the preview server

Run the bundled script — it does both in one step. **Always point at the OUTPUT ROOT** (the directory containing `state.json` and the `batch-N/` subdirs), not at a single batch dir:

```bash
python3 <skill-path>/scripts/serve_preview.py <output-dir> --title "<product name>"
```

The script auto-detects the layout:
- If `<output-dir>/state.json` exists → multi-batch mode. It refreshes every batch's per-batch comparison page AND generates a top-level **tabbed index** at `<output-dir>/index.html` so the user can switch between batches in one tab via the top tab strip. Single port, multiple batches.
- Otherwise → single-batch mode (legacy / first run). Just regenerates `<output-dir>/index.html` for that one directory.

**Always reuse the same port** across iterations. If a server is already up on the user's port (e.g. 8770), running this command again kills the old one and restarts on the same port — the user keeps the same browser tab and the same SSH tunnel. Don't keep allocating new ports per batch.

This:
1. Regenerates `<output-dir>/index.html` (side-by-side iframe grid, Single-mode toggle, viewport switcher) from `assets/index_template.html`.
2. Picks a free port (default 8765+, or pass `--port 8765`).
3. Starts `python3 -m http.server` detached in the background, serving the directory.
4. Prints a paste-ready `ssh -L` command for the user's local PowerShell / Terminal, plus the `http://localhost:PORT/index.html` URL to open in their browser.
5. Writes a `.preview-server.pid` so the server can be killed later: `python3 <skill-path>/scripts/serve_preview.py <output-dir> --kill`.

If you only need the static index without serving (e.g. user is on local machine), you can call `generate_index.py` directly instead — but in 95% of cases the user is on a remote server and `serve_preview.py` is what you want.

### 6. Hand off to the user

The script's output already tells the user exactly what to paste and what to open. Don't re-explain the SSH command — the user has eyes. Just:

1. Re-paste the SSH command and the URL prominently in your reply (they're easy to miss in script output).
2. Briefly (2–3 lines per variant) say what you were going for with each one and what kind of product/audience it's best for.
3. Don't editorialize about which is "best" — that's exactly what the user is here to decide.

If the user is local (not over SSH), tell them to skip the `ssh -L` step and just open `http://localhost:PORT/index.html` directly.

If the user picks one or asks to "go deeper on #2", you can then either:
- generate a second iteration of just that style with refinements they asked for, or
- expand it into more pages (dashboard, settings, etc.) — but only once they have committed to a direction.

### 6.5 If this is an iteration, not a first run — branch here

Before doing anything else for a return-visit prompt, check whether `<output-dir>/state.json` exists. If it does, this is **not** a first run — the user is iterating on a previous batch. Two modes apply, and you must pick one based on natural language:

- **Mode A — "more, but different"**: user wants a fresh batch of styles that haven't been shown yet. Read `state.json` to get the exclusion list, re-pick from the catalog excluding everything ever shown, output to `batch-N/`.
- **Mode B — "go deeper on #N"**: user picked one or more variants (by number or name); generate variations *of those styles* along style-specific axes (palette / type / density / hero device / tone). Lock the same shared copy.

See `references/iteration-modes.md` for the full decision tree, the per-style variation axes (Modern Dark / Bento / Cyberpunk / Brutalism / Editorial / Terminal each have a table), and what `state.json` looks like.

If the first batch was created flat (no `batch-1/` wrapper, no state file — i.e. you're iterating on output from an older skill version), run the bundled migration helper:

```bash
python3 <skill-path>/scripts/init_iteration.py <output-dir> --name "<ProductName>" [--description "..."]
```

It defaults to **dry-run** so you (and the user) can review the planned moves before applying. Re-run with `--commit` to actually execute. This creates the `batch-1/` wrapper, moves all `NN-*/` subdirs and the root index/SUMMARY into it, and writes a `state.json` populated from the migrated content. Don't try to do the migration manually with `mv` commands — the script handles void-tag-style HTML, partial prior runs, and edge cases the spec in `iteration-modes.md` doesn't cover.

### 7. When the user picks a winner — emit DESIGN.md

This step **only fires after the user has clearly committed to one variant**. Trigger phrases (Chinese + English): "用 #N" / "就用 [name]" / "锁定" / "确定" / "采纳" / "选这个" / "go with #N" / "let's ship the [style] one" / "use the [name] direction".

Don't auto-emit a DESIGN.md for every variant during exploration — it pollutes the comparison and most variants will be rejected anyway. The whole value of DESIGN.md is that it represents a **chosen direction** that downstream coding agents (Cursor / Claude Code / Stitch) will read on every future prompt to stay on-brand.

Workflow:

```bash
python3 <skill-path>/scripts/extract_design_md.py <output-dir>/<NN-winning-style> \
    --name "<ProductName>" \
    --description "<one-line pitch>" \
    --style-name "<DisplayName>"
```

This:
1. Scans the winning variant's `index.html` and extracts **solid colors AND gradients** (linear + radial), typography, spacing, border-radius into the YAML front-matter of a new `DESIGN.md` (saved one level up — alongside the variant folders). Solid hex values that are also gradient stops are renamed to indicate the relationship (`brand-start: "#5B7FFF"  # gradients.brand stop 0`) instead of appearing as standalone `accent` / `highlight` tokens — this makes the gradient identity obvious to downstream agents reading the file.
2. Generates the 9-section markdown skeleton with `<!-- LLM-FILL: ... -->` placeholders.

Then **you** (the agent reading this skill) must:

3. **Read the variant's `index.html`** to see what was actually built — colors used, components designed, layout choices made. Ground every prose section in something a reader could verify by looking at the page.
4. **Read `references/design-md-spec.md`** for what each of the 9 sections should contain and the specificity level required.
5. **Replace every `<!-- LLM-FILL: ... -->` placeholder** with real, opinionated, variant-specific prose. Don't write generic design-system copy. Don't soften opinionated styles (Brutalism's DESIGN.md should *forbid* gradients, not "discourage" them).
6. **Review the auto-extracted color token names.** The script guesses based on luminance/saturation — `paper` and `ink` are usually right but `surface`/`muted`/`border` may be miscategorized. Rename to match how each color is actually used on the page.
7. **Optionally validate** with `npx @google/design.md lint <path>/DESIGN.md` (catches broken token references and WCAG contrast issues). Fix anything it flags.
8. Tell the user the file is ready and what they do with it: drop it at the repo root, point Cursor / Claude Code at it, and every future UI prompt will respect the brand.

## Anti-patterns to avoid

- **Five variants that look the same.** If you can't articulate, in one sentence, what makes each one different from the others, you picked the wrong set. Go back and re-pick.
- **Generic "modern" everything.** Rounded corners + a gradient + a hero image is not a style. It is the absence of one. Pick styles that have a real point of view.
- **Burying the comparison.** The user shouldn't have to open 5 tabs. The index.html is the deliverable; the variants are inputs to it.
- **Asking the user to pick styles upfront.** They don't know the catalog. Your job is to pick. They react.
- **Mixing CSS frameworks.** Don't pull in Tailwind in one variant and write vanilla CSS in another and shadcn in a third. Pick one approach (vanilla CSS in `<style>` is fine and has zero deps) and apply it consistently. Variation should be in the *design*, not the *toolchain*.

## Files in this skill

**References (read on demand)**
- `references/style-catalog.md` — fallback style list with enough metadata to render each style if ui-ux-pro-max is not installed
- `references/product-style-mapping.md` — common product types → recommended style sets, for picking quickly
- `references/iteration-modes.md` — how to handle "more, but different" / "go deeper on #N" / "make it like X" iteration requests, plus per-style variation axes (read this before step 6.5)
- `references/design-md-spec.md` — the 9-section DESIGN.md format spec + how to fill in each section well (read this before doing step 7)
- `references/visual-signatures.md` — pre-catalogued brand DNA (palette + gradient + typeface + signature visual move) for ~10 commonly-named brands (Stripe / Linear / Vercel / Coinbase / Datadog / Notion / Apple / Arc / Anthropic / Aurpay). Check this first when the user names a brand, before running brand-DNA extraction.
- `references/comparison-page-tradeoffs.md` — why the comparison index uses sidebar+scroll layout, what other layouts were tried and why they failed, and known CSS pitfalls (iframe height collapse, scroll-snap traps, lazy-load flicker). Read before changing the comparison index template.

**Scripts (called explicitly)**
- `scripts/generate_index.py` — generates the per-batch comparison index.html from a folder of variants (low-level, used by serve_preview.py)
- `scripts/generate_root_index.py` — generates the top-level **tabbed** index.html that switches between batches in one tab (low-level, called by serve_preview.py when state.json is present)
- `scripts/serve_preview.py` — regenerates indexes, starts a background HTTP server, and prints the `ssh -N -L` command for remote previewing. Auto-detects single-batch vs multi-batch layout. Always reuse the same port across iterations.
- `scripts/extract_brand_dna.py` — fetches one or more reference URLs and extracts a structured brand DNA JSON (solids + gradients + fonts + CSS vars + a one-paragraph summary). Run BEFORE generating variants in Mode C (reference-driven). Filters out social-brand and Elementor theme-boilerplate noise. See step 2.
- `scripts/validate_variant.py` — runs after each variant is generated to catch lorem ipsum, dropped headlines, broken HTML, or missing brand colors. Writes `validation.json` per variant; exits non-zero on failure for scripted gating. See step 4.
- `scripts/init_iteration.py` — auto-migrates a flat first-batch output (no `batch-1/` wrapper, no state.json) into the canonical batch-N structure. Defaults to dry-run; pass `--commit` to apply. See step 6.5.
- `scripts/extract_design_md.py` — after the user picks a winner, scans that variant's HTML and emits a DESIGN.md with extracted tokens (now including gradients, with stop-aware renaming) + 9-section skeleton. See step 7.

**Assets (templates)**
- `assets/index_template.html` — the per-batch comparison page template (sidebar TOC + scroll feed)
- `assets/root_index_template.html` — the top-level tabbed page template (one tab per batch)
