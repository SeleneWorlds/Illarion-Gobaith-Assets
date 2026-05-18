#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


OVERLAY_IDS = tuple(range(1, 29))


@dataclass(frozen=True)
class TileSize:
    width: int
    height: int


@dataclass(frozen=True)
class SceneConfig:
    path: Path
    tile_size: TileSize


@dataclass(frozen=True)
class TileConfig:
    path: Path
    tile_type: str
    texture: Path | None
    textures: tuple[Path, ...]
    sprites: str
    visual: str
    transitions: bool
    duration: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render one tile config JSON, or batch render a directory of tile configs, "
            "into isometric tile textures and visual JSON."
        )
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the tile JSON config to render, or a directory containing configs.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Do not delete pre-existing outputs before rendering.",
    )
    parser.add_argument(
        "--resample",
        default="nearest",
        choices=("nearest",),
        help="Sampling mode for the texture projection.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return raw


def require_non_empty_string(raw: dict[str, object], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: field {key!r} must be a non-empty string")
    return value.strip()


def require_positive_int(raw: dict[str, object], key: str, path: Path) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{path}: field {key!r} must be a positive integer")
    return value


def require_positive_number(raw: dict[str, object], key: str, path: Path) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{path}: field {key!r} must be a positive number")
    return float(value)


def resolve_texture_path(raw_path: str, config_path: Path) -> Path:
    texture_path = Path(raw_path)
    if not texture_path.is_absolute():
        texture_path = (config_path.parent / texture_path).resolve()
    return texture_path


def require_non_empty_string_list(raw: dict[str, object], key: str, path: Path) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path}: field {key!r} must be a non-empty array")

    strings: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(
                f"{path}: field {key!r} entry at index {index} must be a non-empty string"
            )
        strings.append(entry.strip())
    return tuple(strings)


def discover_config_files(path: Path) -> list[Path]:
    resolved = path.resolve()
    if resolved.is_file():
        if resolved.name == "scene.json":
            raise ValueError(f"expected a tile config JSON, not a scene config: {resolved}")
        return [resolved]
    if not resolved.is_dir():
        raise FileNotFoundError(f"config path does not exist: {resolved}")

    config_files = sorted(
        candidate.resolve()
        for candidate in resolved.rglob("*.json")
        if candidate.is_file() and candidate.name != "scene.json"
    )
    if not config_files:
        raise FileNotFoundError(f"no tile config JSON files found under: {resolved}")
    return config_files


def find_scene_config(start_dir: Path, stop_dir: Path) -> SceneConfig:
    current = start_dir.resolve()
    stop_dir = stop_dir.resolve()
    while True:
        candidate = current / "scene.json"
        if candidate.is_file():
            raw = load_json_object(candidate, "scene config")
            tile_size_raw = raw.get("tileSize")
            if not isinstance(tile_size_raw, dict):
                raise ValueError(f"{candidate}: field 'tileSize' must be an object")
            return SceneConfig(
                path=candidate,
                tile_size=TileSize(
                    width=require_positive_int(tile_size_raw, "width", candidate),
                    height=require_positive_int(tile_size_raw, "height", candidate),
                ),
            )

        if current == stop_dir or current.parent == current:
            break
        current = current.parent

    raise FileNotFoundError(
        f"missing scene.json for {start_dir}; expected a file in {start_dir} or one of its ancestors up to {stop_dir}"
    )


def ensure_repo_relative_output(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the repository: {resolved}") from exc
    return resolved


def load_tile_config(path: Path, root: Path) -> TileConfig:
    raw = load_json_object(path, "tile config")
    tile_type = raw.get("type")
    if not isinstance(tile_type, str):
        raise ValueError(f"{path}: field 'type' must be 'simple' or 'animated'")
    normalized_type = tile_type.strip().lower()
    if normalized_type not in {"simple", "animated"}:
        raise ValueError(f"{path}: field 'type' must be 'simple' or 'animated'")

    transitions = raw.get("transitions", False)
    if not isinstance(transitions, bool):
        raise ValueError(f"{path}: field 'transitions' must be a boolean when present")

    if normalized_type == "simple":
        texture = resolve_texture_path(require_non_empty_string(raw, "texture", path), path)
        textures: tuple[Path, ...] = ()
        duration = None
    else:
        texture = None
        textures = tuple(
            resolve_texture_path(texture_value, path)
            for texture_value in require_non_empty_string_list(raw, "textures", path)
        )
        duration = (
            require_positive_number(raw, "duration", path)
            if "duration" in raw
            else None
        )
        if transitions:
            raise ValueError(f"{path}: animated tiles do not support transitions")

    return TileConfig(
        path=path,
        tile_type=normalized_type,
        texture=texture,
        textures=textures,
        sprites=require_non_empty_string(raw, "sprites", path),
        visual=require_non_empty_string(raw, "visual", path),
        transitions=transitions,
        duration=duration,
    )


def describe_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def remove_file_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()


def remove_matching_files(paths: tuple[Path, ...]) -> None:
    for path in paths:
        remove_file_if_exists(path)


def remove_matching_glob(pattern: str, directory: Path) -> None:
    for path in directory.glob(pattern):
        remove_file_if_exists(path)


def extract_tile_id(tile_config: TileConfig) -> int:
    candidates = (
        Path(tile_config.visual).name,
        Path(tile_config.sprites).name,
    )
    for candidate in candidates:
        match = re.search(r"(\d+)$", candidate)
        if match is not None:
            return int(match.group(1))
    raise ValueError(
        f"{tile_config.path}: could not derive a numeric tile id from 'visual' or 'sprites'"
    )


def offset_y_for_tile(tile_size: TileSize) -> int:
    return -(tile_size.height // 2)


def load_mask_alpha(path: Path, expected_size: tuple[int, int]) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"mask does not exist: {path}")
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    if rgba.size != expected_size:
        raise ValueError(
            f"mask size mismatch for {path}: expected {expected_size[0]}x{expected_size[1]}, got {rgba.size[0]}x{rgba.size[1]}"
        )
    luminance = rgba.convert("L")
    alpha = rgba.getchannel("A")
    return ImageChops.multiply(luminance, alpha)


def render_base_tile(
    source: Image.Image,
    tile_size: TileSize,
    base_mask_alpha: Image.Image,
) -> Image.Image:
    src_w, src_h = source.size
    if src_w != src_h:
        raise ValueError(
            f"source texture must be square; got {src_w}x{src_h}"
        )

    output = Image.new("RGBA", (tile_size.width, tile_size.height), (0, 0, 0, 0))
    source_pixels = source.load()
    output_pixels = output.load()
    mask_pixels = base_mask_alpha.load()

    half_width = tile_size.width / 2.0
    half_height = tile_size.height / 2.0

    for y in range(tile_size.height):
        for x in range(tile_size.width):
            mask_alpha = mask_pixels[x, y]
            if mask_alpha <= 0:
                continue

            normalized_x = ((x + 0.5) - half_width) / half_width
            normalized_y = (y + 0.5) / half_height
            source_u = (normalized_x + normalized_y) / 2.0
            source_v = (normalized_y - normalized_x) / 2.0

            source_u = min(max(source_u, 0.0), 1.0)
            source_v = min(max(source_v, 0.0), 1.0)
            sample_x = min(src_w - 1, max(0, int(round(source_u * (src_w - 1)))))
            sample_y = min(src_h - 1, max(0, int(round(source_v * (src_h - 1)))))

            red, green, blue, alpha = source_pixels[sample_x, sample_y]
            output_alpha = (alpha * mask_alpha) // 255
            output_pixels[x, y] = (red, green, blue, output_alpha)

    return output


def apply_overlay_mask(base_tile: Image.Image, overlay_mask_alpha: Image.Image) -> Image.Image:
    masked = base_tile.copy()
    combined_alpha = ImageChops.multiply(masked.getchannel("A"), overlay_mask_alpha)
    masked.putalpha(combined_alpha)
    return masked


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def existing_visual_metadata(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    raw = load_json_object(path, "existing visual")
    metadata = raw.get("metadata")
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: existing visual field 'metadata' must be an object")
    return metadata


def with_optional_metadata(
    payload: dict[str, object],
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    if metadata:
        payload["metadata"] = metadata
    return payload


def base_visual_json(
    texture_path: Path,
    root: Path,
    tile_size: TileSize,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    return with_optional_metadata({
        "type": "simple",
        "offsetX": 0,
        "offsetY": offset_y_for_tile(tile_size),
        "texture": str(texture_path.resolve().relative_to(root)).replace("\\", "/"),
    }, metadata)


def animated_visual_json(
    texture_paths: tuple[Path, ...],
    root: Path,
    tile_size: TileSize,
    duration: float | None,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "animated",
        "offsetX": 0,
        "offsetY": offset_y_for_tile(tile_size),
        "textures": [
            str(texture_path.resolve().relative_to(root)).replace("\\", "/")
            for texture_path in texture_paths
        ],
    }
    if duration is not None:
        payload["duration"] = duration
    return with_optional_metadata(payload, metadata)


def transition_visual_json(
    texture_path: Path,
    root: Path,
    tile_size: TileSize,
    tile_id: int,
    overlay_id: int,
) -> dict[str, object]:
    return {
        "type": "simple",
        "offsetX": 0,
        "offsetY": offset_y_for_tile(tile_size),
        "texture": str(texture_path.resolve().relative_to(root)).replace("\\", "/"),
        "metadata": {
            "tileId": tile_id,
            "overlayId": overlay_id,
        },
    }


def animated_texture_output_files(tile_config: TileConfig, root: Path) -> tuple[Path, ...]:
    return tuple(
        ensure_repo_relative_output(
            root / "client" / "textures" / f"{tile_config.sprites}-{index}.png",
            root,
            "animated texture output path",
        )
        for index in range(len(tile_config.textures))
    )


def render_config(args: argparse.Namespace, root: Path, config_path: Path) -> int:
    try:
        tile_config = load_tile_config(config_path, root)
        scene_config = find_scene_config(tile_config.path.parent, root)
        rendered_tile: Image.Image | None = None

        visual_output_file = ensure_repo_relative_output(
            root / "client" / "data" / "illarion" / "visuals" / f"{tile_config.visual}.json",
            root,
            "visual output path",
        )
        visual_metadata = existing_visual_metadata(visual_output_file)

        if tile_config.tile_type == "simple":
            assert tile_config.texture is not None
            if not tile_config.texture.is_file():
                raise FileNotFoundError(f"texture does not exist: {tile_config.texture}")
            texture_output_files = (
                ensure_repo_relative_output(
                    root / "client" / "textures" / f"{tile_config.sprites}.png",
                    root,
                    "texture output path",
                ),
            )
        else:
            missing_textures = [texture for texture in tile_config.textures if not texture.is_file()]
            if missing_textures:
                raise FileNotFoundError(f"texture does not exist: {missing_textures[0]}")
            texture_output_files = animated_texture_output_files(tile_config, root)

        if not args.keep_output:
            remove_matching_files(texture_output_files)
            if tile_config.tile_type == "animated":
                remove_matching_glob(
                    f"{Path(tile_config.sprites).name}-*.png",
                    (root / "client" / "textures" / Path(tile_config.sprites).parent).resolve(),
                )
            remove_file_if_exists(visual_output_file)

        base_mask_alpha = load_mask_alpha(
            root / "masks" / "mask.png",
            (scene_config.tile_size.width, scene_config.tile_size.height),
        )

        if tile_config.tile_type == "simple":
            texture_output_file = texture_output_files[0]
            assert tile_config.texture is not None
            with Image.open(tile_config.texture) as image:
                source = image.convert("RGBA")
            rendered_tile = render_base_tile(source, scene_config.tile_size, base_mask_alpha)

            texture_output_file.parent.mkdir(parents=True, exist_ok=True)
            rendered_tile.save(texture_output_file)
            write_json(
                visual_output_file,
                base_visual_json(
                    texture_output_file,
                    root,
                    scene_config.tile_size,
                    visual_metadata,
                ),
            )
        else:
            rendered_tiles: list[Path] = []
            for texture_path, texture_output_file in zip(tile_config.textures, texture_output_files):
                with Image.open(texture_path) as image:
                    source = image.convert("RGBA")
                rendered_tile = render_base_tile(source, scene_config.tile_size, base_mask_alpha)

                texture_output_file.parent.mkdir(parents=True, exist_ok=True)
                rendered_tile.save(texture_output_file)
                rendered_tiles.append(texture_output_file)

            write_json(
                visual_output_file,
                animated_visual_json(
                    tuple(rendered_tiles),
                    root,
                    scene_config.tile_size,
                    tile_config.duration,
                    visual_metadata,
                ),
            )

        tile_id = extract_tile_id(tile_config) if tile_config.transitions else None
        if tile_config.transitions:
            assert tile_id is not None
            assert rendered_tile is not None
            for overlay_id in OVERLAY_IDS:
                overlay_texture_file = ensure_repo_relative_output(
                    root / "client" / "textures" / f"{tile_config.sprites}_ovl-{overlay_id}.png",
                    root,
                    "transition texture output path",
                )
                overlay_visual_file = ensure_repo_relative_output(
                    root
                    / "client"
                    / "data"
                    / "illarion"
                    / "visuals"
                    / "transitions"
                    / f"transition_{tile_id}_{overlay_id}.json",
                    root,
                    "transition visual output path",
                )
                if not args.keep_output:
                    remove_file_if_exists(overlay_texture_file)
                    remove_file_if_exists(overlay_visual_file)

                overlay_mask_alpha = load_mask_alpha(
                    root / "masks" / f"mask_ovl-{overlay_id}.png",
                    (scene_config.tile_size.width, scene_config.tile_size.height),
                )
                overlay_texture = apply_overlay_mask(rendered_tile, overlay_mask_alpha)
                overlay_texture_file.parent.mkdir(parents=True, exist_ok=True)
                overlay_texture.save(overlay_texture_file)
                write_json(
                    overlay_visual_file,
                    transition_visual_json(
                        overlay_texture_file,
                        root,
                        scene_config.tile_size,
                        tile_id,
                        overlay_id,
                    ),
                )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


def main() -> int:
    args = parse_args()
    root = repo_root()

    try:
        config_paths = discover_config_files(args.config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if len(config_paths) > 1:
        print(f"Batch rendering {len(config_paths)} configs from {args.config_path.resolve()}", flush=True)

    exit_code = 0
    for config_path in config_paths:
        if len(config_paths) > 1:
            print(f"[{describe_path(config_path, root)}]", flush=True)
        result = render_config(args, root, config_path)
        if result != 0:
            exit_code = result

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
