# Gobaith Reborn - Open Assets Collection

This Selene bundle provides open source assets for [Gobaith Reborn](https://gobaith-reborn.com/) and the `illarion-gobaith-data` bundle.

## Prerequisites

The bundle can be used as-is; in order to make changes and rerender, additional tools are required:

- **Python 3.10 or newer** for the command-line scripts.
- **Pillow** for image processing and **NumPy** for procedural effects.
- **Blender**, available as `blender` on your `PATH`, for rendering models and running scripts that import `bpy`. These scripts use Blender's bundled Python.

Run the examples below from this bundle's root directory. A virtual environment keeps Python dependencies separate:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Pillow numpy
```

## Folder structure

```text
client/
  data/illarion/visuals/  Visual JSON definitions consumed by the client
  textures/illarion/     Client textures and generated sprite frames
  sounds/illarion/       Sound effects
  music/illarion/        Music
models/                 Blender source models, textures, and render config JSON
tiles/                  Source tile images, tile configs, and animated water frames
masks/                  Tile transition and wall alpha masks
runes/                  Rune SVG source artwork
particles/              Particle scenes, source images, and effect previews
scripts/                Asset generation, rendering, reporting, and checks
  data/                 Herb catalog and supporting documentation
bundle.json             Selene bundle metadata
CREDITS.csv             Asset sources, authors, and licenses
```

The sprite pipeline uses the nearest ancestor `scene.json` for scene settings, such as tile size and lighting. Model JSON files select sprite and visual output paths and can override scale, animations, directions, and materials. Tile configs describe source textures, output paths, and transitions.

## Script usage

### Render model sprites

Render a single model config or recursively process a directory of configs:

```sh
python scripts/sprite_pipeline.py models/chars/halfling_male/halfling_male.json
python scripts/sprite_pipeline.py models/chars
```

The pipeline invokes `scripts/blender_render_worker.py`, writes sprite frames under `client/textures/`, and generates visual JSON under `client/data/illarion/visuals/`. Use `--blender /path/to/blender` to select an executable and `--engine CYCLES` to select a render engine. By default, the target texture directory is cleared before rendering; `--keep-output` preserves existing files.

### Generate tiles

```sh
python scripts/tile_pipeline.py tiles/grass.json
python scripts/tile_pipeline.py tiles
```

The tile pipeline projects source images into isometric textures and writes visual JSON, including transitions where configured. It also supports `--keep-output`.

To regenerate animated water source frames before processing their tile config:

```sh
python scripts/render_water_tiles.py --size 256 --frames 16
python scripts/tile_pipeline.py tiles/water/water.json
```

### Build models and effects

The `build_*.py` scripts procedurally generate particular Blender models. For example:

```sh
blender -b --python scripts/build_herbs.py -- --validate-only
blender -b --python scripts/build_herbs.py
```

The herb builder reads `scripts/data/herbs.json`; `--only` accepts item IDs or slugs to rebuild a subset. Arguments after Blender's `--` are passed to the script.

Most procedural `render_*_effects.py` scripts run directly with Python and write effect frames and previews. Some require a `--variant`; check their help for supported choices:

```sh
python scripts/render_fireball.py --variant fireball
python scripts/render_magic_effects.py --help
```

Blender particle scenes use a separate renderer:

```sh
blender -b -t 4 --python scripts/render_blender_effects.py
```

Other helpers procedurally generate wood and log textures, UI markers, inventory slots, and combat animations. Consult each script's docstring and, where available, `--help` for inputs and output locations. Generators write into the asset tree and can replace existing assets.

### Render runes

Install KDE SVG tools (`ksvgtopng`) and the Noto Sans Egyptian Hieroglyphs,
CJK JP, Symbols, Symbols 2, and Math fonts used by the SVG text glyphs. Then run:

```sh
python3 scripts/render_runes.py
```

This renders every SVG in `runes/` to a transparent 86 × 86 PNG, preserving the
square SVG canvas proportions, with the same
filename stem in `client/textures/illarion/ui/`, replacing matching PNGs. Defaults
are relative to the script, so it can run from any directory. Use `--width` and
`--height` to change the output dimensions, `--source` and `--output` to override directories,
or `--renderer` to select a `ksvgtopng` executable.

### Check credits

```sh
python scripts/check_missing_credits.py
```

The credits check reports model `.blend` files and client texture `.png` files without a matching entry in `CREDITS.csv`. 

## Credits and licenses

Assets use multiple licenses. See [CREDITS.csv](./CREDITS.csv) for sources, authors, and individual licenses, and [LICENSE](./LICENSE) for the repository license notice. Update the credits when adding or replacing assets.
