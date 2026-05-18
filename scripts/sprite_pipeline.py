#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


DEFAULT_DIRECTIONS = ("north", "east", "south", "west")


@dataclass(frozen=True)
class TileSize:
    width: int
    height: int


@dataclass(frozen=True)
class LightingConfig:
    azimuth: float
    elevation: float
    strength: float
    ambient_strength: float


@dataclass(frozen=True)
class SceneConfig:
    path: Path
    tile_size: TileSize
    lighting: LightingConfig


@dataclass(frozen=True)
class ModelConfig:
    path: Path
    blend_file: Path
    sprites: str
    visual: str
    scale: float
    materials: dict[str, dict[str, Path]] | None
    fps: int
    alpha_clip: float | None
    alpha_mask: Path | None
    offset_x: int | None
    offset_y: int | None
    surface_offset_y: int | None
    animations: tuple[str, ...] | None
    directions: tuple[str, ...] | None
    include: tuple[str, ...] | None
    exclude: tuple[str, ...] | None


@dataclass(frozen=True)
class VariantConfig:
    index: int
    model: ModelConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render one model config JSON, or batch render a directory of configs, "
            "into directional sprite frames using the nearest ancestor scene.json."
        )
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the model JSON config to render, or a directory containing configs.",
    )
    parser.add_argument(
        "--blender",
        default="blender",
        help="Blender executable to invoke.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Do not clear the target texture directory before rendering.",
    )
    parser.add_argument(
        "--engine",
        default="AUTO",
        choices=(
            "AUTO",
            "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT",
            "BLENDER_WORKBENCH",
            "CYCLES",
        ),
        help="Requested Blender render engine.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize_blend_path(path: Path) -> Path:
    path_str = str(path)
    if path_str.lower().endswith(".blend"):
        return path
    if path_str.endswith("."):
        return Path(f"{path_str}blend")
    return Path(f"{path_str}.blend")


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


def require_string(raw: dict[str, object], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: field {key!r} must be a non-empty string")
    return value.strip()


def require_positive_number(raw: dict[str, object], key: str, path: Path) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or float(value) <= 0.0:
        raise ValueError(f"{path}: field {key!r} must be a positive number")
    return float(value)


def require_number(raw: dict[str, object], key: str, path: Path) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{path}: field {key!r} must be a number")
    return float(value)


def optional_unit_interval_number(
    raw: dict[str, object],
    key: str,
    path: Path,
) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"{path}: field {key!r} must be a number when present")
    normalized = float(value)
    if normalized < 0.0 or normalized > 1.0:
        raise ValueError(f"{path}: field {key!r} must be between 0.0 and 1.0")
    return normalized


def optional_path(raw: dict[str, object], key: str, path: Path) -> Path | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: field {key!r} must be a non-empty string when present")
    candidate = Path(value.strip())
    if not candidate.is_absolute():
        candidate = (path.parent / candidate).resolve()
    return candidate


def optional_material_overrides(
    raw: dict[str, object],
    path: Path,
) -> dict[str, dict[str, Path]] | None:
    value = raw.get("materials")
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{path}: field 'materials' must be a non-empty object when present")

    materials: dict[str, dict[str, Path]] = {}
    for material_name, node_value in value.items():
        if not isinstance(material_name, str) or not material_name.strip():
            raise ValueError(f"{path}: field 'materials' must only contain non-empty material names")
        if not isinstance(node_value, dict) or not node_value:
            raise ValueError(
                f"{path}: material override {material_name!r} must be a non-empty object"
            )

        nodes: dict[str, Path] = {}
        for node_name, texture_value in node_value.items():
            if not isinstance(node_name, str) or not node_name.strip():
                raise ValueError(
                    f"{path}: material override {material_name!r} must only contain non-empty node names"
                )
            if not isinstance(texture_value, str) or not texture_value.strip():
                raise ValueError(
                    f"{path}: material override {material_name!r}/{node_name!r} must be a non-empty string"
                )
            texture_path = Path(texture_value.strip())
            if not texture_path.is_absolute():
                texture_path = (path.parent / texture_path).resolve()
            nodes[node_name.strip()] = texture_path
        materials[material_name.strip()] = nodes

    return materials


def optional_alpha_mask_path(
    raw: dict[str, object],
    path: Path,
    root: Path,
) -> Path | None:
    value = raw.get("alphaMask")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: field 'alphaMask' must be a non-empty string when present")
    candidate = Path(value.strip())
    if not candidate.is_absolute():
        candidate = (root / "masks" / candidate).resolve()
    return candidate


def require_positive_int(raw: dict[str, object], key: str, path: Path) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{path}: field {key!r} must be a positive integer")
    return value


def optional_int(raw: dict[str, object], key: str, path: Path) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{path}: field {key!r} must be an integer when present")
    return value


def optional_string_list(
    raw: dict[str, object],
    key: str,
    path: Path,
) -> tuple[str, ...] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path}: field {key!r} must be a non-empty array when present")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: field {key!r} must only contain non-empty strings")
        items.append(item.strip())
    return tuple(items)


def normalize_direction(direction: object, path: Path, field_name: str) -> str:
    if not isinstance(direction, str) or not direction.strip():
        raise ValueError(f"{path}: field {field_name!r} must be a non-empty string when present")
    normalized = direction.strip().lower()
    if normalized not in DEFAULT_DIRECTIONS:
        raise ValueError(
            f"{path}: unknown direction {normalized!r}; expected one of {DEFAULT_DIRECTIONS}"
        )
    return normalized


def optional_direction_list(raw: dict[str, object], path: Path) -> tuple[str, ...] | None:
    direction = raw.get("direction")
    directions = raw.get("directions")
    if direction is not None and directions is not None:
        raise ValueError(f"{path}: only one of 'direction' or 'directions' may be present")

    if direction is not None:
        return (normalize_direction(direction, path, "direction"),)

    if directions is None:
        return None
    if not isinstance(directions, list) or not directions:
        raise ValueError(f"{path}: field 'directions' must be a non-empty array when present")

    return tuple(normalize_direction(item, path, "directions") for item in directions)


def resolve_model_path(raw: dict[str, object], path: Path) -> Path:
    value = raw.get("model")
    if value is None:
        return path.with_suffix(".blend")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: field 'model' must be a non-empty string when present")
    model_path = normalize_blend_path(Path(value.strip()))
    if not model_path.is_absolute():
        model_path = (path.parent / model_path).resolve()
    return model_path


def load_model_config(path: Path, root: Path) -> ModelConfig:
    raw = load_json_object(path, "sibling model config")
    return load_model_config_from_raw(path, raw, root)


def load_model_config_from_raw(
    path: Path,
    raw: dict[str, object],
    root: Path,
) -> ModelConfig:
    fps = raw.get("fps", 15)
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError(f"{path}: field 'fps' must be a positive integer when present")
    alpha_clip = optional_unit_interval_number(raw, "alphaClip", path)
    alpha_mask = optional_alpha_mask_path(raw, path, root)
    if alpha_clip is not None and alpha_mask is not None:
        raise ValueError(f"{path}: only one of 'alphaClip' or 'alphaMask' may be present")

    return ModelConfig(
        path=path,
        blend_file=resolve_model_path(raw, path),
        sprites=require_string(raw, "sprites", path),
        visual=require_string(raw, "visual", path),
        scale=require_positive_number(raw, "scale", path) if "scale" in raw else 1.0,
        materials=optional_material_overrides(raw, path),
        fps=fps,
        alpha_clip=alpha_clip,
        alpha_mask=alpha_mask,
        offset_x=optional_int(raw, "offsetX", path),
        offset_y=optional_int(raw, "offsetY", path),
        surface_offset_y=optional_int(raw, "surfaceOffsetY", path),
        animations=optional_string_list(raw, "animations", path),
        directions=optional_direction_list(raw, path),
        include=optional_string_list(raw, "include", path),
        exclude=optional_string_list(raw, "exclude", path),
    )


def merge_variant_raw(
    base_raw: dict[str, object],
    variant_raw: dict[str, object],
) -> dict[str, object]:
    merged = {key: value for key, value in base_raw.items() if key not in {"type", "variants"}}
    merged.update(variant_raw)
    return merged


def load_variant_configs(path: Path, root: Path) -> tuple[str, list[VariantConfig]]:
    raw = load_json_object(path, "model config")
    config_type = raw.get("type", "simple")
    if not isinstance(config_type, str) or not config_type.strip():
        raise ValueError(f"{path}: field 'type' must be a non-empty string when present")
    normalized_type = config_type.strip().lower()

    if normalized_type == "variants":
        variants_raw = raw.get("variants")
        if not isinstance(variants_raw, list) or not variants_raw:
            raise ValueError(f"{path}: field 'variants' must be a non-empty array")

        variants: list[VariantConfig] = []
        for index, variant_value in enumerate(variants_raw):
            if not isinstance(variant_value, dict):
                raise ValueError(f"{path}: variant {index} must be an object")
            if "sprites" in variant_value or "visual" in variant_value:
                raise ValueError(f"{path}: variant {index} may not override 'sprites' or 'visual'")
            merged_raw = merge_variant_raw(raw, variant_value)
            variants.append(
                VariantConfig(
                    index=index,
                    model=load_model_config_from_raw(path, merged_raw, root),
                )
            )
        return normalized_type, variants

    return normalized_type, [VariantConfig(index=0, model=load_model_config_from_raw(path, raw, root))]


def find_scene_config(start_dir: Path, stop_dir: Path) -> SceneConfig:
    current = start_dir.resolve()
    stop_dir = stop_dir.resolve()
    while True:
        candidate = current / "scene.json"
        if candidate.is_file():
            raw = load_json_object(candidate, "scene config")
            tile_size_raw = raw.get("tileSize")
            lighting_raw = raw.get("lighting")
            if not isinstance(tile_size_raw, dict):
                raise ValueError(f"{candidate}: field 'tileSize' must be an object")
            if not isinstance(lighting_raw, dict):
                raise ValueError(f"{candidate}: field 'lighting' must be an object")
            scene = SceneConfig(
                path=candidate,
                tile_size=TileSize(
                    width=require_positive_int(tile_size_raw, "width", candidate),
                    height=require_positive_int(tile_size_raw, "height", candidate),
                ),
                lighting=LightingConfig(
                    azimuth=require_number(lighting_raw, "azimuth", candidate),
                    elevation=require_number(lighting_raw, "elevation", candidate),
                    strength=require_positive_number(lighting_raw, "strength", candidate),
                    ambient_strength=require_positive_number(
                        lighting_raw,
                        "ambientStrength",
                        candidate,
                    ),
                ),
            )
            return scene

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


def clean_output_dir(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def remove_file_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()


def remove_dir_if_exists(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)


def round_half_away_from_zero(value: float) -> int:
    if value >= 0.0:
        return int(value + 0.5)
    return int(value - 0.5)


def run_command(command: list[str], cwd: Path) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


def discover_config_files(path: Path) -> list[Path]:
    resolved = path.resolve()
    if resolved.is_file():
        if resolved.name == "scene.json":
            raise ValueError(f"expected a model config JSON, not a scene config: {resolved}")
        return [resolved]
    if not resolved.is_dir():
        raise FileNotFoundError(f"config path does not exist: {resolved}")

    config_files = sorted(
        candidate.resolve()
        for candidate in resolved.rglob("*.json")
        if candidate.is_file() and candidate.name != "scene.json"
    )
    if not config_files:
        raise FileNotFoundError(f"no model config JSON files found under: {resolved}")
    return config_files


def describe_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_visual_json(
    render_manifest: dict[str, object],
    texture_root: Path,
    repo_root_path: Path,
    surface_offset_y: int | None = None,
) -> dict[str, object]:
    fps = render_manifest.get("fps")
    entries = render_manifest.get("entries")
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError("render manifest is missing a valid 'fps'")
    if not isinstance(entries, dict):
        raise ValueError("render manifest is missing a valid 'entries' object")

    normalized_entries: dict[str, dict[str, object]] = {}
    for animation_key, payload in sorted(entries.items()):
        if not isinstance(animation_key, str) or not isinstance(payload, dict):
            raise ValueError("render manifest contains an invalid animation entry")
        textures = payload.get("textures")
        offset_x = payload.get("offsetX")
        offset_y = payload.get("offsetY")
        if (
            not isinstance(textures, list)
            or not textures
            or not all(isinstance(item, str) and item for item in textures)
            or not isinstance(offset_x, int)
            or not isinstance(offset_y, int)
        ):
            raise ValueError(f"render manifest entry {animation_key!r} is invalid")

        entry: dict[str, object] = {
            "textures": [
                str((texture_root / texture).resolve().relative_to(repo_root_path)).replace("\\", "/")
                for texture in textures
            ],
            "offsetX": offset_x,
            "offsetY": offset_y,
        }
        if not animation_key.startswith("static/"):
            entry["duration"] = len(textures) / fps
        normalized_entries[animation_key] = entry

    for direction in ("north", "east", "south", "west"):
        stationary_key = f"stationary/{direction}"
        idle_entry = normalized_entries.get(f"idle/{direction}")
        if idle_entry is None:
            continue
        idle_textures = idle_entry.get("textures")
        if not isinstance(idle_textures, list) or not idle_textures:
            raise ValueError(f"render manifest entry 'idle/{direction}' is invalid")
        normalized_entries[stationary_key] = {
            "textures": [idle_textures[0]],
            "offsetX": idle_entry["offsetX"],
            "offsetY": idle_entry["offsetY"],
        }

    if normalized_entries and all(key.startswith("static/") for key in normalized_entries):
        if len(normalized_entries) == 1:
            only_entry = next(iter(normalized_entries.values()))
            textures = only_entry["textures"]
            assert isinstance(textures, list)
            return {
                "type": "simple",
                "sortLayerOffset": 300,
                **({"surfaceOffsetY": surface_offset_y} if surface_offset_y is not None else {}),
                "offsetX": only_entry["offsetX"],
                "offsetY": only_entry["offsetY"],
                "texture": textures[0],
            }

    return {
        "type": "animator",
        "animator": "humanoid",
        "sortLayerOffset": 301,
        **({"surfaceOffsetY": surface_offset_y} if surface_offset_y is not None else {}),
        "animations": normalized_entries,
    }


def apply_offset_overrides(
    render_manifest: dict[str, object],
    *,
    offset_x: int | None,
    offset_y: int | None,
) -> dict[str, object]:
    if offset_x is None and offset_y is None:
        return render_manifest

    entries = render_manifest.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("render manifest is missing a valid 'entries' object")

    for payload in entries.values():
        if not isinstance(payload, dict):
            raise ValueError("render manifest contains an invalid animation entry")
        if offset_x is not None:
            payload["offsetX"] = offset_x
        if offset_y is not None:
            payload["offsetY"] = offset_y
    return render_manifest


def union_bbox(
    current: tuple[int, int, int, int] | None,
    candidate: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return (
        min(current[0], candidate[0]),
        min(current[1], candidate[1]),
        max(current[2], candidate[2]),
        max(current[3], candidate[3]),
    )


def crop_rendered_textures_to_alpha(
    render_manifest: dict[str, object],
    texture_output_dir: Path,
) -> dict[str, object]:
    entries = render_manifest.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("render manifest is missing a valid 'entries' object")

    for key, payload in entries.items():
        if not isinstance(key, str) or not isinstance(payload, dict):
            raise ValueError("render manifest contains an invalid animation entry")
        textures = payload.get("textures")
        crop = payload.get("crop")
        anchor = payload.get("anchor")
        if (
            not isinstance(textures, list)
            or not textures
            or not all(isinstance(item, str) and item for item in textures)
            or not isinstance(crop, dict)
            or not isinstance(anchor, dict)
        ):
            raise ValueError(f"render manifest entry {key!r} is invalid")

        crop_x = crop.get("x")
        crop_y = crop.get("y")
        anchor_x = anchor.get("x")
        anchor_y = anchor.get("y")
        if (
            not isinstance(crop_x, int)
            or not isinstance(crop_y, int)
            or not isinstance(anchor_x, (int, float))
            or not isinstance(anchor_y, (int, float))
        ):
            raise ValueError(f"render manifest entry {key!r} is invalid")

        alpha_bounds: tuple[int, int, int, int] | None = None
        image_size: tuple[int, int] | None = None
        for texture in textures:
            texture_path = texture_output_dir / texture
            with Image.open(texture_path) as image:
                rgba = image.convert("RGBA")
                if image_size is None:
                    image_size = rgba.size
                elif rgba.size != image_size:
                    raise ValueError(f"render manifest entry {key!r} mixes frame sizes")
                alpha_bounds = union_bbox(alpha_bounds, rgba.getchannel("A").getbbox())

        if image_size is None:
            raise ValueError(f"render manifest entry {key!r} does not contain textures")

        if alpha_bounds is None:
            left, top, right, bottom = (0, 0, image_size[0], image_size[1])
        else:
            left, top, right, bottom = alpha_bounds

        for texture in textures:
            texture_path = texture_output_dir / texture
            with Image.open(texture_path) as image:
                rgba = image.convert("RGBA")
                if (left, top, right, bottom) != (0, 0, rgba.width, rgba.height):
                    rgba = rgba.crop((left, top, right, bottom))
                rgba.save(texture_path)

        cropped_width = right - left
        cropped_height = bottom - top
        local_anchor_x = float(anchor_x) - left
        local_anchor_y = float(anchor_y) - top
        payload["crop"] = {
            "x": crop_x + left,
            "y": crop_y + top,
            "width": cropped_width,
            "height": cropped_height,
        }
        payload["anchor"] = {
            "x": local_anchor_x,
            "y": local_anchor_y,
        }
        payload["offsetX"] = round_half_away_from_zero((cropped_width / 2.0) - local_anchor_x)
        payload["offsetY"] = round_half_away_from_zero(local_anchor_y - cropped_height)

    return render_manifest


def dilate_opaque_pixels(pixels: list[tuple[int, int, int, int]], width: int, height: int) -> list[tuple[int, int, int, int]]:
    dilated = pixels[:]
    for y in range(height):
        for x in range(width):
            pixel_index = (y * width) + x
            if pixels[pixel_index][3] > 0:
                continue

            best_neighbor_index: int | None = None
            best_neighbor_alpha = 0
            for offset_y in (-1, 0, 1):
                neighbor_y = y + offset_y
                if neighbor_y < 0 or neighbor_y >= height:
                    continue
                for offset_x in (-1, 0, 1):
                    neighbor_x = x + offset_x
                    if offset_x == 0 and offset_y == 0:
                        continue
                    if neighbor_x < 0 or neighbor_x >= width:
                        continue

                    neighbor_index = (neighbor_y * width) + neighbor_x
                    neighbor_alpha = pixels[neighbor_index][3]
                    if neighbor_alpha <= best_neighbor_alpha:
                        continue
                    best_neighbor_index = neighbor_index
                    best_neighbor_alpha = neighbor_alpha

            if best_neighbor_index is None:
                continue

            dilated[pixel_index] = pixels[best_neighbor_index]
    return dilated


def mask_alpha_on_render_grid(
    mask_alpha: list[int],
    mask_width: int,
    mask_height: int,
    image_width: int,
    image_height: int,
    offset_x: int = 0,
    offset_y: int = 0,
) -> list[int]:
    applied_alpha = [0] * (image_width * image_height)
    start_x = max(0, min(offset_x, image_width - 1)) if image_width > 0 else 0
    start_y = max(0, min(offset_y, image_height - 1)) if image_height > 0 else 0
    overlap_width = min(mask_width, image_width - start_x)
    overlap_height = min(mask_height, image_height - start_y)
    for y in range(overlap_height):
        for x in range(overlap_width):
            applied_alpha[((start_y + y) * image_width) + start_x + x] = mask_alpha[
                (y * mask_width) + x
            ]
    return applied_alpha


def apply_alpha_mask_to_textures(
    render_manifest: dict[str, object],
    texture_output_dir: Path,
    mask_path: Path,
) -> dict[str, object]:
    entries = render_manifest.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("render manifest is missing a valid 'entries' object")

    with Image.open(mask_path) as mask_image:
        mask_rgba = mask_image.convert("RGBA")
        mask_width, mask_height = mask_rgba.size
        mask_alpha = list(mask_rgba.getchannel("A").getdata())

    for key, payload in entries.items():
        if not isinstance(key, str) or not isinstance(payload, dict):
            raise ValueError("render manifest contains an invalid animation entry")
        textures = payload.get("textures")
        if (
            not isinstance(textures, list)
            or not textures
            or not all(isinstance(item, str) and item for item in textures)
        ):
            raise ValueError(f"render manifest entry {key!r} is invalid")

        for texture in textures:
            texture_path = texture_output_dir / texture
            with Image.open(texture_path) as image:
                rgba = image.convert("RGBA")
                image_width, image_height = rgba.size
                pixels = list(rgba.getdata())
                dilated = dilate_opaque_pixels(pixels, image_width, image_height)
                opaque_columns: list[int] = []
                opaque_rows: list[int] = []
                for pixel_index, pixel in enumerate(dilated):
                    if pixel[3] <= 0:
                        continue
                    opaque_columns.append(pixel_index % image_width)
                    opaque_rows.append(pixel_index // image_width)

                mask_offset_x = 0
                mask_offset_y = 0
                if mask_width < image_width and opaque_columns:
                    opaque_left = min(opaque_columns)
                    opaque_right = max(opaque_columns) + 1
                    if opaque_left > (image_width - opaque_right):
                        mask_offset_x = max(0, min(image_width - mask_width, opaque_right - mask_width))
                if mask_height < image_height and opaque_rows:
                    opaque_bottom = min(opaque_rows)
                    opaque_top = max(opaque_rows) + 1
                    if opaque_bottom > (image_height - opaque_top):
                        mask_offset_y = max(0, min(image_height - mask_height, opaque_top - mask_height))

                applied_mask_alpha = mask_alpha_on_render_grid(
                    mask_alpha,
                    mask_width,
                    mask_height,
                    image_width,
                    image_height,
                    mask_offset_x,
                    mask_offset_y,
                )
                masked_pixels = []
                for index, (_r, _g, _b, _a) in enumerate(pixels):
                    if applied_mask_alpha[index] > 0:
                        masked_pixels.append(dilated[index][:3] + (255,))
                    else:
                        masked_pixels.append((0, 0, 0, 0))
                rgba.putdata(masked_pixels)
                rgba.save(texture_path)

    return render_manifest


def render_model(
    *,
    args: argparse.Namespace,
    root: Path,
    model_config: ModelConfig,
    texture_output_dir: Path,
) -> dict[str, object]:
    scene_config = find_scene_config(model_config.blend_file.parent, root)
    render_metadata_file = texture_output_dir / "render_metadata.json"
    worker_script = root / "scripts" / "blender_render_worker.py"

    texture_output_dir.mkdir(parents=True, exist_ok=True)

    blender_command = [
        args.blender,
        "--background",
        str(model_config.blend_file),
        "--python",
        str(worker_script),
        "--",
        "--output-dir",
        str(texture_output_dir),
        "--metadata-file",
        str(render_metadata_file),
        "--tile-width",
        str(scene_config.tile_size.width),
        "--tile-height",
        str(scene_config.tile_size.height),
        "--light-azimuth",
        str(scene_config.lighting.azimuth),
        "--light-elevation",
        str(scene_config.lighting.elevation),
        "--light-strength",
        str(scene_config.lighting.strength),
        "--ambient-strength",
        str(scene_config.lighting.ambient_strength),
        "--fps",
        str(model_config.fps),
        "--scale",
        str(model_config.scale),
        "--engine",
        args.engine,
    ]

    if model_config.alpha_clip is not None:
        blender_command.extend(["--alpha-clip", str(model_config.alpha_clip)])
    if model_config.materials is not None:
        material_payload = {
            material_name: {
                node_name: str(texture_path)
                for node_name, texture_path in nodes.items()
            }
            for material_name, nodes in model_config.materials.items()
        }
        blender_command.extend(["--materials-json", json.dumps(material_payload, sort_keys=True)])

    if model_config.directions is not None:
        for direction in model_config.directions:
            blender_command.extend(["--direction", direction])
    if model_config.animations is not None:
        for animation in model_config.animations:
            blender_command.extend(["--action", animation])
    if model_config.include is not None:
        for object_name in model_config.include:
            blender_command.extend(["--include-object", object_name])
    if model_config.exclude is not None:
        for object_name in model_config.exclude:
            blender_command.extend(["--exclude-object", object_name])

    run_command(blender_command, cwd=root)

    render_manifest = load_json_object(render_metadata_file, "render metadata")
    render_manifest = crop_rendered_textures_to_alpha(render_manifest, texture_output_dir)
    if model_config.alpha_mask is not None:
        render_manifest = apply_alpha_mask_to_textures(
            render_manifest,
            texture_output_dir,
            model_config.alpha_mask,
        )
        render_manifest = crop_rendered_textures_to_alpha(render_manifest, texture_output_dir)
    render_manifest = apply_offset_overrides(
        render_manifest,
        offset_x=model_config.offset_x,
        offset_y=model_config.offset_y,
    )
    render_metadata_file.write_text(json.dumps(render_manifest, indent=2) + "\n", encoding="utf-8")
    return render_manifest


def build_variant_visual_json(
    *,
    variant_visuals: list[dict[str, object]],
    texture_paths: list[Path],
    repo_root_path: Path,
) -> dict[str, object]:
    if not variant_visuals:
        raise ValueError("variants config must produce at least one rendered variant")

    offset_x: int | None = None
    offset_y: int | None = None
    sort_layer_offset: int | None = None
    surface_offset_y: int | None = None
    anchor_x_values: list[int] = []
    anchor_y_values: list[int] = []
    widths: list[int] = []
    heights: list[int] = []
    for index, visual in enumerate(variant_visuals):
        if visual.get("type") != "simple":
            raise ValueError(
                f"variant {index} produced a non-simple visual; variants currently require a single static sprite"
            )
        current_offset_x = visual.get("offsetX")
        current_offset_y = visual.get("offsetY")
        current_sort_layer_offset = visual.get("sortLayerOffset")
        current_surface_offset_y = visual.get("surfaceOffsetY")
        if not isinstance(current_offset_x, int) or not isinstance(current_offset_y, int):
            raise ValueError(f"variant {index} produced an invalid simple visual")
        if current_sort_layer_offset is not None and not isinstance(current_sort_layer_offset, int):
            raise ValueError(f"variant {index} produced an invalid sortLayerOffset")
        if current_surface_offset_y is not None and not isinstance(current_surface_offset_y, int):
            raise ValueError(f"variant {index} produced an invalid surfaceOffsetY")
        with Image.open(texture_paths[index]) as image:
            width, height = image.size
        anchor_x = round((width / 2.0) - current_offset_x)
        anchor_y = height + current_offset_y
        anchor_x_values.append(anchor_x)
        anchor_y_values.append(anchor_y)
        widths.append(width)
        heights.append(height)
        if offset_x is None:
            sort_layer_offset = current_sort_layer_offset if isinstance(current_sort_layer_offset, int) else 300
            surface_offset_y = current_surface_offset_y if isinstance(current_surface_offset_y, int) else None
        if isinstance(current_sort_layer_offset, int) and current_sort_layer_offset != sort_layer_offset:
            raise ValueError("all variants must render with identical sortLayerOffset values")
        if current_surface_offset_y != surface_offset_y:
            raise ValueError("all variants must render with identical surfaceOffsetY values")

    common_anchor_x = max(anchor_x_values)
    common_anchor_y = max(anchor_y_values)
    common_right_extent = max(width - anchor_x for width, anchor_x in zip(widths, anchor_x_values))
    common_bottom_extent = max(height - anchor_y for height, anchor_y in zip(heights, anchor_y_values))
    common_width = common_anchor_x + common_right_extent
    common_height = common_anchor_y + common_bottom_extent

    for index, texture_path in enumerate(texture_paths):
        paste_x = common_anchor_x - anchor_x_values[index]
        paste_y = common_anchor_y - anchor_y_values[index]
        with Image.open(texture_path) as image:
            converted = image.convert("RGBA")
            if converted.size == (common_width, common_height) and paste_x == 0 and paste_y == 0:
                continue
            canvas = Image.new("RGBA", (common_width, common_height), (0, 0, 0, 0))
            canvas.paste(converted, (paste_x, paste_y))
            canvas.save(texture_path)

    offset_x = round((common_width / 2.0) - common_anchor_x)
    offset_y = common_anchor_y - common_height

    return {
        "type": "variants",
        "sortLayerOffset": sort_layer_offset if sort_layer_offset is not None else 300,
        **({"surfaceOffsetY": surface_offset_y} if surface_offset_y is not None else {}),
        "offsetX": offset_x if offset_x is not None else 0,
        "offsetY": offset_y if offset_y is not None else 0,
        "textures": [
            str(texture_path.resolve().relative_to(repo_root_path)).replace("\\", "/")
            for texture_path in texture_paths
        ],
    }


def finalize_simple_visual_output(
    *,
    visual_json: dict[str, object],
    structured_output_dir: Path,
    flat_texture_file: Path,
    root: Path,
) -> dict[str, object]:
    texture = visual_json.get("texture")
    if not isinstance(texture, str) or not texture:
        raise ValueError("simple visual did not produce a valid texture path")

    source_texture_path = ensure_repo_relative_output(root / texture, root, "simple texture path")
    flat_texture_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_texture_path, flat_texture_file)
    visual_json["texture"] = str(flat_texture_file.resolve().relative_to(root)).replace("\\", "/")

    remove_dir_if_exists(structured_output_dir)
    return visual_json


def render_config(args: argparse.Namespace, root: Path, config_path: Path) -> int:
    try:
        config_type, variants = load_variant_configs(config_path, root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    primary_model = variants[0].model
    visual_output_file = ensure_repo_relative_output(
        root / "client" / "data" / "illarion" / "visuals" / f"{primary_model.visual}.json",
        root,
        "visual output path",
    )

    try:
        if config_type == "variants":
            texture_stem_path = ensure_repo_relative_output(
                root / "client" / "textures" / primary_model.sprites,
                root,
                "texture output path",
            )
            texture_parent = texture_stem_path.parent
            texture_stem = texture_stem_path.name
            temp_root = texture_parent / f".{texture_stem}__variants"

            try:
                if not args.keep_output:
                    if temp_root.is_dir():
                        shutil.rmtree(temp_root)
                    for variant in variants:
                        remove_file_if_exists(texture_parent / f"{texture_stem}-{variant.index}.png")
                temp_root.mkdir(parents=True, exist_ok=True)

                variant_visuals: list[dict[str, object]] = []
                variant_texture_paths: list[Path] = []
                for variant in variants:
                    model_config = variant.model
                    if model_config.sprites != primary_model.sprites or model_config.visual != primary_model.visual:
                        raise ValueError("all variants must share the same 'sprites' and 'visual' values")
                    if not model_config.blend_file.is_file():
                        raise FileNotFoundError(f"blend file does not exist: {model_config.blend_file}")

                    variant_output_dir = temp_root / str(variant.index)
                    if not args.keep_output:
                        clean_output_dir(variant_output_dir)
                    else:
                        variant_output_dir.mkdir(parents=True, exist_ok=True)

                    render_manifest = render_model(
                        args=args,
                        root=root,
                        model_config=model_config,
                        texture_output_dir=variant_output_dir,
                    )
                    variant_visual = build_visual_json(
                        render_manifest,
                        variant_output_dir,
                        root,
                        surface_offset_y=model_config.surface_offset_y,
                    )
                    variant_visuals.append(variant_visual)

                    source_texture = variant_visual.get("texture")
                    if not isinstance(source_texture, str) or not source_texture:
                        raise ValueError(f"variant {variant.index} did not produce a single texture")
                    source_texture_path = ensure_repo_relative_output(root / source_texture, root, "variant texture path")
                    target_texture_path = ensure_repo_relative_output(
                        texture_parent / f"{texture_stem}-{variant.index}.png",
                        root,
                        "variant texture output path",
                    )
                    target_texture_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_texture_path, target_texture_path)
                    variant_texture_paths.append(target_texture_path)

                visual_json = build_variant_visual_json(
                    variant_visuals=variant_visuals,
                    texture_paths=variant_texture_paths,
                    repo_root_path=root,
                )
            finally:
                if not args.keep_output and temp_root.is_dir():
                    shutil.rmtree(temp_root)
        else:
            model_config = primary_model
            if not model_config.blend_file.is_file():
                raise FileNotFoundError(f"blend file does not exist: {model_config.blend_file}")
            texture_stem_path = ensure_repo_relative_output(
                root / "client" / "textures" / model_config.sprites,
                root,
                "texture output path",
            )
            texture_output_dir = texture_stem_path
            flat_texture_file = texture_stem_path.with_suffix(".png")

            if not args.keep_output:
                remove_file_if_exists(flat_texture_file)
                clean_output_dir(texture_output_dir)
            else:
                texture_output_dir.mkdir(parents=True, exist_ok=True)

            render_manifest = render_model(
                args=args,
                root=root,
                model_config=model_config,
                texture_output_dir=texture_output_dir,
            )
            visual_json = build_visual_json(
                render_manifest,
                texture_output_dir,
                root,
                surface_offset_y=model_config.surface_offset_y,
            )
            if visual_json.get("type") == "simple":
                visual_json = finalize_simple_visual_output(
                    visual_json=visual_json,
                    structured_output_dir=texture_output_dir,
                    flat_texture_file=flat_texture_file,
                    root=root,
                )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    visual_output_file.parent.mkdir(parents=True, exist_ok=True)
    visual_output_file.write_text(json.dumps(visual_json, indent=2) + "\n", encoding="utf-8")
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
