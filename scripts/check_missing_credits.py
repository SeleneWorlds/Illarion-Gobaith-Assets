#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fnmatch
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check that every .blend file in models and every .png file in "
            "client/textures has a matching entry in CREDITS.csv."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root. Defaults to the parent of this script directory.",
    )
    parser.add_argument(
        "--credits",
        type=Path,
        default=None,
        help="Path to the credits CSV. Defaults to <root>/CREDITS.csv.",
    )
    return parser.parse_args()


def resolve_credits_path(root: Path, credits: Path | None) -> Path:
    if credits is None:
        return root / "CREDITS.csv"
    if credits.is_absolute():
        return credits
    return (root / credits).resolve()


def load_credit_patterns(credits_path: Path, root: Path) -> list[str]:
    try:
        with credits_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "path" not in reader.fieldnames:
                raise ValueError(f"{credits_path} is missing a 'path' header")

            patterns: list[str] = []
            for row in reader:
                raw_path = (row.get("path") or "").strip()
                if not raw_path:
                    continue

                candidate = Path(raw_path)
                if candidate.is_absolute():
                    try:
                        normalized = candidate.resolve().relative_to(root.resolve())
                    except ValueError:
                        normalized = candidate
                    patterns.append(normalized.as_posix())
                else:
                    patterns.append(candidate.as_posix())
            return patterns
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing credits file: {credits_path}") from exc


def collect_assets(root: Path) -> list[str]:
    targets = [
        (root / "models", "*.blend"),
        (root / "client" / "textures", "*.png"),
    ]

    assets: list[str] = []
    for base_dir, pattern in targets:
        if not base_dir.exists():
            continue
        for path in sorted(base_dir.rglob(pattern)):
            if path.suffix.lower() == ".png" and path.stem.endswith("_proprietary"):
                continue
            assets.append(path.relative_to(root).as_posix())
    return assets


def find_missing_assets(assets: list[str], patterns: list[str]) -> list[str]:
    missing: list[str] = []
    for asset in assets:
        if not any(fnmatch.fnmatchcase(asset, pattern) for pattern in patterns):
            missing.append(asset)
    return missing


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    credits_path = resolve_credits_path(root, args.credits)

    try:
        patterns = load_credit_patterns(credits_path, root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    assets = collect_assets(root)
    missing = find_missing_assets(assets, patterns)

    print(f"Checked {len(assets)} assets against {len(patterns)} credit entries.")
    if not missing:
        print("All required assets have matching credits.")
        return 0

    print(f"Missing credits for {len(missing)} assets:")
    for asset in missing:
        print(asset)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
