#!/usr/bin/env python3
"""
Extract a DESIGN.md draft from a chosen style-lab variant.

Usage:
    python3 extract_design_md.py <variant-dir> --name "Brand" [options]

Run this AFTER the user has picked a winning variant. It scans that variant's
index.html, programmatically extracts the design tokens (colors, typography,
spacing, border-radius, etc.) into the YAML front-matter of DESIGN.md, and
emits a 9-section markdown skeleton. The prose sections are seeded with
<!-- LLM-FILL: ... --> placeholders that the calling agent should replace
with real, variant-specific design rationale.

Output goes to the **repo root** by default — `git rev-parse --show-toplevel`
on the variant directory. If the variant isn't in a git repo, falls back to
`<variant-dir>/../DESIGN.md` (sibling of the variant folder). Override with
--output. Repo root is the right default because (a) DESIGN.md is the only
thing meant to be committed, (b) downstream coding agents look there first,
and (c) the rest of `style-lab-output/` should be gitignored.

Spec reference: https://github.com/google-labs-code/design.md
Validate the result with:  npx @google/design.md lint <output>
"""
import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Sibling script — reuse its gradient parser instead of duplicating logic.
# Both files live in the same directory, so this works regardless of cwd
# (Python prepends the executed script's directory to sys.path).
from extract_brand_dna import (
    extract_gradients as _extract_gradients_raw,
    filter_gradients as _filter_gradients,
    guess_gradient_role as _guess_gradient_role,
    hue_family as _hue_family,
)

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
FONT_FAMILY_RE = re.compile(r"font-family:\s*([^;}\n]+)")
BORDER_RADIUS_RE = re.compile(r"border-radius:\s*([^;}\n]+)")
SPACING_RE = re.compile(r"(?:padding|margin|gap):\s*([^;}\n]+)")
GOOGLE_FONTS_RE = re.compile(r"fonts\.googleapis\.com/css2?\?family=([^&\"'\s]+)")
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL)

GENERIC_FONTS = {
    "inherit", "initial", "unset", "system-ui", "-apple-system",
    "BlinkMacSystemFont", "blinkmacsystemfont",
    "Segoe UI", "segoe ui", "sans-serif", "serif", "monospace", "ui-monospace",
    "Helvetica Neue", "Helvetica", "Arial",
}


def extract_styles(html: str) -> str:
    return "\n".join(STYLE_BLOCK_RE.findall(html))


def normalize_hex(c: str) -> str:
    c = c.lower()
    if len(c) == 4:
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


def hex_luminance(c: str) -> float:
    h = c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def hex_saturation(c: str) -> float:
    h = c.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == 0:
        return 0.0
    return (mx - mn) / mx


def extract_colors(css: str) -> list[tuple[str, int]]:
    counts = Counter(normalize_hex(c) for c in HEX_RE.findall(css))
    return counts.most_common()


def classify_colors(colors_with_freq: list[tuple[str, int]]) -> list[tuple[str, str]]:
    """Return (token_name, hex) pairs in token order (paper, ink, accent, ...)."""
    if not colors_with_freq:
        return []
    candidates = [c for c, _ in colors_with_freq[:10]]
    used: set[str] = set()
    out: list[tuple[str, str]] = []

    # paper: light + low-saturation + frequent
    light = sorted(candidates, key=lambda c: hex_luminance(c) - 0.5 * hex_saturation(c), reverse=True)
    if light:
        out.append(("paper", light[0])); used.add(light[0])

    # ink: dark + low-saturation
    dark_candidates = [c for c in candidates if c not in used]
    if dark_candidates:
        ink = min(dark_candidates, key=lambda c: hex_luminance(c) + 0.3 * hex_saturation(c))
        out.append(("ink", ink)); used.add(ink)

    # accent: most saturated remaining (only if actually saturated)
    sat_candidates = [c for c in candidates if c not in used]
    if sat_candidates:
        accent = max(sat_candidates, key=hex_saturation)
        if hex_saturation(accent) > 0.30:
            out.append(("accent", accent)); used.add(accent)

    # surface: another light tone (between paper and accent in luminance)
    surface_candidates = [c for c in candidates if c not in used and hex_luminance(c) > 0.7]
    if surface_candidates:
        out.append(("surface", surface_candidates[0])); used.add(surface_candidates[0])

    # muted / border: mid-luminance low-sat
    mid_candidates = sorted(
        [c for c in candidates if c not in used],
        key=lambda c: abs(hex_luminance(c) - 0.5) + hex_saturation(c),
    )
    role_pool = ["muted", "border", "subtle", "highlight"]
    for c in mid_candidates[:4]:
        if not role_pool:
            break
        out.append((role_pool.pop(0), c)); used.add(c)

    # leftovers
    leftover = [c for c in candidates if c not in used]
    for i, c in enumerate(leftover[:4], start=len(out) + 1):
        out.append((f"color{i:02d}", c))

    return out


def extract_fonts(html: str, css: str) -> list[str]:
    families: list[str] = []

    for m in GOOGLE_FONTS_RE.findall(html):
        family = m.split(":")[0].replace("+", " ")
        if family and family not in families:
            families.append(family)

    for m in FONT_FAMILY_RE.findall(css):
        primary = m.strip().split(",")[0].strip().strip("\"';")
        if not primary or primary.lower() in {f.lower() for f in GENERIC_FONTS}:
            continue
        if primary not in families:
            families.append(primary)

    return families


def normalize_dimension(v: str) -> str | None:
    v = v.strip()
    if not re.match(r"^\d+(?:\.\d+)?(px|rem|em|%)$", v):
        return None
    return v


def extract_radii(css: str) -> list[str]:
    out: list[str] = []
    for m in BORDER_RADIUS_RE.findall(css):
        for v in m.split():
            n = normalize_dimension(v)
            if n is not None:
                out.append(n)
    counted = Counter(out)
    # most common first, then ordered by numeric size ascending
    top = [v for v, _ in counted.most_common(8)]
    return sorted(top, key=_dim_to_px)


def extract_spacing(css: str) -> list[str]:
    out: list[str] = []
    for m in SPACING_RE.findall(css):
        for v in m.split():
            n = normalize_dimension(v)
            if n is not None and _dim_to_px(n) > 0:
                out.append(n)
    counted = Counter(out)
    top = [v for v, _ in counted.most_common(12)]
    return sorted(top, key=_dim_to_px)[:8]


def _dim_to_px(v: str) -> float:
    m = re.match(r"^([\d.]+)(px|rem|em|%)$", v)
    if not m:
        return 0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "rem" or unit == "em":
        return num * 16
    if unit == "%":
        return num
    return num


def extract_gradients(html: str) -> list[dict]:
    """Pull all linear-/radial-gradient declarations from the variant HTML.

    Returns a list of gradient dicts (see `extract_brand_dna.parse_gradient`)
    after filtering Elementor / Instagram boilerplate and dropping gradients
    with no hex stops (rgba-only translucent washes — those are decorative
    tints, not brand identity moments worth promoting to a token).
    """
    raw = _extract_gradients_raw(html)
    raw = _filter_gradients(raw)
    return [g for g in raw if g.get("stops")]


def classify_gradients(gradients_with_freq: list[dict]) -> list[tuple[str, dict]]:
    """Assign unique token names to gradients (e.g. "brand", "cyan", "warm").

    Strategy: classify each gradient via the brand-DNA role classifier, then
    de-duplicate names by appending a numeric suffix to collisions
    (`bg-soft` and `bg-soft-2` if two pale washes are present). Sorted with
    brand-family first, then by frequency descending — the order matches
    typical token-table reading order ("identity first, supporting cast next").
    """
    classified: list[tuple[str, dict]] = []
    name_counts: Counter = Counter()

    def _priority(g: dict) -> tuple[int, int]:
        role = _guess_gradient_role(g)
        prio = 0 if role.startswith("brand") else (1 if role in ("cyan", "warm") else 2)
        return (prio, -g.get("freq", 0))

    for g in sorted(gradients_with_freq, key=_priority):
        role = _guess_gradient_role(g)
        name_counts[role] += 1
        token_name = role if name_counts[role] == 1 else f"{role}-{name_counts[role]}"
        classified.append((token_name, g))
    return classified


def _format_gradient_def(g: dict) -> str:
    """Render `linear-gradient(135deg, #5B7FFF 0%, #A78BFA 100%)`-style string.

    The brand-DNA parser canonicalizes to comma-separated stops without
    explicit positions; for the DESIGN.md YAML we expand back to the
    `<color> <pos%>` form because that's what the manually-curated
    Aurpay reference DESIGN.md uses.
    """
    stops = g["stops"]
    if not stops:
        return g["def"]
    n = len(stops)
    if n == 1:
        positions = ["0%"]
    else:
        positions = [f"{int(round(i * 100 / (n - 1)))}%" for i in range(n)]
    body = ", ".join(f"{c.upper()} {p}" for c, p in zip(stops, positions))
    return f"{g['type']}-gradient({g['direction']}, {body})"


def _gradient_comment(g: dict) -> str:
    """Short trailing comment for a gradient YAML line (color flow + role)."""
    stops = g["stops"]
    role = _guess_gradient_role(g)
    if len(stops) >= 2:
        flow = f"{_hue_family(stops[0])} → {_hue_family(stops[-1])}"
    elif stops:
        flow = _hue_family(stops[0])
    else:
        flow = "unknown"
    return f"{flow} — guessed role {role}"


def _build_stop_label_map(
    gradients_named: list[tuple[str, dict]],
) -> dict[str, str]:
    """Map a hex string -> token-relationship label like "gradients.brand stop 0".

    A solid that also appears as a gradient stop gets its `colors:` token
    renamed to reflect that relationship, so the DESIGN.md reader can see
    "this `#5B7FFF` is the start of `gradients.brand`" at a glance instead
    of guessing.
    """
    out: dict[str, str] = {}
    for name, g in gradients_named:
        for i, hx in enumerate(g["stops"]):
            label = f"gradients.{name} stop {i}"
            # Keep the first occurrence — earlier (higher-priority) gradients
            # win the relationship label.
            out.setdefault(hx, label)
    return out


def _stop_role_token(name: str, idx: int, n_stops: int) -> str:
    """Token name for a solid that's also a gradient stop ("brand-start", etc.)."""
    if n_stops == 1:
        return name
    if idx == 0:
        return f"{name}-start"
    if idx == n_stops - 1:
        return f"{name}-end"
    return f"{name}-mid{idx}"


def _retag_solids_with_gradient_membership(
    colors: list[tuple[str, str]],
    gradients_named: list[tuple[str, dict]],
) -> list[tuple[str, str, str | None]]:
    """Return (token, hex, comment_or_None) — renames tokens that are gradient stops.

    `accent: "#5B7FFF"` becomes `brand-start: "#5B7FFF"  # gradients.brand stop 0`
    so the relationship between the flat token and its gradient is explicit.
    Also avoids the bug where the same color appears as both a flat accent
    and a gradient stop with no obvious link.
    """
    # Map hex -> (gradient_name, stop_index, total_stops) for first match.
    stop_map: dict[str, tuple[str, int, int]] = {}
    for name, g in gradients_named:
        for i, hx in enumerate(g["stops"]):
            stop_map.setdefault(hx, (name, i, len(g["stops"])))

    out: list[tuple[str, str, str | None]] = []
    used_tokens: set[str] = set()
    for token, hex_v in colors:
        hx_norm = hex_v.lower()
        if hx_norm in stop_map:
            grad_name, idx, n = stop_map[hx_norm]
            new_token = _stop_role_token(grad_name, idx, n)
            # De-dup if the same renamed token would collide.
            base = new_token
            k = 2
            while new_token in used_tokens:
                new_token = f"{base}-{k}"
                k += 1
            comment = f"gradients.{grad_name} stop {idx}"
            out.append((new_token, hex_v, comment))
            used_tokens.add(new_token)
        else:
            base = token
            t = token
            k = 2
            while t in used_tokens:
                t = f"{base}-{k}"
                k += 1
            out.append((t, hex_v, None))
            used_tokens.add(t)
    return out


def render_yaml(name: str, description: str, style_name: str,
                colors: list[tuple[str, str]], fonts: list[str],
                spacing: list[str], radii: list[str],
                gradients: list[tuple[str, dict]] | None = None) -> str:
    lines = ["---", "version: alpha", f"name: {name}"]
    if description:
        lines.append(f'description: "{description}"')
    if style_name:
        lines.append(f'# Visual direction: {style_name}')

    gradients = gradients or []

    if colors:
        retagged = _retag_solids_with_gradient_membership(colors, gradients)
        lines.append("colors:")
        for token, hex_v, comment in retagged:
            if comment:
                lines.append(f'  {token}: "{hex_v}"  # {comment}')
            else:
                lines.append(f'  {token}: "{hex_v}"')

    if gradients:
        lines.append("gradients:")
        for token, g in gradients:
            lines.append(
                f'  {token}: "{_format_gradient_def(g)}"  # {_gradient_comment(g)}'
            )

    if fonts:
        lines.append("typography:")
        lines.append(f'  display: {{ family: "{fonts[0]}", weight: 700 }}')
        body_font = fonts[1] if len(fonts) > 1 else fonts[0]
        lines.append(f'  body: {{ family: "{body_font}", weight: 400 }}')
        if len(fonts) > 2:
            lines.append(f'  mono: {{ family: "{fonts[2]}", weight: 400 }}')

    if spacing:
        lines.append("spacing:")
        for i, s in enumerate(spacing, start=1):
            lines.append(f'  {i}: "{s}"')

    if radii:
        lines.append("rounded:")
        keys = ["sm", "md", "lg", "xl", "full"]
        for i, r in enumerate(radii[:5]):
            lines.append(f'  {keys[i]}: "{r}"')

    lines.append("---")
    return "\n".join(lines)


SECTION_BODIES = [
    ("Overview",
     "{description}\n\nVisual direction: **{style_name}**.\n\n"
     "<!-- LLM-FILL: 1-2 short paragraphs on what this design is meant to feel like, who it's for, and the tone of voice. Specific to *this* variant — don't write generic copy. -->"),
    ("Colors",
     "Token reference: see `colors` and `gradients` in front-matter.\n\n"
     "<!-- LLM-FILL: Walk through the solids vs the gradients — which colors are flat tokens for text/borders, which are gradient identity moments. Mention which gradient is THE brand identity and where it must appear (CTA / wordmark / dashboard halo / etc.). Also: contrast strategy, palette restrictions, which solo solids are sanctioned and which only exist inside a gradient. -->"),
    ("Typography",
     "Token reference: see `typography` in front-matter.\n\n"
     "<!-- LLM-FILL: Display vs body face, weight & letter-spacing conventions, hierarchy rules (h1 size, line-height conventions, paragraph rhythm). Note any special treatments (drop caps, all-caps tracking, monospace use). -->"),
    ("Layout",
     "<!-- LLM-FILL: How content is structured — grid behavior (number of cols, gutters), max content widths, vertical rhythm, alignment philosophy (left/centered/asymmetric), density (spacious vs dense). Reference spacing tokens. -->"),
    ("Elevation & Depth",
     "<!-- LLM-FILL: Shadow philosophy — flat? layered? hard offset blocks? glass with backdrop-filter? List specific shadow values used and when each applies. State explicitly if depth is avoided. -->"),
    ("Shapes",
     "Token reference: see `rounded` in front-matter.\n\n"
     "<!-- LLM-FILL: Corner radius philosophy — sharp/rounded/mixed. What shapes signal interactivity. Any unusual shape language (bento tiles, blob backgrounds, ASCII boxes). -->"),
    ("Components",
     "<!-- LLM-FILL: Describe key components — primary button, card, nav, form input. Use token references where possible (e.g. `bg: ink`, `radius: rounded.sm`). Be opinionated: for each component say what it MUST do and what it MUST NOT do. -->"),
    ("Do's and Don'ts",
     "### Do\n\n"
     "<!-- LLM-FILL: 3-5 specific things to ALWAYS do (e.g. \"use ink on paper for body text at 16px+\", \"maintain 24px vertical rhythm\"). -->\n\n"
     "### Don't\n\n"
     "<!-- LLM-FILL: 3-5 things that break the brand (e.g. \"no gradients\", \"never use accent for body text\", \"don't introduce a second sans-serif\"). -->"),
]


def render_markdown(name: str, description: str, style_name: str) -> str:
    parts = [f"# {name}", ""]
    for i, (title, body) in enumerate(SECTION_BODIES, start=1):
        parts.append(f"## {i}. {title}")
        parts.append("")
        parts.append(body.format(description=description or "—", style_name=style_name or "—"))
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def find_repo_root(start: Path) -> Path | None:
    """Return the git toplevel containing `start`, or None if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    path = result.stdout.strip()
    return Path(path) if path else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("variant_dir", help="Path to the chosen variant directory")
    parser.add_argument("--name", required=True, help="Brand / product name (goes in front-matter)")
    parser.add_argument("--description", default="", help="One-line product pitch")
    parser.add_argument("--style-name", default="", help='Display name of the chosen style (e.g. "Brutalism")')
    parser.add_argument(
        "--output",
        help="Where to write DESIGN.md (default: <repo-root>/DESIGN.md if the "
        "variant is inside a git repo, else <variant-dir>/../DESIGN.md)",
    )
    args = parser.parse_args()

    variant_dir = Path(args.variant_dir).resolve()
    if not variant_dir.is_dir():
        print(f"error: {variant_dir} is not a directory", file=sys.stderr)
        return 1

    html_path = variant_dir / "index.html"
    if not html_path.exists():
        print(f"error: no index.html in {variant_dir}", file=sys.stderr)
        return 1

    style_name = args.style_name or re.sub(r"^\d+[-_]", "", variant_dir.name).replace("-", " ").title()

    html = html_path.read_text(encoding="utf-8", errors="ignore")
    css = extract_styles(html)

    color_freq = extract_colors(css)
    classified = classify_colors(color_freq)
    fonts = extract_fonts(html, css)
    spacing = extract_spacing(css)
    radii = extract_radii(css)
    # Gradients live in inline-style attributes too, not just <style> blocks
    # (e.g. background-image="linear-gradient(...)" on the hero), so scan
    # the whole HTML body, not just `css`.
    gradients_raw = extract_gradients(html)
    gradients_named = classify_gradients(gradients_raw)

    yaml = render_yaml(args.name, args.description, style_name, classified, fonts, spacing, radii, gradients_named)
    md = render_markdown(args.name, args.description, style_name)
    full = yaml + "\n\n" + md

    if args.output:
        output = Path(args.output)
        output_origin = "explicit --output"
    else:
        repo_root = find_repo_root(variant_dir)
        if repo_root is not None:
            output = repo_root / "DESIGN.md"
            output_origin = f"repo root ({repo_root})"
        else:
            output = variant_dir.parent / "DESIGN.md"
            output_origin = "variant parent (no enclosing git repo)"

    pre_existed = output.exists()
    output.write_text(full, encoding="utf-8")

    if pre_existed:
        print(f"Overwrote existing {output}")
    else:
        print(f"Wrote {output}")
    print(f"  Destination:    {output_origin}")
    print(f"  Source variant: {variant_dir.name}")
    print(f"  Colors:    {len(color_freq)} unique → {len(classified)} tokens")
    for token, hex_v in classified:
        print(f"    {token:>10}: {hex_v}")
    if gradients_named:
        print(f"  Gradients: {len(gradients_raw)} extracted → {len(gradients_named)} named tokens")
        for token, g in gradients_named:
            print(f"    {token:>10}: {_format_gradient_def(g)}")
    print(f"  Fonts:     {fonts}")
    print(f"  Spacing:   {spacing}")
    print(f"  Radii:     {radii}")
    print()
    print("Next:")
    print("  1. The file contains <!-- LLM-FILL: ... --> placeholders. Replace each")
    print("     with real prose specific to this variant — read the variant's HTML")
    print("     to ground your descriptions in what is actually on the page.")
    print(f"  2. (Optional) Validate: npx @google/design.md lint {output}")
    print("  3. Hand the file off — it's what coding agents will read on every future")
    print("     prompt to keep the product on-brand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
