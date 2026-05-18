#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generate_visual_comparison_html import (
    iter_generated_visual_jsons,
    load_json,
    resolve_old_preview,
    resolve_visual_definition_preview,
    safe_relpath,
    visual_id_from_generated_path,
)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    new_root = script_dir.parent
    old_root = new_root.parent / "illarion-gobaith-assets-proprietary"

    parser = argparse.ArgumentParser(
        description=(
            "Generate a compact Markdown asset report for visuals in "
            "illarion-gobaith-assets against illarion-gobaith-assets-proprietary."
        )
    )
    parser.add_argument(
        "--new-root",
        type=Path,
        default=new_root,
        help="Path to the illarion-gobaith-assets repository.",
    )
    parser.add_argument(
        "--old-root",
        type=Path,
        default=old_root,
        help="Path to the illarion-gobaith-assets-proprietary repository.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=new_root / "asset-report.md",
        help="Output Markdown path.",
    )
    return parser.parse_args()


def build_markdown(rows: list[dict[str, str | int | None]]) -> str:
    duplicate_groups: dict[str, list[dict[str, str | int | None]]] = {}
    missing_new_rows: list[dict[str, str | int | None]] = []

    for row in rows:
        new_file = row["new_file"]
        if new_file is None:
            missing_new_rows.append(row)
            continue

        duplicate_count = row["duplicate_new_count"]
        if isinstance(duplicate_count, int) and duplicate_count > 1:
            duplicate_groups.setdefault(str(new_file), []).append(row)

    duplicate_items = sorted(
        duplicate_groups.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    missing_new_rows.sort(key=lambda row: str(row["visual_id"]))

    lines = [
        "# Illarion Asset Report",
        "",
        "## Summary",
        "",
        f"- Total visuals: {len(rows)}",
        (
            f"- Duplicate uses: {sum(len(group) for _, group in duplicate_items)} visuals "
            f"across {len(duplicate_items)} resolved sprite files"
        ),
        f"- Missing new: {len(missing_new_rows)} visuals",
        "",
        f"## Duplicate Uses ({len(duplicate_items)} sprite files)",
        "",
    ]

    if not duplicate_items:
        lines.append("None.")
    else:
        for new_file, group in duplicate_items:
            visual_ids = ", ".join(f"`{row['visual_id']}`" for row in sorted(group, key=lambda row: str(row["visual_id"])))
            lines.append(f"- `{new_file}` used by {len(group)} visuals: {visual_ids}")

    lines.extend(
        [
            "",
            f"## Missing New ({len(missing_new_rows)} visuals)",
            "",
        ]
    )

    if not missing_new_rows:
        lines.append("None.")
    else:
        for row in missing_new_rows:
            legacy_json = row["old_visual_json"] or "Missing"
            legacy_preview = row["old_file"] or "Missing"
            lines.append(
                f"- `{row['visual_id']}` from `{row['source_json']}` "
                f"(legacy JSON: `{legacy_json}`, legacy preview: `{legacy_preview}`)"
            )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    new_root = args.new_root.resolve()
    old_root = args.old_root.resolve()
    output_path = args.output if args.output.is_absolute() else (new_root / args.output).resolve()

    if not new_root.exists():
        print(f"error: new root does not exist: {new_root}", file=sys.stderr)
        return 2
    if not old_root.exists():
        print(f"error: old root does not exist: {old_root}", file=sys.stderr)
        return 2

    visual_jsons = iter_generated_visual_jsons(new_root)
    generated_visual_usage: dict[str, int] = {}
    rows: list[dict[str, str | int | None]] = []

    for path in visual_jsons:
        data = load_json(path)
        visual_id = visual_id_from_generated_path(path, new_root)
        new_preview = resolve_visual_definition_preview(new_root, data)
        old_visual_json, old_preview = resolve_old_preview(old_root, visual_id)

        new_file = safe_relpath(new_preview, new_root) if new_preview is not None else None
        if new_file is not None:
            generated_visual_usage[new_file] = generated_visual_usage.get(new_file, 0) + 1

        rows.append(
            {
                "source_json": safe_relpath(path, new_root),
                "visual_id": visual_id,
                "old_visual_json": (
                    safe_relpath(old_visual_json, old_root)
                    if old_visual_json is not None and old_visual_json.exists()
                    else None
                ),
                "old_file": (
                    safe_relpath(old_preview, old_root) if old_preview is not None else None
                ),
                "new_file": new_file,
            }
        )

    for row in rows:
        new_file = row["new_file"]
        row["duplicate_new_count"] = generated_visual_usage.get(str(new_file), 0) if new_file else 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} visual entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
