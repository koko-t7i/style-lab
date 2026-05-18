#!/usr/bin/env python3
"""
Extract a DESIGN.md draft from a chosen style-lab variant.

Usage:
    python3 extract_design_md.py <variant-dir> --name "Brand" [options]

Run this AFTER the user has picked a winning variant. It scans that variant's
index.html, programmatically extracts the design tokens (colors, typography,
rounded, spacing, components) into the YAML front-matter of DESIGN.md in the
getdesign.md / Google-Stitch *extended* canonical shape, and emits the
11-section markdown skeleton. The prose sections are seeded with
<!-- LLM-FILL: ... --> placeholders that the calling agent should replace
with real, variant-specific design rationale.

Output goes to the **repo root** by default — `git rev-parse --show-toplevel`
on the variant directory. If the variant isn't in a git repo, falls back to
`<variant-dir>/../DESIGN.md` (sibling of the variant folder). Override with
--output. Repo root is the right default because (a) DESIGN.md is the only
thing meant to be committed, (b) downstream coding agents look there first,
and (c) the rest of `.style-lab/` should be gitignored.

Spec lineage: Google Stitch DESIGN.md format (stitch.withgoogle.com/docs/
design-md/format/), extended-sections variant as used by getdesign.md /
github.com/VoltAgent/awesome-design-md. See references/design-md-spec.md.
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
    reference DESIGN.md uses.
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


# Canonical extended typography hierarchy (getdesign.md / Stitch). Each entry:
# (token, family-role, fontSize, fontWeight, lineHeight, letterSpacing).
# The extractor seeds families from the variant; sizes/weights are sensible
# defaults the calling agent tunes against what the page actually uses.
TYPO_SCALE = [
    ("display-xl", "display", "56px", 700, "1.05", "-1px"),
    ("display-lg", "display", "44px", 700, "1.1",  "-0.5px"),
    ("display-md", "display", "32px", 700, "1.15", "-0.3px"),
    ("title-lg",   "body",    "22px", 600, "1.3",  "0"),
    ("title-md",   "body",    "18px", 600, "1.4",  "0"),
    ("body-md",    "body",    "16px", 400, "1.6",  "0"),
    ("body-sm",    "body",    "14px", 400, "1.55", "0"),
    ("caption",    "body",    "13px", 500, "1.4",  "0"),
    ("code",       "mono",    "14px", 400, "1.6",  "0"),
    ("button",     "body",    "14px", 600, "1",    "0"),
    ("nav-link",   "body",    "14px", 500, "1.4",  "0"),
]
# Inner family names use single quotes — the whole value is emitted inside a
# double-quoted YAML scalar, so nested double quotes would break the YAML.
DISPLAY_FALLBACK = "Georgia, 'Times New Roman', serif"
BODY_FALLBACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
MONO_FALLBACK = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

# `spacing` and `rounded` are *designed* monotonic scales in the canonical
# format, not raw observations. Zipping observed paddings/radii onto the named
# scale produces non-monotonic, colliding garbage, so we always emit the
# conventional scale (identical to the getdesign.md corpus) and surface the
# observed values as a comment for the prose-fill agent to reconcile.
SPACING_SCALE = [("xxs", "4px"), ("xs", "8px"), ("sm", "12px"), ("md", "16px"),
                 ("lg", "24px"), ("xl", "32px"), ("xxl", "48px"), ("section", "96px")]
ROUNDED_SCALE = [("xs", "4px"), ("sm", "6px"), ("md", "8px"), ("lg", "12px"), ("xl", "16px")]

# Canonical component set, expressed against token names the color classifier
# can actually emit (paper/ink/accent/surface/muted...). `_pick` falls back so
# refs never dangle and `npx @google/design.md lint` stays green.
COMPONENT_TEMPLATE = [
    ("button-primary",   ["accent", "ink"],     ["paper", "on-primary"], "button",     "md"),
    ("button-secondary", ["paper", "surface"],  ["ink", "accent"],       "button",     "md"),
    ("feature-card",     ["surface", "paper"],  ["ink", "body"],         "title-md",   "lg"),
    ("top-nav",          ["paper", "surface"],  ["ink", "body"],         "nav-link",   None),
    ("text-input",       ["paper", "surface"],  ["ink", "body"],         "body-md",    "md"),
    ("cta-band",         ["accent", "ink"],     ["paper", "on-primary"], "display-md", "lg"),
    ("footer",           ["ink", "surface"],    ["paper", "muted"],      "body-sm",    None),
]


def _family(role: str, fonts: list[str]) -> str:
    """Build a `Primary, fallback` family string for a typography role.

    The primary face is quoted only if multi-word, and is dropped if it would
    just duplicate the head of the fallback stack.
    """
    disp = fonts[0] if fonts else None
    body = fonts[1] if len(fonts) > 1 else (fonts[0] if fonts else None)
    mono = fonts[2] if len(fonts) > 2 else None
    primary, fallback = (
        (disp, DISPLAY_FALLBACK) if role == "display"
        else (mono, MONO_FALLBACK) if role == "mono"
        else (body, BODY_FALLBACK)
    )
    if not primary:
        return fallback
    if primary.lower() == fallback.split(",")[0].strip().strip("'\"").lower():
        return fallback
    quoted = f"'{primary}'" if " " in primary else primary
    return f"{quoted}, {fallback}"


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

    color_tokens: list[str] = []
    if colors:
        retagged = _retag_solids_with_gradient_membership(colors, gradients)
        lines.append("colors:")
        for token, hex_v, comment in retagged:
            color_tokens.append(token)
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

    # Typography: full named hierarchy (display-xl … nav-link) regardless of
    # how many faces were extracted — downstream agents expect every token.
    lines.append("typography:")
    for token, role, size, weight, lh, ls in TYPO_SCALE:
        fam = _family(role, fonts)
        lines.append(
            f'  {token}: {{ fontFamily: "{fam}", fontSize: {size}, '
            f"fontWeight: {weight}, lineHeight: {lh}, letterSpacing: {ls} }}"
        )

    # rounded: canonical monotonic scale + pill/full; observed radii noted for
    # the agent to reconcile against what the variant actually uses.
    obs_r = f"  # observed in variant: {', '.join(radii)}" if radii else ""
    lines.append(f"rounded:{obs_r}")
    for key, val in ROUNDED_SCALE:
        lines.append(f'  {key}: "{val}"')
    lines.append('  pill: "9999px"')
    lines.append('  full: "9999px"')

    # spacing: canonical monotonic named scale; observed values noted.
    obs_s = f"  # observed in variant: {', '.join(spacing)}" if spacing else ""
    lines.append(f"spacing:{obs_s}")
    for key, val in SPACING_SCALE:
        lines.append(f'  {key}: "{val}"')

    def _pick(prefs: list[str]) -> str:
        for p in prefs:
            if p in color_tokens:
                return p
        return color_tokens[0] if color_tokens else "ink"

    lines.append("components:")
    for comp, bg_prefs, fg_prefs, typo, rnd in COMPONENT_TEMPLATE:
        lines.append(f"  {comp}:")
        lines.append(f'    backgroundColor: "{{colors.{_pick(bg_prefs)}}}"')
        lines.append(f'    textColor: "{{colors.{_pick(fg_prefs)}}}"')
        lines.append(f'    typography: "{{typography.{typo}}}"')
        if rnd:
            lines.append(f'    rounded: "{{rounded.{rnd}}}"')

    lines.append("---")
    return "\n".join(lines)


# The 11 canonical extended sections (getdesign.md / Stitch), in fixed order,
# with the same sub-headings the reference corpus uses. Plain `## Title`
# headings — no numeric prefix — matching the published files.
SECTION_BODIES = [
    ("Overview",
     "{description}\n\nVisual direction: **{style_name}**.\n\n"
     "<!-- LLM-FILL: 1-2 paragraphs on the surface/atmosphere story — what this design feels like, who it's for, the tone. Specific to *this* variant, never \"modern\"/\"clean\". -->\n\n"
     "**Key Characteristics:**\n\n"
     "<!-- LLM-FILL: 5-8 bullets, each citing a `{{token}}`: the defining color, the display face + its tracking, the signature visual move, the radius scale, the section rhythm. -->"),
    ("Colors",
     "### Brand & Accent\n\n"
     "<!-- LLM-FILL: One bullet per brand/accent color: bold name, `{{colors.x}}` ref, hex, and exactly when to use it (CTA bg / wordmark / callout). -->\n\n"
     "### Surface\n\n"
     "<!-- LLM-FILL: canvas / soft / card / dark surface tokens — what each floor is for and the band-alternation rhythm. -->\n\n"
     "### Text\n\n"
     "<!-- LLM-FILL: ink / body / muted / on-primary / on-dark — contrast strategy and the on-color text rules. -->\n\n"
     "### Semantic\n\n"
     "<!-- LLM-FILL: success / warning / error if present; say if they're absent on marketing surfaces. -->"),
    ("Typography",
     "### Font Family\n\n"
     "<!-- LLM-FILL: display vs body face and the editorial logic of the split; the fallback stacks. -->\n\n"
     "### Hierarchy\n\n"
     "<!-- LLM-FILL: a table — Token | Size | Weight | Line Height | Letter Spacing | Use — mirroring the `typography` front-matter, with the real on-page usage of each token. -->\n\n"
     "### Principles\n\n"
     "<!-- LLM-FILL: weight & tracking rules, what is non-negotiable (the serif/sans split, negative display tracking, etc.). -->\n\n"
     "### Note on Font Substitutes\n\n"
     "<!-- LLM-FILL: closest open-source substitutes for any licensed/proprietary face; skip if all faces are already open Google Fonts. -->"),
    ("Layout",
     "### Spacing System\n\n"
     "<!-- LLM-FILL: base unit + the named `{{spacing.*}}` tokens, section padding, card padding, CTA-band padding. -->\n\n"
     "### Grid & Container\n\n"
     "<!-- LLM-FILL: max content width, the column grid per content type, responsive column counts (desktop/tablet/mobile). -->\n\n"
     "### Whitespace Philosophy\n\n"
     "<!-- LLM-FILL: the pacing rationale — why this much air, what the rhythm communicates. -->"),
    ("Elevation & Depth",
     "<!-- LLM-FILL: a Level | Treatment | Use table (flat / hairline / soft / lifted) with concrete shadow/border values and when each applies. State explicitly if depth is rejected. -->\n\n"
     "### Decorative Depth\n\n"
     "<!-- LLM-FILL: glows, blurs, layered surfaces, hard offset blocks — or \"none; the system is strictly flat\". -->"),
    ("Shapes",
     "### Border Radius Scale\n\n"
     "<!-- LLM-FILL: the `{{rounded.*}}` scale and which radius each component uses; what shapes signal interactivity. -->\n\n"
     "### Photography & Illustrations\n\n"
     "<!-- LLM-FILL: image/illustration treatment — crop shape, stroke weight, art direction; or \"none; product chrome only\". -->"),
    ("Components",
     "<!-- LLM-FILL: one bold-key entry per component (`button-primary`, `feature-card`, `top-nav`, `text-input`, `cta-band`, `footer`, …). For each: the `{{token}}` bindings and what it MUST do and MUST NOT do. The most load-bearing section. -->"),
    ("Do's and Don'ts",
     "### Do\n\n"
     "<!-- LLM-FILL: 5-7 concrete, verifiable rules (\"16px+ body text\", \"96px between bands\", \"accent only on primary CTA + full-bleed callouts\"). -->\n\n"
     "### Don't\n\n"
     "<!-- LLM-FILL: 5-7 brand-breakers (\"no cool grays for canvas\", \"never bold the display serif\", \"don't repeat a surface mode in consecutive bands\"). -->"),
    ("Responsive Behavior",
     "### Breakpoints\n\n"
     "<!-- LLM-FILL: a Name | Width | Key Changes table (Mobile <768 / Tablet 768-1024 / Desktop 1024-1440 / Wide >1440). -->\n\n"
     "### Touch Targets\n\n"
     "<!-- LLM-FILL: minimum sizes per interactive component (button >= 40x40, input height, tappable card area). -->\n\n"
     "### Collapsing Strategy\n\n"
     "<!-- LLM-FILL: how nav and grids collapse mobile->desktop; what stays visually distinct at every breakpoint. -->\n\n"
     "### Image Behavior\n\n"
     "<!-- LLM-FILL: how code blocks / hero art / avatars behave at small widths (scroll vs wrap vs scale). -->"),
    ("Iteration Guide",
     "<!-- LLM-FILL: a numbered list of rules for safely extending the system — one component at a time, variants as separate `components:` entries, always `{{token}}` refs never inline hex, what is unbreakable, how to add emphasis without breaking the brand. -->"),
    ("Known Gaps",
     "<!-- LLM-FILL: an honest bullet list of what this document does NOT cover — licensed fonts unavailable as web fonts, animation/transition timings out of scope, states not observable from a static page, product-app surfaces beyond this marketing page. Keeps downstream agents from inventing authority. -->"),
]


def render_markdown(name: str, description: str, style_name: str) -> str:
    parts = [f"# {name}", ""]
    for title, body in SECTION_BODIES:
        parts.append(f"## {title}")
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
