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
