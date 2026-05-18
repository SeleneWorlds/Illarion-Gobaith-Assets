#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from html import escape
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    new_root = script_dir.parent
    old_root = new_root.parent / "illarion-gobaith-assets-proprietary"

    parser = argparse.ArgumentParser(
        description=(
            "Generate an HTML comparison page for visuals in "
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
        default=new_root / "visual-comparison.html",
        help="Output HTML path.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def iter_generated_visual_jsons(new_root: Path) -> list[Path]:
    visual_root = new_root / "client" / "data" / "illarion" / "visuals"
    return sorted(visual_root.rglob("*.json"))


def choose_first(existing_paths: list[Path]) -> Path | None:
    for path in existing_paths:
        if path.exists() and path.is_file():
            return path
    return None


def choose_old_animation_textures(data: dict[str, Any]) -> list[str]:
    animations = data.get("animations")
    if not isinstance(animations, dict):
        return []

    preferred_keys = [
        "stationary/south",
        "stationary/west",
        "stationary/east",
        "stationary/north",
        "walk/south",
        "walk/west",
        "walk/east",
        "walk/north",
    ]

    ordered_keys = preferred_keys + sorted(
        key for key in animations.keys() if key not in preferred_keys
    )
    for key in ordered_keys:
        entry = animations.get(key)
        if not isinstance(entry, dict):
            continue
        textures = entry.get("textures")
        if isinstance(textures, list):
            pngs = [item for item in textures if isinstance(item, str) and item.endswith(".png")]
            if pngs:
                return pngs
    return []


def resolve_visual_definition_preview(repo_root: Path, data: dict[str, Any]) -> Path | None:
    texture = data.get("texture")
    if isinstance(texture, str):
        preview = repo_root / texture
        return preview if preview.exists() else None

    textures = data.get("textures")
    if isinstance(textures, list):
        pngs = [item for item in textures if isinstance(item, str) and item.endswith(".png")]
        if pngs:
            preview = repo_root / pngs[0]
            return preview if preview.exists() else None

    animation_pngs = choose_old_animation_textures(data)
    if animation_pngs:
        preview = repo_root / animation_pngs[0]
        return preview if preview.exists() else None

    return None


def resolve_old_preview(old_root: Path, visual_id: str) -> tuple[Path | None, Path | None]:
    visual_json = old_root / "client" / "data" / "illarion" / "visuals" / f"{visual_id}.json"
    if not visual_json.exists():
        return visual_json, None

    data = load_json(visual_json)
    return visual_json, resolve_visual_definition_preview(old_root, data)


def first_metadata_texture(metadata: dict[str, Any]) -> str | None:
    entries = metadata.get("entries")
    if isinstance(entries, dict):
        for key in sorted(entries.keys()):
            entry = entries[key]
            if not isinstance(entry, dict):
                continue
            textures = entry.get("textures")
            if isinstance(textures, list):
                for texture in textures:
                    if isinstance(texture, str) and texture.endswith(".png"):
                        return texture

    actions = metadata.get("actions")
    if isinstance(actions, dict):
        for action_name in sorted(actions.keys()):
            directions = actions[action_name]
            if not isinstance(directions, dict):
                continue
            for direction in ["south", "west", "east", "north"]:
                entry = directions.get(direction)
                if not isinstance(entry, dict):
                    continue
                frames = entry.get("frames")
                if isinstance(frames, int) and frames > 0:
                    return f"{action_name}/{direction}/0001.png"
    return None


def resolve_new_preview(new_root: Path, visual_data: dict[str, Any]) -> Path | None:
    sprites = visual_data["sprites"]
    texture_root = new_root / "client" / "textures"

    direct_png = texture_root / f"{sprites}.png"
    if direct_png.exists():
        return direct_png

    sprite_dir = texture_root / sprites
    metadata_path = sprite_dir / "render_metadata.json"
    if metadata_path.exists():
        metadata = load_json(metadata_path)
        first_texture = first_metadata_texture(metadata)
        if first_texture is not None:
            candidate = sprite_dir / first_texture
            if candidate.exists():
                return candidate

    sprite_parent = (texture_root / sprites).parent
    sprite_stem = Path(sprites).name
    numbered = sorted(sprite_parent.glob(f"{sprite_stem}-*.png"))
    preview = choose_first(numbered)
    if preview is not None:
        return preview

    return None


def rel_href(target: Path | None, output_path: Path) -> str | None:
    if target is None:
        return None
    return Path(
        os.path.relpath(target.resolve(), output_path.resolve().parent)
    ).as_posix()


def safe_relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def visual_id_from_generated_path(path: Path, repo_root: Path) -> str:
    visual_root = repo_root / "client" / "data" / "illarion" / "visuals"
    return path.resolve().relative_to(visual_root.resolve()).with_suffix("").as_posix()


def image_cell(image_href: str | None, file_label: str | None) -> str:
    if image_href is None:
        return (
            '<div class="image missing">Missing</div>'
            '<div class="filename missing-text">No sprite resolved</div>'
        )
    return (
        f'<img class="image" loading="lazy" src="{escape(image_href)}" '
        f'alt="{escape(file_label or "sprite preview")}">'
        f'<div class="filename">{escape(file_label or image_href)}</div>'
    )


def build_html(rows: list[dict[str, str | None]]) -> str:
    cards = []
    for row in rows:
        search_text = " ".join(
            part
            for part in [
                row["source_json"],
                row["visual_id"],
                row["old_visual_json"],
                row["old_file"],
                row["new_file"],
            ]
            if part
        ).lower()
        old_missing = "true" if row["old_image_href"] is None else "false"
        new_missing = "true" if row["new_image_href"] is None else "false"
        duplicate_new = "true" if row.get("duplicate_new") == "true" else "false"
        cards.append(
            (
                f'<article class="card" data-search="{escape(search_text)}" '
                f'data-old-missing="{old_missing}" data-new-missing="{new_missing}" '
                f'data-duplicate-new="{duplicate_new}">'
                '<div class="meta">'
                f'<div><span class="label">Visual JSON</span>{escape(row["source_json"] or "")}</div>'
                f'<div><span class="label">Visual ID</span>{escape(row["visual_id"] or "")}</div>'
                f'<div><span class="label">Legacy JSON</span>{escape(row["old_visual_json"] or "Missing")}</div>'
                f'<div><span class="label">New Visual Uses</span>{escape(row["duplicate_new_count"] or "0")}</div>'
                "</div>"
                '<div class="comparison">'
                '<section class="pane">'
                '<h2>Old (-proprietary)</h2>'
                f'{image_cell(row["old_image_href"], row["old_file"])}'
                "</section>"
                '<section class="pane">'
                '<h2>New</h2>'
                f'{image_cell(row["new_image_href"], row["new_file"])}'
                "</section>"
                "</div>"
                "</article>"
            )
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Illarion Visual Comparison</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f1e8;
      --panel: rgba(255, 250, 240, 0.92);
      --ink: #1f1b16;
      --muted: #685f52;
      --line: #d3c4ae;
      --accent: #8b5e34;
      --missing: #efe1d8;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Iosevka Etoile", "IBM Plex Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(191, 153, 105, 0.25), transparent 30%),
        linear-gradient(180deg, #f9f5ed, var(--bg));
    }}
    header {{
      padding: 32px 24px 20px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 248, 235, 0.82);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(1.8rem, 2.4vw, 2.8rem);
    }}
    p {{
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(260px, 1.6fr) auto auto auto;
      gap: 12px;
      margin-top: 18px;
      align-items: center;
    }}
    .search {{
      width: 100%;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 252, 246, 0.95);
      padding: 12px 16px;
      font: inherit;
      color: var(--ink);
    }}
    .toggle {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 252, 246, 0.9);
      color: var(--ink);
      font-size: 0.92rem;
      white-space: nowrap;
    }}
    .summary {{
      justify-self: end;
      color: var(--muted);
      font-size: 0.92rem;
      white-space: nowrap;
    }}
    main {{
      display: grid;
      gap: 18px;
      padding: 24px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: 0 12px 40px rgba(61, 40, 16, 0.08);
      overflow: hidden;
    }}
    .meta {{
      display: grid;
      gap: 8px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(240, 229, 211, 0.75);
      font-size: 0.95rem;
      word-break: break-word;
    }}
    .label {{
      display: block;
      font-size: 0.74rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 2px;
    }}
    .comparison {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .pane {{
      padding: 16px 18px 20px;
    }}
    .pane + .pane {{
      border-left: 1px solid var(--line);
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }}
    .image {{
      display: grid;
      place-items: center;
      width: 100%;
      min-height: 160px;
      max-height: 360px;
      object-fit: contain;
      image-rendering: pixelated;
      background:
        linear-gradient(45deg, #eadfcf 25%, transparent 25%, transparent 75%, #eadfcf 75%),
        linear-gradient(45deg, #eadfcf 25%, transparent 25%, transparent 75%, #eadfcf 75%);
      background-position: 0 0, 10px 10px;
      background-size: 20px 20px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
    }}
    .image.missing {{
      background: var(--missing);
      color: var(--muted);
      font-weight: 600;
    }}
    .filename {{
      margin-top: 10px;
      font-family: "Iosevka Etoile", "IBM Plex Mono", monospace;
      font-size: 0.85rem;
      color: var(--muted);
      word-break: break-all;
    }}
    .missing-text {{
      color: #8a4f3c;
    }}
    .hidden {{
      display: none;
    }}
    @media (max-width: 900px) {{
      .controls {{
        grid-template-columns: 1fr;
      }}
      .summary {{
        justify-self: start;
      }}
      .comparison {{
        grid-template-columns: 1fr;
      }}
      .pane + .pane {{
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      header, main {{
        padding-left: 16px;
        padding-right: 16px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Illarion Visual Comparison</h1>
    <p>Side-by-side preview of legacy sprites from <code>illarion-gobaith-assets-proprietary</code> and current sprites from <code>illarion-gobaith-assets</code>. Entries are generated from every new visual JSON under <code>client/data/illarion/visuals</code>.</p>
    <div class="controls">
      <input id="search" class="search" type="search" placeholder="Search JSON paths, visual ids, or sprite file names">
      <label class="toggle"><input id="missing-new" type="checkbox"> Missing new</label>
      <label class="toggle"><input id="duplicate-new" type="checkbox"> Duplicate new sprite</label>
      <div id="summary" class="summary"></div>
    </div>
  </header>
  <main>
    {''.join(cards)}
  </main>
  <script>
    const searchInput = document.getElementById("search");
    const missingNew = document.getElementById("missing-new");
    const duplicateNew = document.getElementById("duplicate-new");
    const summary = document.getElementById("summary");
    const cards = Array.from(document.querySelectorAll(".card"));

    function applyFilters() {{
      const query = searchInput.value.trim().toLowerCase();
      let visibleCount = 0;

      for (const card of cards) {{
        const haystack = card.dataset.search || "";
        const newMissing = card.dataset.newMissing === "true";
        const duplicate = card.dataset.duplicateNew === "true";
        const matchesSearch = query === "" || haystack.includes(query);
        const matchesNew = !missingNew.checked || newMissing;
        const matchesDuplicate = !duplicateNew.checked || duplicate;
        const visible = matchesSearch && matchesNew && matchesDuplicate;

        card.classList.toggle("hidden", !visible);
        if (visible) {{
          visibleCount += 1;
        }}
      }}

      summary.textContent = `${{visibleCount}} / ${{cards.length}} shown`;
    }}

    for (const control of [searchInput, missingNew, duplicateNew]) {{
      control.addEventListener("input", applyFilters);
      control.addEventListener("change", applyFilters);
    }}

    applyFilters();
  </script>
</body>
</html>
"""


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

    generated_visual_usage: dict[str, int] = {}
    generated_visual_root = new_root / "client" / "data" / "illarion" / "visuals"
    visual_jsons = iter_generated_visual_jsons(new_root)
    for path in visual_jsons:
        try:
            data = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        preview = resolve_visual_definition_preview(new_root, data)
        if preview is None:
            continue
        preview_key = safe_relpath(preview, new_root)
        generated_visual_usage[preview_key] = generated_visual_usage.get(preview_key, 0) + 1

    rows: list[dict[str, str | None]] = []

    for path in visual_jsons:
        data = load_json(path)
        visual_id = visual_id_from_generated_path(path, new_root)
        new_preview = resolve_visual_definition_preview(new_root, data)
        old_visual_json, old_preview = resolve_old_preview(old_root, visual_id)

        rows.append(
            {
                "source_json": safe_relpath(path, new_root),
                "visual_id": visual_id,
                "old_visual_json": (
                    safe_relpath(old_visual_json, old_root)
                    if old_visual_json is not None and old_visual_json.exists()
                    else None
                ),
                "old_image_href": rel_href(old_preview, output_path),
                "new_image_href": rel_href(new_preview, output_path),
                "old_file": (
                    safe_relpath(old_preview, old_root) if old_preview is not None else None
                ),
                "new_file": (
                    safe_relpath(new_preview, new_root) if new_preview is not None else None
                ),
            }
        )

    for row in rows:
        new_file = row["new_file"]
        duplicate_count = generated_visual_usage.get(new_file, 0) if new_file is not None else 0
        row["duplicate_new_count"] = str(duplicate_count)
        row["duplicate_new"] = (
            "true" if duplicate_count > 1 else "false"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} visual comparisons to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
