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


def _load_batch_entry(output_dir: Path) -> dict:
    """Return the raw state.json batch dict whose `dir` matches output_dir.name.

    Single source of truth for the ../state.json read path. Returns {} if
    state.json is missing, unparseable, or has no matching batch.
    """
    state_path = output_dir.parent / "state.json"
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    for batch in state.get("batches", []):
        if batch.get("dir") == output_dir.name:
            return batch
    return {}


def load_batch_picks(output_dir: Path) -> tuple[list[str], list[str]]:
    """Return (styles, user_picks) for the batch this directory represents.

    Returns ([], []) if state.json is missing, unparseable, or has no matching batch.
    """
    batch = _load_batch_entry(output_dir)
    if not batch:
        return [], []
    return list(batch.get("styles", [])), list(batch.get("user_picks", []))


def load_batch_blurbs(output_dir: Path) -> list[str]:
    """Return the optional `blurbs` array (parallel to `styles`) for this batch.

    Empty list if state.json is missing, unparseable, has no matching batch,
    or the batch has no `blurbs`.
    """
    batch = _load_batch_entry(output_dir)
    if not batch:
        return []
    return list(batch.get("blurbs", []))


def resolve_blurbs(variants: list[Path], styles: list[str], blurbs: list[str]) -> list[str]:
    """Map each variant to its one-line blurb via the same style resolution as picks.

    For each variant, resolve its style name with `_resolve_style`, find that
    style's index in `styles`, and pick `blurbs[that_index]`. Empty string when
    blurbs is missing/short or the variant doesn't map to a known style.
    """
    out: list[str] = []
    for i, v in enumerate(variants):
        resolved = _resolve_style(v, i, styles)
        blurb = ""
        if resolved is not None and resolved in styles:
            si = styles.index(resolved)
            if si < len(blurbs):
                blurb = blurbs[si] or ""
        out.append(blurb)
    return out


def _norm(s: str) -> str:
    """Collapse to lowercase alphanumerics for slug↔style comparison.

    'Modern Dark · blue spacious' and the slug '01-modern-dark-blue-spacious'
    both normalize to 'moderndarkbluespacious', so a Mode B/C variant whose
    folder order doesn't line up with state.json's `styles[]` array still maps
    to the right style name.
    """
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _resolve_style(variant: Path, idx: int, styles: list[str]) -> str | None:
    """Map a variant directory to its style name in `styles`.

    Match by normalized name first (order-independent), fall back to the
    positional style only when no name match exists. Positional mapping was
    the previous behavior and silently mis-highlighted picks whenever the
    filesystem sort order diverged from the state.json array order.
    """
    if not styles:
        return None
    disp = _norm(slug_to_display_name(variant.name))
    exact = [s for s in styles if _norm(s) == disp]
    if exact:
        return exact[0]
    prefix = [s for s in styles if disp.startswith(_norm(s)) or _norm(s).startswith(disp)]
    if prefix:
        # Longest normalized overlap wins (most specific style).
        return max(prefix, key=lambda s: len(_norm(s)))
    return styles[idx] if idx < len(styles) else None


def compute_picks(variants: list[Path], styles: list[str], user_picks: list[str]) -> tuple[list[bool], list[str]]:
    """Return (per-variant picked flags, leftover free-form picks).

    Each variant is mapped to its style name via `_resolve_style` (by
    normalized slug↔style match, not folder position). A variant is "picked"
    when its resolved style — or its own display name — appears verbatim in
    user_picks, or is a prefix of some pick string (handles cases like
    'Modern Dark · spacious ✓ FINAL' picking the 'Modern Dark · spacious'
    variant). Picks that don't map to any variant are returned as leftover
    notes for display in the sidebar.
    """
    picked = [False] * len(variants)
    matched_picks: set[int] = set()
    for i, v in enumerate(variants):
        candidates = {slug_to_display_name(v.name)}
        resolved = _resolve_style(v, i, styles)
        if resolved:
            candidates.add(resolved)
        for j, pick in enumerate(user_picks):
            for style in candidates:
                if pick == style or pick.startswith(style + " ") or pick.startswith(style + "·"):
                    picked[i] = True
                    matched_picks.add(j)
                    break
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


def render_section(variant_dir: Path, output_dir: Path, idx: int, picked: bool,
                   blurb: str = "", pasteback: str = "", url: str = "",
                   bundle: bool = False) -> str:
    rel = variant_dir.relative_to(output_dir)
    name = slug_to_display_name(variant_dir.name)
    src = f"{rel}/index.html"
    # Eagerly load the first two iframes so the page has visible content immediately;
    # later ones are lazy to keep the initial paint snappy.
    loading_attr = "" if idx < 2 else ' loading="lazy"'
    badge = '<span class="pick-badge">★ Picked</span>' if picked else ""
    section_class = "variant-section picked" if picked else "variant-section"
    intent = (f'\n          <div class="variant-intent">{html.escape(blurb)}</div>'
              if blurb else "")
    if bundle:
        content = (variant_dir / "index.html").read_text(encoding="utf-8")
        iframe = f'<iframe srcdoc="{html.escape(content, quote=True)}"{loading_attr}></iframe>'
    else:
        iframe = f'<iframe src="{src}"{loading_attr}></iframe>'
    return f"""<section class="{section_class}" id="variant-{idx}" data-idx="{idx}">
      <div class="variant-header">
        <div class="variant-title">
          <span class="variant-num">{idx + 1:02d}</span>
          <span class="variant-name">{name}</span>
          {badge}
        </div>{intent}
        <div class="variant-actions">
          <button class="act-pick" type="button" data-pasteback="{html.escape(pasteback, quote=True)}">✓ Pick this</button>
          <button class="act-link" type="button" data-url="{html.escape(url, quote=True)}">🔗 Copy link</button>
          <a href="{src}" target="_blank" rel="noopener">Open ↗</a>
        </div>
      </div>
      <div class="variant-frame">
        {iframe}
      </div>
      <div class="variant-notes"><textarea class="note-input" data-idx="{idx}" rows="2" placeholder="Your notes on this one (private to you) …"></textarea></div>
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
                    picked_flags: list[bool], leftover_picks: list[str],
                    blurbs: list[str] | None = None, pastebacks: list[str] | None = None,
                    urls: list[str] | None = None, bundle: bool = False) -> str:
    if not variants:
        return """<div class="empty-state">
    <h2>No variants found</h2>
    <p>Each variant must be a subdirectory containing an index.html file.</p>
    <p>Expected naming: <code>01-style-slug/index.html</code>, <code>02-style-slug/index.html</code>, etc.</p>
  </div>"""

    blurbs = blurbs or [""] * len(variants)
    pastebacks = pastebacks or [""] * len(variants)
    urls = urls or [""] * len(variants)
    toc = "\n      ".join(render_toc_item(v, i, picked_flags[i]) for i, v in enumerate(variants))
    sections = "\n    ".join(
        render_section(v, output_dir, i, picked_flags[i],
                       blurbs[i], pastebacks[i], urls[i], bundle)
        for i, v in enumerate(variants))
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
      <button id="copy-feedback" type="button">Copy all feedback</button>
    </div>
  </aside>
  <main id="main">
    {sections}
  </main>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", help="Directory containing variant subdirectories")
    parser.add_argument("--title", default="", help="Product title shown in the sidebar")
    parser.add_argument(
        "--public-base", default="",
        help="Base URL to prefix variant src paths with (e.g. http://localhost:8765). "
             "When empty, url == src (relative).",
    )
    parser.add_argument(
        "--bundle", action="store_true",
        help="Also write a single self-contained comparison-bundle.html where every "
             "variant iframe uses srcdoc (works via file:// with no server)",
    )
    parser.add_argument(
        "--bundle-output", default="",
        help="Path for the bundle file (default: <output-dir>/comparison-bundle.html)",
    )
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
    blurbs_arr = load_batch_blurbs(output_dir)
    picked_flags, leftover_picks = compute_picks(variants, styles, user_picks)
    blurbs = resolve_blurbs(variants, styles, blurbs_arr)

    base = args.public_base.rstrip("/")
    entries = []
    pastebacks = []
    urls = []
    for i, v in enumerate(variants):
        name = slug_to_display_name(v.name)
        num = f"{i + 1:02d}"
        slug = v.name
        src = f"{v.relative_to(output_dir)}/index.html"
        url = f"{base}/{src}" if base else src
        pasteback = f"Go with #{i + 1} — {num} {name}"
        entries.append({
            "idx": i,
            "num": num,
            "name": name,
            "slug": slug,
            "src": src,
            "url": url,
            "blurb": blurbs[i],
            "pasteback": pasteback,
        })
        pastebacks.append(pasteback)
        urls.append(url)
    variants_json = json.dumps(entries)

    body = render_app_body(variants, output_dir, title, picked_flags, leftover_picks,
                           blurbs, pastebacks, urls, bundle=False)

    rendered = (template
                .replace("__PRODUCT_TITLE__", title)
                .replace("__APP_BODY__", body)
                .replace("__VARIANTS_JSON__", variants_json))

    out_path = output_dir / "index.html"
    out_path.write_text(rendered, encoding="utf-8")

    if args.bundle:
        bundle_body = render_app_body(variants, output_dir, title, picked_flags,
                                      leftover_picks, blurbs, pastebacks, urls,
                                      bundle=True)
        bundle_rendered = (template
                           .replace("__PRODUCT_TITLE__", title)
                           .replace("__APP_BODY__", bundle_body)
                           .replace("__VARIANTS_JSON__", variants_json))
        bundle_path = (Path(args.bundle_output).resolve() if args.bundle_output
                       else output_dir / "comparison-bundle.html")
        bundle_path.write_text(bundle_rendered, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  Variants: {len(variants)}")
    for i, v in enumerate(variants):
        marker = "  ★" if picked_flags[i] else ""
        print(f"    {i + 1:02d}. {slug_to_display_name(v.name)}{marker}")
    if leftover_picks:
        print(f"  Picks (free-form, {len(leftover_picks)}):")
        for p in leftover_picks:
            print(f"    - {p}")
    if args.bundle:
        print(f"  Bundle (self-contained, file://-safe): {bundle_path}")
    print(f"\nOpen: file://{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
