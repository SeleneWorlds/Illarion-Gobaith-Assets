# Illarion Gobaith - Open Assets Collection

This is a Selene bundle providing open source textures for use with the [Illarion-Gobaith-Data](https://github.com/SeleneWorlds/Illarion-Gobaith-Data) bundle.

It is currently a very barebones collection, with many items sharing the same graphics. Contributions are welcome.

See [CREDITS.csv](./CREDITS.csv) for a full listing of sources.

## Texture resolution

The pack uses a 128×64 isometric tile footprint. Sprites retain their individual
cropped dimensions; their offsets and the render grid use the same pixel scale.
Model and terrain source textures stay at their original resolution.

Regenerate model sprites with `python3 scripts/sprite_pipeline.py models` and
terrain tiles with `python3 scripts/tile_pipeline.py tiles` (Blender and Pillow
are required). The scene files in `models/` and `tiles/` define the target size.

`scripts/upscale_pack.py` performs the one-time migration from the legacy 76×37
pack, scaling existing sprites and masks with nearest-neighbor sampling before
regenerating terrain and available models. Its `--resume` option retries an
interrupted batch using logs in `/tmp/illarion-upscale-128x64`; keep that directory
until the migration finishes. Characters whose Blender sources are unavailable
retain scaled sprites.

## Asset categories

Item model sources live in `models/items/<category>/<model>/`, with categories
such as `food`, `weapons`, `tools`, `containers`, `books`, `clothing`, and
`materials`. Keep each model's Blender files, source textures, render JSONs,
and optional local `scene.json` together. Shared material libraries remain in
`models/materials/`.

Rendered item textures live in `client/textures/illarion/items/<category>/`.
Most categories have a model subfolder; all rendered books share `books/`,
buckets share `containers/bucket/`, and potions share `potions/`. Furniture,
walls, trees, crops, and other scenery mirror their existing model categories.
Procedural item effects live in `effects/`, and item markers in `markers/`.
Visual IDs stay in `client/data/illarion/visuals/items/`; item IDs and runtime
visual names do not change when texture folders change.

Set each render JSON's `sprites` path to its categorized texture destination.
The sprite pipeline recursively discovers nested model folders. Run a whole
category or a single model, for example:

```sh
python3 scripts/sprite_pipeline.py models/items/food
python3 scripts/sprite_pipeline.py models/items/containers/bucket
```

## Material and color overrides

Use `materialOverrides` to assign materials already saved in a shared Blender
model. Keys are object names, then the original material slot names; values name
the replacement materials. Assignments affect only that object, even when its
mesh is shared. Keep unused alternatives with Blender's Fake User enabled.

```json
"materialOverrides": {
  "Shield": {"MetalCoating": "WoodCoating"}
},
"colorOverrides": {
  "MetalRim": {"Color": [0.65, 0.4, 0.08, 1.0]}
},
"exclude": ["Emblem"]
```

`colorOverrides` maps material names to named RGB shader nodes and their new
linear RGB or RGBA values in `[0, 1]` (RGB defaults to alpha 1). Connect the RGB
node to the material's color input in Blender. Color overrides use temporary
material copies and do not modify the source model. Missing objects, slots,
materials, or RGB nodes produce an error.

The existing `materials` field still replaces image texture nodes by filename.
The renderer applies material assignments, then texture replacements, then color
overrides. All three fields can be set per variant; a variant replaces the entire
field when provided, and `null` disables inherited overrides.

## Reflections for glossy items

Add `"reflections": "studio"` to a model render JSON to give metallic or glossy
materials broad reflected highlights, as used by `models/items/currency/coins/`.
The renderer creates a temporary reflection environment and enables Eevee ray
tracing when available. It keeps the shared sun and uses the scene's
`ambientStrength` for the reflection intensity. No lights or world shader need
to be saved in the model.

For horizontal polished surfaces such as the medal, `"reflections": "studio-flat"`
positions a softer reflection card for the flat face, preserving the model pose
and bump-map engraving. The standard `studio` preset stays unchanged.

Keep material settings in Blender: metals generally need a high Metallic value
and Roughness around 0.15–0.3 for visible shine. The preset does not change
materials. Omitting `reflections` (or setting it to `"none"`) preserves the
existing lighting behavior. Variants inherit the option and can override it.

For armor inventory sprites, set `"direction": "armor"` in the model config.
This rotates the model 15 degrees so the shirt neckline points toward the
upper-right of the sprite, with the hem toward the lower-left.

## Procedural rift portals

Items 10 (blue) and 798 (red) use original procedural energy sprites, with eight
94×154 RGBA frames in a 0.4-second loop. Generate them with NumPy and Pillow:

```sh
python3 scripts/render_portals.py --write-visuals
```

The generator uses no input images. `--seed` controls the turbulence;
`--output-dir` and `--preview-dir` can redirect textures and previews for experiments.
Contact sheets and animated GIFs are in `particles/portal-preview/`.
These two items are maintained by this generator; the other portal items retain
their Blender models. Run this command after the one-time upscale migration,
which can replace animated item definitions.

## Simulated campfire

`models/structures/campfire/campfire.blend` contains a Mantaflow gas/fire
simulation. Its relative `campfire_fire_cache/` directory holds generated baked
data and is ignored by Git. The rendered PNG frames remain versioned and need
no simulation cache at runtime. Before rerendering on a fresh checkout, after
deleting the cache, or after changing the fuel source, domain, or turbulence:

```sh
blender -b --python scripts/bake_campfire.py
python3 scripts/sprite_pipeline.py models/structures/campfire/campfire.json
```

The bake script is a command-line convenience for Blender's Bake All operation;
you can also bake the Fire_Domain simulation from Blender's Physics properties.
Material-only changes can reuse an existing bake.

The config uses `"frameRange": [33, 64]` and `"fps": 24` to export 32 frames
after the simulation warms up. A single-direction scene frame range produces
an `animated` visual with a shared crop and anchor across all frames. The
existing item light is retained. Frame ranges are inclusive and cannot be
combined with named armature animations.

## Portable torches

`models/items/lighting/torch/torch.json` renders the unlit torch (item 391).
`torch_lit.json` renders item 392 with a simulated flame at the wrapped head,
using 32 frames at 24 fps. Both torch surfaces use Standard color management,
roughness 0.75, and zero emission. Their local `scene.json` lights the visible
side of the handheld pose to preserve the dark wood texture's detail.
The generated `torch_fire_cache/` is ignored by Git.
To bake the lit torch on a fresh checkout or after changing its simulation:

```sh
blender -b --python scripts/bake_fire.py -- models/items/lighting/torch/torch_lit.blend
blender -b --python scripts/build_wall_torch_flames.py -- --handheld
python3 scripts/sprite_pipeline.py models/items/lighting/torch
```

The shared bake command also accepts other fire models with a `Fire_Domain`
object, including `models/structures/campfire/campfire.blend`.

The lit wall torches (items 402 and 404) use the same flame setup in
`models/furniture/wall_torch/wall_torch_lit.blend`, with a separate ignored
`wall_torch_fire_cache/`. Both directions render 32 frames at 24 fps. To rebuild:

```sh
blender -b --python scripts/bake_fire.py -- models/furniture/wall_torch/wall_torch_lit.blend
blender -b --python scripts/build_wall_torch_flames.py
python3 scripts/sprite_pipeline.py models/furniture/wall_torch
```

Both portable and wall torches use the same orange flame and bright yellow core.
The flame builder converts the baked fire grids into animated surfaces for
Eevee, preserving the simulation motion without a rectangular volume artifact.
These surfaces are saved in the Blender source; rendering needs no cache until
the animation is rebuilt.

## Wall rendering

Wall configs use `gridAligned: true` and `alphaClip: 0.5`. The mesh defines the
silhouette, including window and door openings. Walls rotate around the tile
origin, including hidden Boolean operands that cut out doors and windows. The
camera projects that origin onto an integer pixel boundary.
Cropping pads odd widths to an even width so integer center offsets preserve
placement exactly. Offsets are calculated from the projected origin rather than
set by hand. Adjacent tiles are separated by 64 pixels horizontally and 32
pixels vertically.

A grid-aligned config may set `translation: [x, y, z]` in model units before
rotation. For example, the south pillar uses `[-0.375, -0.375, 0]` with the
south direction to place its quarter-tile footprint at the front corner.
Its sprite offsets are still calculated from the tile origin.

Run the regression checks after rendering:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/test_wall_alignment.py --preview /tmp/wall-alignment.png
```

The checks assemble items 240, 38, 33, and 922, inspect both sides of five joins
for transparent seams, and check pixel anchors, base pixels, mask clipping, and
crop placement. Item 86 also has a regression check that verifies the open
doorway and its surrounding frame.

## Contributing

All contributed files must be listed in [CREDITS.csv](./CREDITS.csv) alongside their license identifier, author, and a source URL (if available).

Assets must be under an Open Source license. Proprietary assets are not accepted as part of this bundle.

Submissions must either be handmade or procedurally generated; AI-generated assets will not be accepted.

## Procedural pure elements

The pure water, fire, earth, and air items use original glossy drop sprites,
rendered without image inputs. Regenerate them with NumPy and Pillow:

```sh
python3 scripts/render_pure_elements.py
```

The generator preserves each item's texture dimensions and placement. Use
`--output-dir` for experiments and `--preview /tmp/pure-elements.png` for an
enlarged comparison sheet.

## Procedural herbs

Generate ordinary herb models from the editable [herb catalog](scripts/data/herbs.json).
See [the generator documentation](scripts/data/herbs.md) for rebuilding and supported
plant parts.
