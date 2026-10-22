#!/usr/bin/env python3
"""Migrate the legacy 76x37 pack, then regenerate its procedural assets.

Run once without --resume to prepare the files; use --resume for interrupted
render batches. Logs and successful config paths are kept in --work-dir.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SX, SY = 128 / 76, 64 / 37


def rounded(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def scale_offsets(value: object) -> None:
    if isinstance(value, list):
        for child in value:
            scale_offsets(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in ("offsetX", "offsetY", "surfaceOffsetY"):
                value[key] = rounded(child * (SX if key == "offsetX" else SY))
            else:
                scale_offsets(child)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare(work: Path) -> None:
    grid_path = ROOT / "client/data/illarion/render_grids/default.json"
    grid = json.loads(grid_path.read_text())
    if (grid["tileWidth"], grid["tileHeight"]) != (76, 37):
        raise ValueError("Preparation requires the original 76x37 pack; use --resume after preparation")
    # Preserve the original visual definitions for alias alignment after rendering.
    originals = {str(p.relative_to(ROOT)): json.loads(p.read_text())
                 for p in (ROOT / "client/data/illarion/visuals").rglob("*.json")}
    write_json(work / "original-visuals.json", originals)
    for folder in ("client/textures", "masks"):
        for path in (ROOT / folder).rglob("*.png"):
            if path.parent == ROOT / "client/textures/illarion/ui" and path.name.startswith("cursor_"):
                continue
            with Image.open(path) as image:
                image.resize((max(1, rounded(image.width * SX)),
                              max(1, rounded(image.height * SY))),
                             Image.Resampling.NEAREST).save(path)
    for folder in ("models", "client/data/illarion/visuals"):
        for path in (ROOT / folder).rglob("*.json"):
            if path.parent == ROOT / "client/data/illarion/visuals" and path.name.startswith("cursor_"):
                continue
            raw = json.loads(path.read_text())
            previous = json.dumps(raw)
            scale_offsets(raw)
            if "tileSize" in raw:
                raw["tileSize"] = {"width": 128, "height": 64}
            if json.dumps(raw) != previous:
                write_json(path, raw)
    for path in (ROOT / "client/textures").rglob("render_metadata.json"):
        raw = json.loads(path.read_text())
        scale_offsets(raw)
        raw["tileSize"] = {"width": 128, "height": 64}
        for entry in raw.get("entries", {}).values():
            for key in ("crop", "anchor"):
                for field, value in entry.get(key, {}).items():
                    entry[key][field] = rounded(value * (SX if field in ("x", "width") else SY))
        write_json(path, raw)
    write_json(ROOT / "tiles/scene.json", {"tileSize": {"width": 128, "height": 64}})
    grid.update(tileWidth=128, tileHeight=64, tileStepX=64, tileStepY=32,
                tileStepZ=rounded(grid["tileStepZ"] * SX))
    write_json(grid_path, grid)
    (work / "prepared").touch()


def render(config: Path, pipeline: str, work: Path) -> tuple[str, bool]:
    name = str(config.relative_to(ROOT))
    log = work / (name.replace("/", "__") + ".log")
    marker = log.with_suffix(".done")
    if marker.exists():
        return name, True
    if pipeline == "sprite_pipeline.py":
        import sprite_pipeline
        _, variants = sprite_pipeline.load_variant_configs(config, ROOT)
        if any(not variant.model.blend_file.is_file() for variant in variants):
            log.write_text("Source model unavailable; retained scaled legacy sprites.\n")
            marker.touch()
            return name, True
    # Preserve scaled fallback graphics if Blender rejects a legacy model.
    raw = json.loads(config.read_text())
    stem = ROOT / "client/textures" / raw["sprites"]
    outputs = [stem, stem.with_suffix(".png"),
               *stem.parent.glob(stem.name + "-*.png"),
               ROOT / "client/data/illarion/visuals" / (raw["visual"] + ".json")]
    with tempfile.TemporaryDirectory(dir=work) as backup_dir:
        saved = []
        for index, path in enumerate(outputs):
            if path.exists():
                backup = Path(backup_dir) / str(index)
                if path.is_dir():
                    shutil.copytree(path, backup)
                else:
                    shutil.copy2(path, backup)
                saved.append((path, backup))
        with log.open("w") as output:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / pipeline),
                                     str(config)], cwd=ROOT, stdout=output,
                                    stderr=subprocess.STDOUT)
        if result.returncode:
            for path, backup in saved:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                if backup.is_dir():
                    shutil.copytree(backup, path)
                else:
                    shutil.copy2(backup, path)
    if result.returncode == 0:
        marker.touch()
    return name, result.returncode == 0


def align_aliases(work: Path) -> None:
    originals = json.loads((work / "original-visuals.json").read_text())
    # Copies with identical old geometry must follow the regenerated geometry,
    # while retaining their own metadata and render policy.
    def signature(raw: dict) -> str:
        return json.dumps({k: raw[k] for k in ("type", "texture", "textures", "animations",
                                              "offsetX", "offsetY") if k in raw}, sort_keys=True)
    canonical = {}
    configs = sorted((ROOT / "models").rglob("*.json"))
    configs += sorted((ROOT / "tiles").rglob("*.json"))
    for path in configs:
        raw = json.loads(path.read_text())
        if "visual" in raw:
            name = f'client/data/illarion/visuals/{raw["visual"]}.json'
            if name in originals and (ROOT / name).exists():
                canonical[signature(originals[name])] = json.loads((ROOT / name).read_text())
    for name, original in originals.items():
        source = canonical.get(signature(original))
        path = ROOT / name
        current = json.loads(path.read_text())
        for key in ("metadata", "sortLayerOffset", "occlusionFade", "instanced", "animator", "light"):
            if key in original:
                current[key] = original[key]
        if "surfaceOffsetY" in original and "surfaceOffsetY" not in current:
            current["surfaceOffsetY"] = rounded(original["surfaceOffsetY"] * SY)
        for key in ("texture", "textures", "animations", "offsetX", "offsetY"):
            if source is not None and key in source:
                current[key] = source[key]
        write_json(path, current)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/illarion-upscale-128x64"))
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        prepare(work)
    elif not (work / "prepared").exists():
        parser.error("No prepared migration in --work-dir")
    tasks = [(p, "tile_pipeline.py") for p in sorted((ROOT / "tiles").rglob("*.json")) if p.name != "scene.json"]
    # Match the normal sequential pipeline: the last sorted config wins when
    # legacy configs share an output. Render that destination only once.
    models = {}
    for path in sorted((ROOT / "models").rglob("*.json")):
        if path.name != "scene.json":
            raw = json.loads(path.read_text())
            models[raw["sprites"]] = path
    tasks += [(p, "sprite_pipeline.py") for p in sorted(models.values())]
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(render, p, pipeline, work) for p, pipeline in tasks]
        for index, future in enumerate(as_completed(futures), 1):
            name, success = future.result()
            print(f"[{index}/{len(tasks)}] {'OK' if success else 'FAILED'} {name}", flush=True)
            if not success:
                failures.append(name)
    if failures:
        print(f"{len(failures)} failed configs; see {work} and rerun with --resume", flush=True)
        return 1
    align_aliases(work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
