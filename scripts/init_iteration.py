#!/usr/bin/env python3
"""
Migrate a flat style-lab output directory to the batched layout.

Usage:
    python3 init_iteration.py <output-dir> --name "<ProductName>" \\
        [--description "..."] [--commit] [--quiet]

The flat layout (older skill workflow) looks like:

    <output-dir>/
        01-some-style/index.html
        02-other-style/index.html
        index.html               # comparison page (optional)
        SUMMARY.txt              # optional

The batched layout (current workflow) looks like:

    <output-dir>/
        state.json
        batch-1/
            01-some-style/index.html
            02-other-style/index.html
            index.html
            SUMMARY.txt

This script plans (default) or performs (--commit) the migration. Dry-run is
the default because the move is irreversible without a backup; users must
opt in to writes.

Already-migrated directories (those with state.json or any batch-N/ subdir)
print "Already migrated, no action needed" and exit 0.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

VARIANT_RE = re.compile(r"^\d+[-_].+$")
BATCH_RE = re.compile(r"^batch-\d+$")


def slug_to_display_name(slug: str) -> str:
    """Match scripts/generate_index.py's slug_to_display_name()."""
    name = re.sub(r"^\d+[-_]", "", slug)
    name = name.replace("-", " ").replace("_", " ")
    return name.title()


def find_variant_dirs(output_dir: Path) -> list[Path]:
    """Subdirectories matching NN-* and containing index.html."""
    out: list[Path] = []
    for child in sorted(output_dir.iterdir()):
        if child.is_dir() and VARIANT_RE.match(child.name) and (child / "index.html").exists():
            out.append(child)
    return out


def is_already_migrated(output_dir: Path) -> bool:
    if (output_dir / "state.json").exists():
        return True
    for child in output_dir.iterdir():
        if child.is_dir() and BATCH_RE.match(child.name):
            return True
    return False


def is_flat_layout(output_dir: Path) -> bool:
    """Flat = no state.json, no batch-N/, but has at least one variant subdir."""
    if is_already_migrated(output_dir):
        return False
    return len(find_variant_dirs(output_dir)) > 0


def build_state(name: str, description: str, variants: list[Path]) -> dict:
    return {
        "product": {
            "name": name,
            "description": description or "",
        },
        "shared_copy": {},
        "batches": [
            {
                "n": 1,
                "kind": "fresh",
                "based_on": [],
                "dir": "batch-1",
                "styles": [slug_to_display_name(v.name) for v in variants],
                "user_picks": [],
            }
        ],
    }


def plan_moves(output_dir: Path, variants: list[Path]) -> list[tuple[Path, Path]]:
    batch_dir = output_dir / "batch-1"
    moves: list[tuple[Path, Path]] = [(v, batch_dir / v.name) for v in variants]
    for extra in ("index.html", "SUMMARY.txt"):
        src = output_dir / extra
        if src.exists() and src.is_file():
            moves.append((src, batch_dir / extra))
    return moves


def _print_plan(output_dir: Path, moves: list[tuple[Path, Path]],
                state: dict, quiet: bool) -> None:
    if quiet:
        return
    print(f"Detected FLAT layout at {output_dir}/")
    print()
    print("Would migrate to batch-1/:")
    width = max((len(src.name) for src, _ in moves), default=0)
    for src, dst in moves:
        rel_dst = dst.relative_to(output_dir)
        print(f"  {src.name.ljust(width)}  →  {rel_dst}")
    print()
    print("Would create state.json with:")
    print(f"  product.name: {state['product']['name']!r}")
    if state["product"]["description"]:
        print(f"  product.description: {state['product']['description']!r}")
    print(f"  batches[0].styles: {state['batches'][0]['styles']}")
    print()
    print("This is a dry run. Re-run with --commit to apply.")


def _apply_moves(output_dir: Path, moves: list[tuple[Path, Path]],
                 state: dict, quiet: bool) -> None:
    batch_dir = output_dir / "batch-1"
    if batch_dir.exists():
        # We checked is_flat_layout() above so batch-1 shouldn't exist; bail just in case.
        raise RuntimeError(
            f"refusing to overwrite existing {batch_dir} — directory is no longer flat"
        )
    batch_dir.mkdir()
    if not quiet:
        print(f"Created {batch_dir}/")
    for src, dst in moves:
        shutil.move(str(src), str(dst))
        if not quiet:
            print(f"  moved {src.name} → {dst.relative_to(output_dir)}")
    state_path = output_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    if not quiet:
        print(f"Wrote {state_path}")
        print()
        print("Migration complete. Verify with:")
        print(f"  python3 scripts/generate_index.py {batch_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("output_dir", help="Style-lab output directory to migrate")
    parser.add_argument("--name", required=True, help="Product name to record in state.json")
    parser.add_argument("--description", default="", help="Product description (optional)")
    parser.add_argument(
        "--commit", action="store_true",
        help="Actually perform the migration (default is a dry run that prints the plan)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.exists():
        print(f"error: {output_dir} does not exist", file=sys.stderr)
        return 1
    if not output_dir.is_dir():
        print(f"error: {output_dir} is not a directory", file=sys.stderr)
        return 1

    if is_already_migrated(output_dir):
        if not args.quiet:
            print(f"Already migrated, no action needed: {output_dir}")
        return 0

    variants = find_variant_dirs(output_dir)
    if not variants:
        print(
            f"error: {output_dir} has no NN-style subdirectories with index.html — "
            "nothing to migrate",
            file=sys.stderr,
        )
        return 1

    if not is_flat_layout(output_dir):
        # Defensive: should be unreachable given the checks above.
        if not args.quiet:
            print(f"Already migrated, no action needed: {output_dir}")
        return 0

    state = build_state(args.name, args.description, variants)
    moves = plan_moves(output_dir, variants)

    if not args.commit:
        _print_plan(output_dir, moves, state, args.quiet)
        return 0

    _apply_moves(output_dir, moves, state, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
