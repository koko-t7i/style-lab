# style-lab

English | [简体中文](./README.zh-CN.md)

A Claude Code skill that turns a product description into 3–5 self-contained single-page HTML mockups in **distinctly different** visual styles, plus one comparison page to flip through them.

Output is **runnable HTML** — no screenshots, no React, no build step. Open in any browser and *feel* the design in seconds.

## Install

This repo is a Claude Code plugin:

```
/plugin install koko-t7i/style-lab
```

`.claude-plugin/{plugin,marketplace}.json` are pre-configured for `/plugin marketplace`. `skills/style-lab/` is a symlink back to the repo root (no duplicate copy).

## Use

Ask Claude Code for visual options — no need to type `/style-lab`. Auto-triggers on (English or Chinese):

- *"see what styles fit this product"* / *"generate a few design variants"* / *"moodboard"*
- *"make it like Stripe / Linear / Vercel"* — extracts brand DNA (colors, gradients, fonts) from the reference URL
- A pasted PRD / product description

## Iteration

After the first batch:

| You say | Mode | Result |
|---|---|---|
| *"more, but different"* | Fresh-different | New batch of N styles, excluding all shown before |
| *"go deeper on #N"* | Refinement | N variations of the picked style (palette / type / density / hero / tone) |
| *"make it like [Linear / Stripe / Vercel]"* + URL | Reference-driven | Variants stay inside the brand DNA, vary on family-internal axes |
| *"different layouts under this style"* | Layout exploration | Style held constant, page layout varies (single-column, bento, sidebar, pricing) |

State lives in `<output-dir>/state.json` and survives across sessions; picks resurface as `★ Picked` badges. Each comparison-page card has **✓ Pick this**, **🔗 Copy link**, and a per-variant **notes box** with **Copy all feedback**. On a winner, run the DESIGN.md extractor for a Google-Stitch spec downstream coding agents can read.

## Output layout

```
<output-dir>/
  state.json                       # batches, picks, reference summaries
  index.html                       # top-level tabbed page across all batches
  batch-1/
    01-modern-dark/index.html      # one self-contained variant
    02-bento-grid/index.html
    index.html                     # per-batch comparison page (sidebar TOC)
    comparison-bundle.html         # optional single-file build (--bundle)
```

Open `<output-dir>/index.html`; tabs switch batches, each with a sidebar TOC and desktop/tablet/mobile viewport switcher.

## Preview server

`scripts/serve_preview.py <output-dir>` regenerates comparison pages and serves them on a background HTTP server, auto-detecting environment:

- **Local** → `http://localhost:PORT/index.html`
- **SSH** (via `$SSH_CONNECTION`) → also prints a paste-ready `ssh -N -L` tunnel command. Force with `--host <user@host>` or `$STYLE_LAB_SSH_HOST`.

- Stop: `serve_preview.py <output-dir> --kill` — reap all: `serve_preview.py --kill-all`
- No tunnel possible: `generate_index.py <batch-dir> --bundle` writes a single `file://`-openable `comparison-bundle.html`

## Repo layout

```
SKILL.md                       # full agent-facing spec (auto-loaded)
assets/                        # comparison + root page templates
references/
  style-catalog.md             # ~80 visual styles with vocabulary
  product-style-mapping.md     # product type → recommended styles
  visual-signatures.md         # named-brand DNA catalog
  iteration-modes.md           # Mode A/B/C/D state machine
  layout-catalog.md            # named page layouts (Mode D)
  design-md-spec.md            # Google Stitch DESIGN.md spec
  comparison-page-tradeoffs.md # comparison-page design notes
scripts/
  generate_index.py            # build per-batch comparison page
  generate_root_index.py       # build top-level tabbed page
  serve_preview.py             # regenerate + serve + SSH/local detect
  extract_brand_dna.py         # pull colors/gradients/fonts from a URL
  extract_design_md.py         # post-pick DESIGN.md from chosen variant
  init_iteration.py            # migrate flat output dir → batched layout
  validate_variant.py          # sanity-check a generated variant
evals/evals.json               # behavioral eval suite (bilingual triggers)
.claude-plugin/                # plugin + marketplace manifests
skills/style-lab/              # symlink back to root (plugin requirement)
```

For the full agent spec (style picking, refinement axes, reference-driven flow, failure modes), see [`SKILL.md`](./SKILL.md).
