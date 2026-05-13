#!/usr/bin/env python3
"""
Validate a single style-lab variant directory and flag quality issues.

Usage:
    python3 validate_variant.py <variant-dir> [--state state.json] [--quiet]

The variant directory is expected to be of the form
<output-dir>/batch-N/NN-style-slug/ and to contain index.html. If --state
is omitted, the parent output directory's state.json is auto-discovered at
<variant-dir>/../../state.json.

Checks run (severity in brackets):

  [error]   no-lorem-ipsum     - no occurrences of lorem/Lorem/LOREM
  [error]   html-parses        - html.parser accepts the document
  [error]   has-style-block    - at least one <style> block (self-contained)
  [error]   min-size           - file >= 5KB (smaller is almost certainly a stub)
  [error]   has-cta-text       - state.shared_copy.cta_primary present in HTML
  [error]   headline-verbatim  - state.shared_copy.headline appears verbatim
  [error]   subhead-verbatim   - state.shared_copy.subhead appears verbatim
  [error]   brand-name-present - state.product.name appears at least once

  [warn]    no-cdn-imports     - no unexpected CDN hosts (fonts.* allowed)
  [warn]    important-overuse  - !important appears <= 5 times
  [warn]    brand-color-present - hex colors mentioned in reference_summary appear

Writes <variant-dir>/validation.json and prints a one-line-per-check summary.
Exit code is 0 if all error-severity checks pass (warnings never affect the
exit code) and 1 otherwise.
"""
import argparse
import datetime as _dt
import html.parser
import json
import re
import sys
from pathlib import Path

MIN_SIZE_BYTES = 5 * 1024
IMPORTANT_LIMIT = 5
ALLOWED_CDN_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
# Asset references only — restricting to src/href/url() avoids false-positives
# from example URLs that appear in code-block content.
ASSET_URL_RE = re.compile(
    r"""(?:src|href)\s*=\s*['"](https?://[^'"\s]+)['"]"""
    r"""|url\(\s*['"]?(https?://[^'")\s]+)""",
    re.IGNORECASE,
)
HOSTNAME_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)", re.IGNORECASE)


class _CollectingParser(html.parser.HTMLParser):
    """A lenient HTMLParser that records errors instead of raising.

    Records text content as it goes so the verbatim-copy checks can compare
    against rendered text rather than raw HTML (variants legitimately wrap
    brand-name spans, em emphasis, etc. inside headlines).
    """

    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    SKIP_TEXT_IN = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.stack: list[tuple[str, int, int]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag.lower() in self.VOID_ELEMENTS:
            return
        self.stack.append((tag.lower(), *self.getpos()))

    def handle_startendtag(self, tag: str, attrs):  # type: ignore[override]
        # XHTML-style self-closing (<br />, <meta ... />): nothing to push/pop.
        return

    def handle_endtag(self, tag: str):  # type: ignore[override]
        t = tag.lower()
        # XHTML-style void elements often emit a phantom end-tag through
        # html.parser; absorb them silently rather than flagging "stray".
        if t in self.VOID_ELEMENTS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == t:
                for unclosed in self.stack[i + 1:]:
                    self.errors.append(
                        f"unclosed <{unclosed[0]}> opened at line {unclosed[1]}:{unclosed[2]}"
                    )
                self.stack = self.stack[:i]
                return
        self.errors.append(f"stray </{t}> at line {self.getpos()[0]}:{self.getpos()[1]}")

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1][0] in self.SKIP_TEXT_IN:
            return
        self.text_parts.append(data)

    def error(self, message):  # type: ignore[override]
        # HTMLParser.error is only called on very old Pythons, but be safe.
        self.errors.append(message)


def _record(name: str, passed: bool, evidence: str, severity: str) -> dict:
    return {"name": name, "passed": passed, "evidence": evidence, "severity": severity}


def _check_no_lorem(html_text: str) -> dict:
    count = len(re.findall(r"lorem", html_text, flags=re.IGNORECASE))
    return _record(
        "no-lorem-ipsum",
        passed=(count == 0),
        evidence=f"{count} occurrences",
        severity="error",
    )


def _parse_html(html_text: str) -> _CollectingParser:
    parser = _CollectingParser()
    parser.feed(html_text)
    parser.close()
    # Anything still on the stack at EOF is also an unclosed tag.
    for unclosed in parser.stack:
        parser.errors.append(
            f"unclosed <{unclosed[0]}> opened at line {unclosed[1]}:{unclosed[2]}"
        )
    return parser


def _check_html_parses(parser: _CollectingParser) -> dict:
    if parser.errors:
        first = parser.errors[0]
        more = f" (+{len(parser.errors) - 1} more)" if len(parser.errors) > 1 else ""
        return _record("html-parses", False, first + more, "error")
    return _record("html-parses", True, "valid", "error")


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _check_style_block(html_text: str) -> dict:
    count = len(re.findall(r"<style[\s>]", html_text, flags=re.IGNORECASE))
    return _record(
        "has-style-block",
        passed=(count >= 1),
        evidence=f"{count} <style> tags",
        severity="error",
    )


def _check_min_size(path: Path) -> dict:
    size = path.stat().st_size
    return _record(
        "min-size",
        passed=(size >= MIN_SIZE_BYTES),
        evidence=f"{size} bytes (min {MIN_SIZE_BYTES})",
        severity="error",
    )


def _check_verbatim(name: str, rendered_text: str, needle: str | None) -> dict | None:
    """Match `needle` against the parsed text body (whitespace-normalized).

    The rendered text strips tags + decodes entities, so headlines that wrap a
    brand-name in <em>...</em> still pass this check. We're verifying copy
    fidelity, not markup fidelity.
    """
    if not needle:
        return None
    haystack = _normalize_ws(rendered_text)
    target = _normalize_ws(needle)
    offset = haystack.find(target)
    if offset >= 0:
        return _record(name, True, f"found at text offset {offset}", "error")
    snippet = needle if len(needle) <= 60 else needle[:57] + "..."
    return _record(name, False, f"not found: {snippet!r}", "error")


def _check_cta_text(rendered_text: str, cta: str | None) -> dict | None:
    if not cta:
        return None
    found = _normalize_ws(cta) in _normalize_ws(rendered_text)
    return _record(
        "has-cta-text",
        passed=found,
        evidence=("found" if found else f"not found: {cta!r}"),
        severity="error",
    )


def _check_brand_name(rendered_text: str, product_name: str | None) -> dict | None:
    if not product_name:
        return None
    count = _normalize_ws(rendered_text).count(_normalize_ws(product_name))
    return _record(
        "brand-name-present",
        passed=(count >= 1),
        evidence=f"{count} occurrences",
        severity="error",
    )


def _check_no_cdn(html_text: str) -> dict:
    """Look only at asset-loading sites (src/href/url()), not arbitrary text."""
    hosts: set[str] = set()
    for match in ASSET_URL_RE.finditer(html_text):
        url = match.group(1) or match.group(2) or ""
        m = HOSTNAME_RE.match(url)
        if m:
            hosts.add(m.group(1).lower())
    unexpected = sorted(h for h in hosts if h not in ALLOWED_CDN_HOSTS)
    if not unexpected:
        return _record("no-cdn-imports", True, "no external hosts", "warning")
    return _record(
        "no-cdn-imports",
        False,
        "unexpected hosts: " + ", ".join(unexpected),
        "warning",
    )


def _check_important_overuse(html_text: str) -> dict:
    count = html_text.count("!important")
    return _record(
        "important-overuse",
        passed=(count <= IMPORTANT_LIMIT),
        evidence=f"{count} uses (limit {IMPORTANT_LIMIT})",
        severity="warning",
    )


def _check_brand_colors(html_text: str, reference_summary: str | None) -> dict | None:
    if not reference_summary:
        return None
    expected_raw = HEX_RE.findall(reference_summary)
    # de-dup while preserving order, normalize to uppercase for comparison
    seen: list[str] = []
    seen_norm: set[str] = set()
    for h in expected_raw:
        norm = h.upper()
        if norm not in seen_norm:
            seen.append(h)
            seen_norm.add(norm)
    if not seen:
        return None
    html_hexes = {h.upper() for h in HEX_RE.findall(html_text)}
    found = [h for h in seen if h.upper() in html_hexes]
    missing = [h for h in seen if h.upper() not in html_hexes]
    expected_str = ", ".join(seen)
    if not found:
        evidence = f"expected {expected_str}; found NONE"
    elif missing:
        evidence = (
            f"expected {expected_str}; "
            f"found {', '.join(found)}; missing {', '.join(missing)}"
        )
    else:
        evidence = f"expected {expected_str}; all present"
    return _record(
        "brand-color-present",
        passed=bool(found),
        evidence=evidence,
        severity="warning",
    )


def _discover_state(variant_dir: Path) -> Path | None:
    candidate = variant_dir.parent.parent / "state.json"
    return candidate if candidate.exists() else None


def _load_state(state_path: Path | None) -> dict | None:
    if state_path is None:
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"warn: could not read {state_path}: {e}", file=sys.stderr)
        return None


def _print_summary(records: list[dict], summary: dict, quiet: bool) -> None:
    if quiet:
        return
    for rec in records:
        if rec["severity"] == "warning":
            mark = "✓" if rec["passed"] else "⚠"
        else:
            mark = "✓" if rec["passed"] else "✗"
        line = f"{mark} {rec['name']}"
        if not rec["passed"]:
            line += f" — {rec['evidence']}"
        print(line)
    overall = "PASS" if summary["overall_pass"] else "FAIL"
    print(
        f"\n{summary['errors_passed']}/"
        f"{summary['errors_passed'] + summary['errors_failed']} errors passed · "
        f"{summary['warnings_failed']}/{summary['warnings_total']} warnings failed · "
        f"OVERALL: {overall}"
    )


def validate(variant_dir: Path, state_path: Path | None) -> dict:
    index_path = variant_dir / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"{index_path} not found")
    html_text = index_path.read_text(encoding="utf-8", errors="replace")
    parser = _parse_html(html_text)
    rendered_text = "".join(parser.text_parts)

    records: list[dict] = [
        _check_no_lorem(html_text),
        _check_html_parses(parser),
        _check_style_block(html_text),
        _check_min_size(index_path),
    ]

    state = _load_state(state_path)
    if state is not None:
        shared = state.get("shared_copy") or {}
        product = state.get("product") or {}
        cta_rec = _check_cta_text(rendered_text, shared.get("cta_primary"))
        if cta_rec:
            records.append(cta_rec)
        for name, key in (
            ("headline-verbatim", "headline"),
            ("subhead-verbatim", "subhead"),
        ):
            rec = _check_verbatim(name, rendered_text, shared.get(key))
            if rec:
                records.append(rec)
        brand_rec = _check_brand_name(rendered_text, product.get("name"))
        if brand_rec:
            records.append(brand_rec)

    # Warnings (always run, regardless of state.json)
    records.append(_check_no_cdn(html_text))
    records.append(_check_important_overuse(html_text))

    # brand-color-present needs the most recent reference_summary on the variant's batch
    ref_summary = _resolve_reference_summary(variant_dir, state)
    color_rec = _check_brand_colors(html_text, ref_summary)
    if color_rec:
        records.append(color_rec)

    errors_passed = sum(1 for r in records if r["severity"] == "error" and r["passed"])
    errors_failed = sum(1 for r in records if r["severity"] == "error" and not r["passed"])
    warnings_total = sum(1 for r in records if r["severity"] == "warning")
    warnings_failed = sum(
        1 for r in records if r["severity"] == "warning" and not r["passed"]
    )

    summary = {
        "errors_passed": errors_passed,
        "errors_failed": errors_failed,
        "warnings_total": warnings_total,
        "warnings_failed": warnings_failed,
        "overall_pass": errors_failed == 0,
    }
    return {
        "variant": variant_dir.name,
        "variant_dir": str(variant_dir),
        "validated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "checks": records,
        "summary": summary,
    }


def _resolve_reference_summary(variant_dir: Path, state: dict | None) -> str | None:
    """Pick the most relevant reference_summary for this variant.

    Strategy: find the batch in state.batches whose `dir` matches the variant's
    parent directory name. Fall back to any state-level reference_summary.
    """
    if not state:
        return None
    batch_dir_name = variant_dir.parent.name
    for batch in state.get("batches", []) or []:
        if batch.get("dir") == batch_dir_name:
            rs = batch.get("reference_summary")
            if rs:
                return rs
            break
    return state.get("reference_summary")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "variant_dir",
        help="Variant directory (e.g. <output>/batch-1/01-modern-dark/)",
    )
    parser.add_argument(
        "--state",
        help="Path to state.json (default: <variant-dir>/../../state.json if it exists)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress stdout summary (still writes validation.json)"
    )
    args = parser.parse_args()

    variant_dir = Path(args.variant_dir).resolve()
    if not variant_dir.is_dir():
        print(f"error: {variant_dir} is not a directory", file=sys.stderr)
        return 1
    if not (variant_dir / "index.html").exists():
        print(f"error: {variant_dir}/index.html not found", file=sys.stderr)
        return 1

    if args.state:
        state_path: Path | None = Path(args.state).resolve()
        if not state_path.exists():
            print(f"warn: --state {state_path} does not exist; continuing without it",
                  file=sys.stderr)
            state_path = None
    else:
        state_path = _discover_state(variant_dir)

    try:
        report = validate(variant_dir, state_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out_path = variant_dir / "validation.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    _print_summary(report["checks"], report["summary"], args.quiet)

    return 0 if report["summary"]["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
