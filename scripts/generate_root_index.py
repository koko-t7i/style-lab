#!/usr/bin/env python3
"""
Generate the top-level tabbed index.html for an output directory containing
multiple batches.

Usage:
    python3 generate_root_index.py <output-dir>

Reads <output-dir>/state.json, then writes <output-dir>/index.html with one
tab per batch. Each tab loads the batch's own comparison page in an iframe.
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "root_index_template.html"

KIND_LABELS = {
    "fresh": ("FRESH", "fresh"),
    "fresh-different": ("MORE", "fresh"),
    "refinement-of": ("REFINE", "refine"),
    "reference-driven": ("REF", "ref"),
}


def render_tab(batch: dict, idx: int) -> str:
    n = batch.get("n", idx + 1)
    kind = batch.get("kind", "fresh")
    label, css = KIND_LABELS.get(kind, ("BATCH", "fresh"))
    style_count = len(batch.get("styles", []))
    picks = batch.get("user_picks", [])
    pick_html = ""
    if picks:
        pick_html = f'<span class="picked">★ {len(picks)} picked</span>'

    return f"""<button class="tab" data-idx="{idx}" type="button">
        <div class="tab-row">
          <span class="tab-num">batch {n:02d}</span>
          <span class="tab-kind {css}">{label}</span>
        </div>
        <div class="tab-meta">
          <span>{style_count} {'variant' if style_count == 1 else 'variants'}</span>
          {pick_html}
        </div>
      </button>"""


def render_empty() -> str:
    return """<div class="empty-state">
    <h2>No batches yet</h2>
    <p>state.json has no <code>batches</code> entries. Generate a batch first.</p>
  </div>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", help="Output directory containing state.json + batch-N/ subdirs")
    parser.add_argument("--title", default="", help="Product title shown in the header (default: from state.json)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        print(f"error: {output_dir} is not a directory", file=sys.stderr)
        return 1

    state_path = output_dir / "state.json"
    if not state_path.exists():
        print(f"error: no state.json in {output_dir}", file=sys.stderr)
        return 1

    if not TEMPLATE_PATH.exists():
        print(f"error: template missing at {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    state = json.loads(state_path.read_text(encoding="utf-8"))
    batches = state.get("batches", [])
    title = args.title or state.get("product", {}).get("name") or output_dir.name.replace("-", " ").title()

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    if batches:
        tabs = "\n      ".join(render_tab(b, i) for i, b in enumerate(batches))
        stage = ""  # populated by JS
        batch_descriptors = []
        for i, b in enumerate(batches):
            n = b.get("n", i + 1)
            batch_dir = b.get("dir", f"batch-{n}")
            batch_descriptors.append({
                "n": n,
                "kind": b.get("kind", "fresh"),
                "src": f"{batch_dir}/index.html",
                "styles": b.get("styles", []),
                "user_picks": b.get("user_picks", []),
            })
        batches_json = json.dumps(batch_descriptors)
    else:
        tabs = ""
        stage = render_empty()
        batches_json = "[]"

    html = (template
            .replace("__PRODUCT_TITLE__", title)
            .replace("__TABS__", tabs)
            .replace("__STAGE__", stage)
            .replace("__BATCHES_JSON__", batches_json))

    out_path = output_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  Batches: {len(batches)}")
    for i, b in enumerate(batches):
        n = b.get("n", i + 1)
        kind = b.get("kind", "fresh")
        styles = len(b.get("styles", []))
        picks = len(b.get("user_picks", []))
        marker = f" · {picks} picked" if picks else ""
        print(f"    {n:02d}. {kind}  ({styles} variants){marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
