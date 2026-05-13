#!/usr/bin/env python3
"""
Generate a sidebar-TOC + scroll-feed comparison index.html for a style-lab
output directory.

Usage:
    python3 generate_index.py <output-dir> [--title "Product Name"]

Layout: a fixed left sidebar listing every variant (click to jump, auto-
highlights the variant you're scrolling past), and a main scroll-snap area
where each variant renders in a full-viewport-height iframe. Scroll naturally
to flip through every variant; or click the sidebar; or press j/k / ↑↓ /
1–9 keys.

Subdirectory naming convention: NN-style-slug  (e.g., 01-minimalism). The
numeric prefix controls order; the rest becomes the display name.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "index_template.html"


def slug_to_display_name(slug: str) -> str:
    name = re.sub(r"^\d+[-_]", "", slug)
    name = name.replace("-", " ").replace("_", " ")
    return name.title()


def find_variants(output_dir: Path) -> list[Path]:
    variants = []
    for child in sorted(output_dir.iterdir()):
        if child.is_dir() and (child / "index.html").exists():
            variants.append(child)
    return variants


def load_batch_picks(output_dir: Path) -> tuple[list[str], list[str]]:
    """Return (styles, user_picks) for the batch this directory represents.

    Reads ../state.json and finds the batch whose `dir` matches output_dir.name.
    Returns ([], []) if state.json is missing, unparseable, or has no matching batch.
    """
    state_path = output_dir.parent / "state.json"
    if not state_path.exists():
        return [], []
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], []
    for batch in state.get("batches", []):
        if batch.get("dir") == output_dir.name:
            return list(batch.get("styles", [])), list(batch.get("user_picks", []))
    return [], []


def compute_picks(variants: list[Path], styles: list[str], user_picks: list[str]) -> tuple[list[bool], list[str]]:
    """Return (per-variant picked flags, leftover free-form picks).

    A variant is "picked" when its positional style (styles[i]) either appears
    verbatim in user_picks, or is a prefix of some pick string (handles cases
    like 'Modern Dark · spacious ✓ FINAL' picking the 'Modern Dark · spacious'
    variant). Picks that don't map to any variant are returned as leftover
    notes for display in the sidebar.
    """
    picked = [False] * len(variants)
    matched_picks: set[int] = set()
    for i, _ in enumerate(variants):
        if i >= len(styles):
            break
        style = styles[i]
        for j, pick in enumerate(user_picks):
            if pick == style or pick.startswith(style + " ") or pick.startswith(style + "·"):
                picked[i] = True
                matched_picks.add(j)
    leftovers = [p for j, p in enumerate(user_picks) if j not in matched_picks]
    return picked, leftovers


def render_toc_item(variant_dir: Path, idx: int, picked: bool) -> str:
    name = slug_to_display_name(variant_dir.name)
    classes = "toc-item picked" if picked else "toc-item"
    badge = '<span class="toc-pick">★ Picked</span>' if picked else ""
    return f"""<button class="{classes}" data-idx="{idx}" type="button">
        <span class="toc-num">{idx + 1:02d}</span>
        <span class="toc-name">{name}</span>
        {badge}
      </button>"""


def render_section(variant_dir: Path, output_dir: Path, idx: int, picked: bool) -> str:
    rel = variant_dir.relative_to(output_dir)
    name = slug_to_display_name(variant_dir.name)
    src = f"{rel}/index.html"
    # Eagerly load the first two iframes so the page has visible content immediately;
    # later ones are lazy to keep the initial paint snappy.
    loading_attr = "" if idx < 2 else ' loading="lazy"'
    badge = '<span class="pick-badge">★ Picked</span>' if picked else ""
    section_class = "variant-section picked" if picked else "variant-section"
    return f"""<section class="{section_class}" id="variant-{idx}" data-idx="{idx}">
      <div class="variant-header">
        <div class="variant-title">
          <span class="variant-num">{idx + 1:02d}</span>
          <span class="variant-name">{name}</span>
          {badge}
        </div>
        <div class="variant-actions">
          <a href="{src}" target="_blank" rel="noopener">Open ↗</a>
        </div>
      </div>
      <div class="variant-frame">
        <iframe src="{src}"{loading_attr}></iframe>
      </div>
    </section>"""


def render_picks_notes(leftovers: list[str]) -> str:
    if not leftovers:
        return ""
    items = "\n        ".join(f"<li>{html.escape(p)}</li>" for p in leftovers)
    return f"""<div class="picks-notes">
      <div class="picks-label">Picks (free-form)</div>
      <ul>
        {items}
      </ul>
    </div>"""


def render_app_body(variants: list[Path], output_dir: Path, product_title: str,
                    picked_flags: list[bool], leftover_picks: list[str]) -> str:
    if not variants:
        return """<div class="empty-state">
    <h2>No variants found</h2>
    <p>Each variant must be a subdirectory containing an index.html file.</p>
    <p>Expected naming: <code>01-style-slug/index.html</code>, <code>02-style-slug/index.html</code>, etc.</p>
  </div>"""

    toc = "\n      ".join(render_toc_item(v, i, picked_flags[i]) for i, v in enumerate(variants))
    sections = "\n    ".join(render_section(v, output_dir, i, picked_flags[i]) for i, v in enumerate(variants))
    n = len(variants)
    pick_count = sum(picked_flags)
    pick_summary = f" · {pick_count} picked" if pick_count else ""
    notes_block = render_picks_notes(leftover_picks)

    return f"""<aside>
    <div class="brand">
      <div class="wordmark">Style Lab</div>
      <div class="product">{product_title}</div>
    </div>
    <nav class="toc">
      <div class="toc-label">{n} direction{'s' if n != 1 else ''}{pick_summary}</div>
      {toc}
    </nav>
    {notes_block}
    <div class="controls">
      <div class="control-label">Viewport</div>
      <div class="viewport-switcher" id="viewport-switcher">
        <button data-viewport="desktop" class="active">Desktop</button>
        <button data-viewport="tablet">Tablet</button>
        <button data-viewport="mobile">Mobile</button>
      </div>
      <div class="keyhint">
        <kbd>↑</kbd> <kbd>↓</kbd> or <kbd>1</kbd>–<kbd>{min(n, 9)}</kbd>
      </div>
    </div>
  </aside>
  <main id="main">
    {sections}
  </main>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", help="Directory containing variant subdirectories")
    parser.add_argument("--title", default="", help="Product title shown in the sidebar")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory", file=sys.stderr)
        return 1

    if not TEMPLATE_PATH.exists():
        print(f"Error: template missing at {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    variants = find_variants(output_dir)
    title = args.title or output_dir.name.replace("-", " ").title()

    styles, user_picks = load_batch_picks(output_dir)
    picked_flags, leftover_picks = compute_picks(variants, styles, user_picks)

    body = render_app_body(variants, output_dir, title, picked_flags, leftover_picks)
    variants_json = json.dumps([
        {"name": slug_to_display_name(v.name), "src": f"{v.relative_to(output_dir)}/index.html"}
        for v in variants
    ])

    rendered = (template
                .replace("__PRODUCT_TITLE__", title)
                .replace("__APP_BODY__", body)
                .replace("__VARIANTS_JSON__", variants_json))

    out_path = output_dir / "index.html"
    out_path.write_text(rendered, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  Variants: {len(variants)}")
    for i, v in enumerate(variants):
        marker = "  ★" if picked_flags[i] else ""
        print(f"    {i + 1:02d}. {slug_to_display_name(v.name)}{marker}")
    if leftover_picks:
        print(f"  Picks (free-form, {len(leftover_picks)}):")
        for p in leftover_picks:
            print(f"    - {p}")
    print(f"\nOpen: file://{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
