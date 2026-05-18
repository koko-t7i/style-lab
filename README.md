# style-lab

English | [简体中文](./README.zh-CN.md)

A Claude Code skill that turns a product description into 3–5 self-contained single-page HTML mockups in **distinctly different** visual styles, plus one comparison page to flip through them in seconds.

Picking a visual direction early is high-leverage but slow — designers usually mock up 2–3 directions, the founder reacts, they iterate. `style-lab` compresses that loop: hand it a one-pager or PRD, get back real HTML pages each committed to a different visual language, side-by-side. Click through, point at the one that resonates, you have a direction.

The output is **runnable HTML**, not screenshots and not React. Opens in any browser with no build step, so you can *feel* the design within seconds.

## Install

This repo is a Claude Code plugin. From any Claude Code session:

```
/plugin install koko-t7i/style-lab
```

Or add it to a marketplace and install via `/plugin marketplace` — `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` are already set up. `skills/style-lab/` is a thin symlink layer pointing back to the repo root, so there is no duplicate copy to drift.

## Use

Just ask Claude Code for visual options in a session where the plugin is installed. The skill auto-triggers on phrases like:

- *"see what styles fit this product"* / *"design exploration"* / *"generate a few design variants"*
- *"prototype a few looks"* / *"moodboard"* / *"I'm not sure what direction to take"*
- *"make it like Stripe / Linear / Aurpay"* — extracts brand DNA (colors, gradients, fonts) from the reference URL(s) and applies it to every variant
- Or just paste a PRD / product description and ask for visual ideas

You don't need to type `/style-lab` explicitly. The skill also triggers on the equivalent Chinese phrases — see the [中文版](./README.zh-CN.md).

## Iteration

After the first batch:

| You say | Mode | What happens |
|---|---|---|
| *"more, but different"* | Fresh-different | A new batch of N styles, excluding everything shown before |
| *"go deeper on #N"* | Refinement | N variations of the picked style, varying along style-specific axes (palette / type / density / hero device / tone) |
| *"make it like [Linear / Stripe / Aurpay]"* + reference URL | Reference-driven | Extracts brand DNA from the URL, generates variants that all live inside that DNA but vary along family-internal sub-axes |
| *"different layouts under this style"* | Layout exploration | After a style is locked, holds it constant and varies the page layout/composition (single-column, bento, sidebar-workspace, pricing comparison) |

State lives in `<output-dir>/state.json` and survives across sessions. Picked variants are tracked there too and surface as `★ Picked` badges in the comparison page on the next iteration.

In the comparison page, each variant card has a **✓ Pick this** button (copies a ready-to-paste selection phrase so you don't retype which one you liked), a **🔗 Copy link** button (open that variant on your phone / another device), and a per-variant **notes box** with a **Copy all feedback** button — jot reactions per variant and paste them all back at once to drive a tighter refinement round.

When you commit to a winner, run the DESIGN.md extractor to emit a Google-Stitch-format design spec downstream coding agents (Cursor / Claude Code) can read on every future prompt.

## Output layout

```
<output-dir>/
  state.json                       # batches, picks, reference summaries
  index.html                       # top-level tabbed page across all batches
  batch-1/
    01-modern-dark/index.html      # one self-contained variant
    02-bento-grid/index.html
    03-cyberpunk-hud/index.html
    index.html                     # per-batch comparison page with sidebar TOC
  batch-2/
    ...
  batch-1/comparison-bundle.html   # optional: single self-contained file (--bundle)
```

Open `<output-dir>/index.html` and use the tabs at the top to switch between batches. Each tab shows that batch's variants with a sidebar TOC and viewport switcher (desktop / tablet / mobile). Picked variants get a blue `★ Picked` badge.

## Preview server

`scripts/serve_preview.py <output-dir>` regenerates every batch's comparison page from the current state.json and starts a background HTTP server. It auto-detects whether you're on a local machine or in an SSH session:

- **Local**: prints just `http://localhost:PORT/index.html` — open and go.
- **SSH** (detected via `$SSH_CONNECTION`): also prints a paste-ready `ssh -N -L PORT:localhost:PORT <host>` tunnel command. Force this branch by passing `--host <user@host>` or setting `$STYLE_LAB_SSH_HOST`.

Stop the server with `python3 scripts/serve_preview.py <output-dir> --kill`, or reap every preview server started across sessions/dirs with `python3 scripts/serve_preview.py --kill-all`.

For users who can't run an SSH tunnel (locked-down laptop, just want a file), generate a single self-contained file instead: `python3 scripts/generate_index.py <batch-dir> --bundle` writes `comparison-bundle.html` with every variant inlined — it opens straight from `file://`, no server needed.

## Repo layout

```
SKILL.md                     # the full agent-facing spec (auto-loaded by Claude Code)
assets/
  index_template.html        # per-batch comparison page template (sidebar TOC + iframe stack)
  root_index_template.html   # top-level tabbed page template (one tab per batch)
references/
  style-catalog.md           # ~80 distinct visual styles with vocabulary
  product-style-mapping.md   # product type → recommended style set
  visual-signatures.md       # named-brand DNA catalog (Stripe, Linear, Apple, etc.)
  iteration-modes.md         # Mode A/B/C/D state machine for "another round"
  layout-catalog.md          # named page layouts for Mode D layout exploration
  design-md-spec.md          # Google Stitch DESIGN.md spec, post-pick handoff
  comparison-page-tradeoffs.md  # design notes on the comparison page itself
scripts/
  generate_index.py          # build per-batch comparison page
  generate_root_index.py     # build top-level tabbed page
  serve_preview.py           # regenerate + serve + auto-detect SSH/local
  extract_brand_dna.py       # pull colors, gradients, fonts from a URL
  extract_design_md.py       # post-pick, emit DESIGN.md from the chosen variant
  init_iteration.py          # migrate a pre-iteration flat output dir to batched layout
  validate_variant.py        # sanity-check a generated variant
evals/
  evals.json                 # behavioral eval suite (incl. bilingual trigger prompts)
.claude-plugin/
  plugin.json                # plugin manifest
  marketplace.json           # marketplace entry
skills/
  style-lab/                 # symlinks back to root (plugin format requirement)
.gitignore                   # ignores caches + throwaway exploration artifacts
```

For the full agent spec (style picking rules, refinement axes, reference-driven flow, failure modes), read [`SKILL.md`](./SKILL.md).
