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


def render_toc_item(variant_dir: Path, idx: int) -> str:
    name = slug_to_display_name(variant_dir.name)
    return f"""<button class="toc-item" data-idx="{idx}" type="button">
        <span class="toc-num">{idx + 1:02d}</span>
        <span class="toc-name">{name}</span>
      </button>"""


def render_section(variant_dir: Path, output_dir: Path, idx: int) -> str:
    rel = variant_dir.relative_to(output_dir)
    name = slug_to_display_name(variant_dir.name)
    src = f"{rel}/index.html"
    # Eagerly load the first two iframes so the page has visible content immediately;
    # later ones are lazy to keep the initial paint snappy.
    loading_attr = "" if idx < 2 else ' loading="lazy"'
    return f"""<section class="variant-section" id="variant-{idx}" data-idx="{idx}">
      <div class="variant-header">
        <div class="variant-title">
          <span class="variant-num">{idx + 1:02d}</span>
          <span class="variant-name">{name}</span>
        </div>
        <div class="variant-actions">
          <a href="{src}" target="_blank" rel="noopener">Open ↗</a>
        </div>
      </div>
      <div class="variant-frame">
        <iframe src="{src}"{loading_attr}></iframe>
      </div>
    </section>"""


def render_app_body(variants: list[Path], output_dir: Path, product_title: str) -> str:
    if not variants:
        return """<div class="empty-state">
    <h2>No variants found</h2>
    <p>Each variant must be a subdirectory containing an index.html file.</p>
    <p>Expected naming: <code>01-style-slug/index.html</code>, <code>02-style-slug/index.html</code>, etc.</p>
  </div>"""

    toc = "\n      ".join(render_toc_item(v, i) for i, v in enumerate(variants))
    sections = "\n    ".join(render_section(v, output_dir, i) for i, v in enumerate(variants))
    n = len(variants)

    return f"""<aside>
    <div class="brand">
      <div class="wordmark">Style Lab</div>
      <div class="product">{product_title}</div>
    </div>
    <nav class="toc">
      <div class="toc-label">{n} direction{'s' if n != 1 else ''}</div>
      {toc}
    </nav>
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

    body = render_app_body(variants, output_dir, title)
    variants_json = json.dumps([
        {"name": slug_to_display_name(v.name), "src": f"{v.relative_to(output_dir)}/index.html"}
        for v in variants
    ])

    html = (template
            .replace("__PRODUCT_TITLE__", title)
            .replace("__APP_BODY__", body)
            .replace("__VARIANTS_JSON__", variants_json))

    out_path = output_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  Variants: {len(variants)}")
    for i, v in enumerate(variants):
        print(f"    {i + 1:02d}. {slug_to_display_name(v.name)}")
    print(f"\nOpen: file://{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
