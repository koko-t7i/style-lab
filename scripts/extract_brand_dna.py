#!/usr/bin/env python3
"""
Extract structured brand DNA from one or more public URLs.

Usage:
    python3 extract_brand_dna.py <url> [<url>...] [--output dna.json] [--timeout 15]

This script fetches the raw HTML of each URL using `curl -sL` (intentionally —
the Claude WebFetch tool prose-summarizes pages and loses inline color/font
detail; we need the raw markup), then mines:

  - Solid hex colors from `style="..."` inline declarations AND `<style>`
    block rules (class-based sites keep brand colors in `<style>`).
  - linear-gradient(...) / radial-gradient(...) declarations with stops + direction.
  - Google Fonts families from <link href="fonts.googleapis.com/css...family=...">.
  - CSS custom properties (`--name: value;`) inside <style> blocks.

Known social-media brand colors (LinkedIn, Twitter/X, FB, IG, etc.) are
filtered out before classification, as are the generic Elementor / WordPress
Gutenberg gradient swatches that ship on every Elementor site and would
otherwise pollute the brand-color extraction.

Output is a single JSON document with a programmatically composed `summary`
paragraph — that summary is the most important downstream signal: it's what
the style-lab "brand-tracking" mode hands to the design agent.

Schema (abbreviated):
    {
      "sources": [...], "fetched_at": "...",
      "solids":   [{"hex": "#5B7FFF", "freq": 12, "guessed_role": "brand-start",
                    "luminance": 0.45, "saturation": 0.78}, ...],
      "gradients":[{"def": "linear-gradient(135deg, ...)", "freq": 8,
                    "type": "linear", "direction": "135deg",
                    "stops": ["#...", "#..."], "guessed_role": "brand"}, ...],
      "fonts":    ["Inter", "JetBrains Mono"],
      "css_vars": [{"name": "--primary", "value": "#5B7FFF"}, ...],
      "summary":  "..."
    }

Run example:
    ./extract_brand_dna.py https://aurpay.net/ --output /tmp/aurpay-dna.json
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# --- Code reuse from the sibling script ---------------------------------------
# Inline copies kept here (instead of importing) so this script remains
# single-file runnable when invoked from arbitrary CWDs.

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
INLINE_STYLE_RE = re.compile(r'style="([^"]*)"', re.IGNORECASE)
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
GOOGLE_FONTS_RE = re.compile(r"fonts\.googleapis\.com/css2?\?family=([^&\"'\s>]+)")
CSS_VAR_RE = re.compile(r"(--[a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*([^;}\n]+?)\s*(?:;|})")


def normalize_hex(c: str) -> str:
    """Lower-case + expand 3-digit shorthand (#abc -> #aabbcc)."""
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


def hex_hue(c: str) -> float:
    """Return hue in degrees [0, 360)."""
    h = c.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0
    if mx == r:
        h_ = ((g - b) / d) % 6
    elif mx == g:
        h_ = (b - r) / d + 2
    else:
        h_ = (r - g) / d + 4
    return (h_ * 60.0) % 360.0


def hue_family(c: str) -> str:
    """Coarse hue family label (red/orange/yellow/green/cyan/blue/purple/pink)."""
    if hex_saturation(c) < 0.12:
        # near-grey
        return "neutral"
    h = hex_hue(c)
    if h < 15 or h >= 340:
        return "red"
    if h < 45:
        return "orange"
    if h < 70:
        return "yellow"
    if h < 170:
        return "green"
    if h < 200:
        return "cyan"
    if h < 255:
        return "blue"
    if h < 300:
        return "purple"
    return "pink"


# --- Filter lists -------------------------------------------------------------

# Social-media brand colors — these leak through inline styles on share/follow
# buttons but are NEVER the page brand. Stored as normalized #rrggbb.
SOCIAL_BRAND_HEXES = {
    "#0077b5",  # LinkedIn
    "#3c589a",  # Facebook (legacy)
    "#1877f2",  # Facebook (modern)
    "#55acee",  # Twitter (legacy)
    "#1da1f2",  # Twitter
    "#cc2329",  # YouTube (legacy)
    "#ff0000",  # YouTube
    "#ee8e2d",  # Reddit (alt)
    "#ff4500",  # Reddit
    "#55eb4c",  # WhatsApp (alt)
    "#25d366",  # WhatsApp
}

# Elementor / Gutenberg default palette swatches. If we see these specific
# rgb() triples inside a gradient, the gradient is boilerplate and gets dropped.
ELEMENTOR_RGB_STOPS = {
    "rgb(122,220,180)",
    "rgb(2,3,129)",
    "rgb(202,248,128)",
    "rgb(252,185,0)",
    "rgb(254,205,165)",
    "rgb(255,105,0)",
    "rgb(255,203,112)",
    "rgb(255,206,236)",
    "rgb(255,245,203)",
    "rgb(6,147,227)",
    "rgb(74,234,220)",
    # Additional companion stops that appear paired with the above in the
    # WP/Gutenberg gradient presets (`vivid-cyan-blue-to-vivid-purple`,
    # `very-light-gray-to-cyan-bluish-gray`, etc.).
    "rgb(155,81,224)",
    "rgb(0,208,130)",
    "rgb(207,46,46)",
    "rgb(238,238,238)",
    "rgb(169,184,195)",
    "rgb(151,120,209)",
    "rgb(207,42,186)",
    "rgb(238,44,130)",
    "rgb(251,105,98)",
    "rgb(254,248,76)",
    "rgb(152,150,240)",
    "rgb(254,45,45)",
    "rgb(107,0,62)",
    "rgb(199,81,192)",
    "rgb(65,88,208)",
    "rgb(182,227,212)",
    "rgb(51,167,181)",
    "rgb(113,206,126)",
    "rgb(40,116,252)",
}

# Instagram radial gradient stop signature — if we see all of these in one
# gradient, drop the whole gradient.
INSTAGRAM_STOPS = {"#fdf497", "#fd5949", "#d6249f", "#285aeb"}


def _strip_rgb_spaces(s: str) -> str:
    """Normalize 'rgb(122, 220, 180)' -> 'rgb(122,220,180)' for set comparison."""
    return re.sub(r"\s+", "", s)


# --- HTML fetch ---------------------------------------------------------------

def fetch_html(url: str, timeout: int) -> str:
    """Fetch via curl — preserves raw markup (no prose summarization)."""
    try:
        result = subprocess.run(
            ["curl", "-sL", url, "--max-time", str(timeout)],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        print(f"warning: curl timed out for {url}", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("error: curl not found on PATH", file=sys.stderr)
        sys.exit(2)
    if result.returncode != 0:
        print(f"warning: curl exit {result.returncode} for {url}: "
              f"{result.stderr.strip()[:200]}", file=sys.stderr)
    return result.stdout or ""


# --- Extraction ---------------------------------------------------------------

def extract_inline_style_hexes(html: str) -> Counter:
    """Hex frequencies from `style="..."` attributes only.

    Inline style attrs are actually-rendered brand colors (CTA bg, headline
    color) with no third-party-SVG spam — but class-based sites (Stripe,
    Linear, anything Tailwind-ish) put almost everything in `<style>` blocks
    or external CSS, so inline-only extraction comes back nearly empty for
    exactly the brands users name most. `extract_style_block_hexes` covers
    that case; this function stays inline-only so callers can weight the two
    sources differently if needed.
    """
    counts: Counter = Counter()
    for style_val in INLINE_STYLE_RE.findall(html):
        for hex_v in HEX_RE.findall(style_val):
            counts[normalize_hex(hex_v)] += 1
    return counts


def extract_style_block_hexes(html: str) -> Counter:
    """Hex frequencies from inside `<style>...</style>` block bodies.

    Catches class-based brand colors that never appear in an inline `style=`
    attribute. Gradients are handled separately (`extract_gradients` already
    scans the whole document), so this is solids only.
    """
    counts: Counter = Counter()
    for block in STYLE_BLOCK_RE.findall(html):
        for hex_v in HEX_RE.findall(block):
            counts[normalize_hex(hex_v)] += 1
    return counts


def _extract_balanced_call(text: str, fn_name: str) -> list[str]:
    """Find every `fn_name(...)` substring with balanced parens.

    `re` can't match balanced parens so we do a tiny manual scan.
    Returns the inside of the parens (without the leading fn_name).
    """
    out: list[str] = []
    needle = fn_name + "("
    i = 0
    while True:
        idx = text.find(needle, i)
        if idx == -1:
            break
        start = idx + len(needle)
        depth = 1
        j = start
        while j < len(text) and depth > 0:
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            j += 1
        if depth == 0:
            out.append(text[start:j - 1])
        i = j
    return out


_DIRECTION_RE = re.compile(
    r"^\s*((?:to\s+(?:top|bottom|left|right)(?:\s+(?:top|bottom|left|right))?)|(?:-?\d+(?:\.\d+)?(?:deg|rad|turn))|(?:circle(?:\s+at\s+[^,]+)?)|(?:ellipse(?:\s+at\s+[^,]+)?))\s*,",
    re.IGNORECASE,
)


def _split_top_level_commas(inner: str) -> list[str]:
    """Split a gradient body on commas at depth 0 (so rgb(...) stays intact)."""
    parts: list[str] = []
    depth = 0
    last = 0
    for i, ch in enumerate(inner):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[last:i])
            last = i + 1
    parts.append(inner[last:])
    return [p.strip() for p in parts if p.strip()]


_STOP_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
_STOP_RGB_RE = re.compile(r"rgba?\([^)]+\)", re.IGNORECASE)


def parse_gradient(grad_type: str, inner: str) -> dict | None:
    """Parse `linear-gradient(...)` / `radial-gradient(...)` body.

    Returns {def, type, direction, stops_raw, stops_hex} or None on parse fail.
    """
    # Direction prefix (optional)
    direction = "135deg" if grad_type == "linear" else "center"
    m = _DIRECTION_RE.match(inner)
    if m:
        direction = m.group(1).strip().lower()
        inner_body = inner[m.end():]
    else:
        inner_body = inner

    raw_stops = _split_top_level_commas(inner_body)
    stops_hex: list[str] = []
    stops_raw: list[str] = []
    for s in raw_stops:
        # A stop is "<color> [<position>]"; color is hex or rgb(...) or named.
        hex_match = _STOP_HEX_RE.search(s)
        rgb_match = _STOP_RGB_RE.search(s)
        if hex_match:
            stops_hex.append(normalize_hex(hex_match.group(0)))
            stops_raw.append(hex_match.group(0))
        elif rgb_match:
            stops_raw.append(_strip_rgb_spaces(rgb_match.group(0)))
        else:
            # named color / var() / unrecognized — record raw token
            stops_raw.append(s.split()[0] if s.split() else s)

    if not stops_raw:
        return None

    # Rebuild a clean canonical "def" string for de-dup / display.
    canonical = f"{grad_type}-gradient({direction}, " + ", ".join(stops_raw) + ")"
    return {
        "def": canonical,
        "type": grad_type,
        "direction": direction,
        "stops": stops_hex,            # only hex stops (for downstream JSON)
        "stops_raw": stops_raw,        # for filter checks
    }


def extract_gradients(html: str) -> list[dict]:
    """Pull every linear-/radial-gradient call from the document (with freq)."""
    bodies: list[tuple[str, str]] = []
    for body in _extract_balanced_call(html, "linear-gradient"):
        bodies.append(("linear", body))
    for body in _extract_balanced_call(html, "radial-gradient"):
        bodies.append(("radial", body))

    by_def: dict[str, dict] = {}
    for grad_type, body in bodies:
        parsed = parse_gradient(grad_type, body)
        if parsed is None:
            continue
        key = parsed["def"]
        if key in by_def:
            by_def[key]["freq"] += 1
        else:
            parsed["freq"] = 1
            by_def[key] = parsed
    return list(by_def.values())


def is_elementor_gradient(g: dict) -> bool:
    """True if the gradient contains any Elementor preset palette stop.

    The Elementor preset swatches are very specific RGB triples
    (e.g. `rgb(122,220,180)`); no real brand picks those exact values by
    chance. Even one match means the gradient came from the WP/Elementor
    theme defaults (typically the WP gradient preset variables) rather than
    the brand designer.
    """
    raw = set(g["stops_raw"])
    return any(s in ELEMENTOR_RGB_STOPS for s in raw)


def is_instagram_gradient(g: dict) -> bool:
    hex_set = set(g["stops"])
    return len(INSTAGRAM_STOPS & hex_set) >= 3


def filter_gradients(gradients: list[dict]) -> list[dict]:
    out = []
    for g in gradients:
        if is_elementor_gradient(g):
            continue
        if is_instagram_gradient(g):
            continue
        out.append(g)
    return out


def extract_google_fonts(html: str) -> list[str]:
    families: list[str] = []
    for m in GOOGLE_FONTS_RE.findall(html):
        # Family param may contain multiple families separated by `|` (v1 API)
        # or `&family=` (v2 API). Inside one family, `:` separates weights.
        # The url-encoded forms are %7C and %3A respectively.
        chunk = (m.replace("%7C", "|").replace("%7c", "|")
                  .replace("%3A", ":").replace("%3a", ":"))
        for fam in chunk.split("|"):
            family = fam.split(":")[0].replace("+", " ").strip()
            if family and family not in families:
                families.append(family)
    return families


def extract_css_vars(html: str) -> list[dict]:
    """Pull `--name: value;` from inline <style> blocks. Dedupes by name."""
    by_name: dict[str, str] = {}
    for block in STYLE_BLOCK_RE.findall(html):
        for name, value in CSS_VAR_RE.findall(block):
            name = name.strip()
            value = value.strip()
            if not value:
                continue
            # Keep first occurrence (top-of-document tokens win).
            if name not in by_name:
                by_name[name] = value
    return [{"name": n, "value": v} for n, v in by_name.items()]


# --- Classification (guessed roles) ------------------------------------------

def guess_solid_role(
    hex_v: str,
    is_brand_candidate: bool,
    gradient_hex_membership: dict[str, list[str]],
) -> str:
    """Assign a coarse semantic role to a solid hex.

    Order of precedence:
      1. If the hex is a stop in some gradient, return that gradient's
         membership label (e.g. "brand-start", "brand-end", "cyan").
      2. Luminance / saturation heuristics:
         - very dark (lum < 0.25)            -> "ink" (text color; may be
                                                 hue-tinted, e.g. #121437)
         - very light + low sat              -> "paper"
         - saturated mid-range               -> "brand" (one chosen via
                                                 `is_brand_candidate`) or
                                                 "accent" otherwise
         - light                             -> "surface"
         - mid-luminance, low sat            -> "muted"
    """
    if hex_v in gradient_hex_membership:
        return gradient_hex_membership[hex_v][0]

    lum = hex_luminance(hex_v)
    sat = hex_saturation(hex_v)

    # Dark text first — even a high-saturation dark color is ink (e.g. #121437).
    if lum < 0.25:
        return "ink"
    if lum >= 0.92 and sat < 0.15:
        return "paper"
    if sat >= 0.45:
        return "brand" if is_brand_candidate else "accent"
    if lum >= 0.70:
        return "surface"
    if lum <= 0.45:
        return "ink-soft"
    return "muted"


def guess_gradient_role(g: dict) -> str:
    """Coarse semantic label for a parsed gradient."""
    stops = g["stops"]
    if not stops:
        return "gradient"

    lums = [hex_luminance(s) for s in stops]
    sats = [hex_saturation(s) for s in stops]
    families = [hue_family(s) for s in stops if hue_family(s) != "neutral"]
    fam_set = set(families)

    avg_lum = sum(lums) / len(lums)
    max_sat = max(sats) if sats else 0.0

    # All stops pale → background wash.
    if all(l > 0.88 for l in lums):
        # Differentiate by which warm/cool tint dominates.
        if "pink" in fam_set or "red" in fam_set or "orange" in fam_set:
            return "bg-pink" if "pink" in fam_set else "bg-warm"
        return "bg-soft"

    # All stops dark → dark surface.
    if all(l < 0.20 for l in lums):
        return "dark"

    # Saturated + 2 stops crossing color families → brand identity.
    if len(stops) >= 2 and len(fam_set) >= 2 and max_sat >= 0.4:
        if fam_set <= {"blue", "purple", "pink"}:
            # Blue → purple is the canonical "fintech-web3 brand" move.
            if {"blue", "purple"} <= fam_set:
                return "brand"
            if {"purple", "pink"} <= fam_set or {"pink", "blue"} <= fam_set:
                return "brand-alt"
        if {"cyan", "blue"} <= fam_set:
            return "cyan"
        if {"pink", "orange"} <= fam_set or {"red", "orange"} <= fam_set or {"pink", "yellow"} <= fam_set:
            return "warm"
        if {"green", "cyan"} <= fam_set or {"green", "blue"} <= fam_set:
            return "fresh"
        return "brand"

    # Mono-family but saturated.
    if max_sat >= 0.4 and fam_set:
        fam = next(iter(fam_set))
        return f"{fam}-mono"

    # Mid-luminance neutral wash.
    if avg_lum < 0.45:
        return "mid-dark"
    return "soft"


def build_gradient_hex_membership(gradients: list[dict]) -> dict[str, list[str]]:
    """Map hex → list of role-derived labels (e.g. "brand-start") for gradient stops."""
    out: dict[str, list[str]] = {}
    for g in gradients:
        stops = g["stops"]
        if not stops:
            continue
        role = g.get("guessed_role") or guess_gradient_role(g)
        for i, hx in enumerate(stops):
            if i == 0:
                label = f"{role}-start"
            elif i == len(stops) - 1:
                label = f"{role}-end"
            else:
                label = f"{role}-mid{i}"
            out.setdefault(hx, []).append(label)
    return out


# --- Summary --------------------------------------------------------------

def compose_summary(
    solids: list[dict],
    gradients: list[dict],
    fonts: list[str],
    sources: list[str],
) -> str:
    """Compose a one-paragraph human-readable DNA summary.

    Order: identity gradient (if any) → solid roles → typeface. This matches
    the priority a downstream design agent should read.
    """
    parts: list[str] = []
    src = sources[0] if len(sources) == 1 else f"{len(sources)} sources"

    # Identity moment — prefer the highest-frequency "brand"-family gradient.
    brand_grad = next(
        (g for g in gradients if g.get("guessed_role", "").startswith("brand")),
        None,
    )
    if brand_grad is None and gradients:
        brand_grad = max(gradients, key=lambda g: g.get("freq", 0))
    if brand_grad:
        stops = brand_grad["stops"]
        if stops:
            fam_a = hue_family(stops[0]) if stops else "?"
            fam_b = hue_family(stops[-1]) if len(stops) > 1 else fam_a
            stops_str = " → ".join(stops)
            parts.append(
                f"Primary identity = {fam_a} → {fam_b} gradient "
                f"({stops_str}) at {brand_grad['direction']}, role "
                f"`{brand_grad.get('guessed_role', 'brand')}`"
            )
    else:
        # No gradient identity. Prefer the explicit `brand` solid; fall back to
        # the most-saturated solid that isn't ink/paper.
        brand_solid = next((s for s in solids if s["guessed_role"] == "brand"), None)
        if brand_solid is None:
            usable = [s for s in solids if s["guessed_role"] not in ("ink", "paper")]
            if usable:
                brand_solid = max(usable, key=lambda s: s["saturation"])
        if brand_solid:
            parts.append(
                f"Primary identity = solid {brand_solid['hex']} "
                f"({hue_family(brand_solid['hex'])}, role "
                f"`{brand_solid['guessed_role']}`)"
            )
        elif solids:
            top = solids[0]
            parts.append(
                f"Primary identity = solid {top['hex']} "
                f"({hue_family(top['hex'])}, role `{top['guessed_role']}`)"
            )

    if solids:
        role_lines = []
        seen_roles: set[str] = set()
        for s in solids[:6]:
            role = s["guessed_role"]
            if role in seen_roles:
                continue
            seen_roles.add(role)
            role_lines.append(f"{role}={s['hex']}")
        if role_lines:
            parts.append("Solids: " + ", ".join(role_lines))

    if fonts:
        primary = fonts[0]
        rest = fonts[1:3]
        if rest:
            parts.append(f"Typeface: {primary} (primary), plus {', '.join(rest)}")
        else:
            parts.append(f"Typeface: {primary}")

    if not parts:
        return f"No visual DNA could be extracted from {src}."

    return f"From {src}: " + ". ".join(parts) + "."


# --- Orchestration -----------------------------------------------------------

def extract_dna(urls: list[str], timeout: int) -> dict:
    all_html = []
    for url in urls:
        html = fetch_html(url, timeout)
        if html:
            all_html.append(html)
        else:
            print(f"warning: empty HTML for {url}", file=sys.stderr)

    combined = "\n".join(all_html)

    # 1. Solids — inline style attrs + <style> block rules (class-based sites
    #    keep brand colors in <style>, so inline-only misses them entirely).
    solid_counts = extract_inline_style_hexes(combined)
    solid_counts.update(extract_style_block_hexes(combined))
    # Filter social-media + pure-grey scaffolding noise we don't care about.
    for noise in list(SOCIAL_BRAND_HEXES):
        solid_counts.pop(noise, None)
    # 2. Gradients
    raw_gradients = extract_gradients(combined)
    gradients = filter_gradients(raw_gradients)
    # 3. Fonts
    fonts = extract_google_fonts(combined)
    # 4. CSS vars
    css_vars = extract_css_vars(combined)

    # Classify gradients first so we can use their stops to label solids.
    for g in gradients:
        g["guessed_role"] = guess_gradient_role(g)
    gradient_membership = build_gradient_hex_membership(gradients)

    top_solids = solid_counts.most_common(20)

    # Pre-pick THE brand candidate: of all solids that aren't gradient stops,
    # the one that is bright-enough (lum > 0.25) AND most saturated. There is
    # at most one `brand` token; everything else with high saturation becomes
    # `accent`.
    brand_candidate: str | None = None
    candidates = [
        h for h, _ in top_solids
        if h not in gradient_membership
        and 0.25 <= hex_luminance(h) <= 0.92
        and hex_saturation(h) >= 0.45
    ]
    if candidates:
        brand_candidate = max(candidates, key=hex_saturation)

    solids: list[dict] = []
    for hex_v, freq in top_solids:
        role = guess_solid_role(hex_v, hex_v == brand_candidate, gradient_membership)
        solids.append({
            "hex": hex_v,
            "freq": freq,
            "guessed_role": role,
            "luminance": round(hex_luminance(hex_v), 3),
            "saturation": round(hex_saturation(hex_v), 3),
        })

    # Sort gradients: brand-family first, then by frequency.
    def _grad_priority(g: dict) -> tuple[int, int]:
        role = g.get("guessed_role", "")
        prio = 0 if role.startswith("brand") else (1 if role in ("cyan", "warm") else 2)
        return (prio, -g.get("freq", 0))

    gradients.sort(key=_grad_priority)

    # Build final per-gradient dicts (drop the working-only stops_raw).
    gradients_out = [{
        "def": g["def"],
        "freq": g["freq"],
        "type": g["type"],
        "direction": g["direction"],
        "stops": g["stops"],
        "guessed_role": g["guessed_role"],
    } for g in gradients]

    summary = compose_summary(solids, gradients_out, fonts, urls)

    return {
        "sources": urls,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "solids": solids,
        "gradients": gradients_out,
        "fonts": fonts,
        "css_vars": css_vars,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("urls", nargs="+", help="One or more URLs to fetch")
    parser.add_argument("--output", help="Where to write the JSON (default: stdout)")
    parser.add_argument("--timeout", type=int, default=15,
                        help="curl --max-time seconds (default 15)")
    args = parser.parse_args()

    dna = extract_dna(args.urls, args.timeout)
    blob = json.dumps(dna, indent=2)

    if args.output:
        Path(args.output).write_text(blob, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
        print(f"  Sources:   {len(dna['sources'])}", file=sys.stderr)
        print(f"  Solids:    {len(dna['solids'])}", file=sys.stderr)
        print(f"  Gradients: {len(dna['gradients'])}", file=sys.stderr)
        print(f"  Fonts:     {dna['fonts']}", file=sys.stderr)
        print(f"  CSS vars:  {len(dna['css_vars'])}", file=sys.stderr)
        print(file=sys.stderr)
        print("Summary:", file=sys.stderr)
        print(f"  {dna['summary']}", file=sys.stderr)
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
