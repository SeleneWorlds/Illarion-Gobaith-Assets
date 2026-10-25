# Procedural herbs

`herbs.json` is the editable source catalog for `scripts/build_herbs.py`.
Generated models and sprite recipes live in `models/items/plants/herbs/`.

## Rebuild

From the bundle root:

```sh
blender -b --python scripts/build_herbs.py
python3 scripts/sprite_pipeline.py models/items/plants/herbs
```

Build selected herbs by item ID or slug:

```sh
blender -b --python scripts/build_herbs.py -- --only 144 sandberry
python3 scripts/sprite_pipeline.py models/items/plants/herbs/virgins_weed.json
python3 scripts/sprite_pipeline.py models/items/plants/herbs/sandberry.json
```

Validate the entire catalog without writing output:

```sh
blender -b --python scripts/build_herbs.py -- --validate-only
```

`--config PATH` selects another catalog. `--output-dir /tmp/herb-preview` builds
models and recipes elsewhere for inspection. Render recipes still name the
normal item destinations: running the sprite pipeline on these recipes updates
those item sprites and mappings.

Each herb has an independent fixed random seed. Regenerating the same catalog
with the same Blender version produces the same mesh, materials, and recipes;
Blender files themselves can differ in serialization metadata. Rebuilding
replaces generated files, including any manual edits to those files. Change the
catalog to preserve adjustments. Generation does not edit credits or remove
obsolete models when entries are deleted from the catalog.

## Catalog

The top-level `version` is `1`. `materials` maps names to linear RGB `color` and
optional `light` values, plus optional `roughness` and `subsurface` values.
Materials use procedural noise to vary between their two colors.

Each entry in `herbs` contains:

- `item`: visual item ID.
- `slug`: unique lowercase filename without an extension.
- `name`: readable name.
- `seed`: optional random seed; defaults to the item ID.
- `scale`, `direction`: sprite render settings, defaulting to `1` and `west`.
- `stem_thickness`: multiplier for main stems, flower spike stems, fern stems, and berry stalks; defaults to `1`. Current herbs use `1.82`. Roots, veins, and thistle bristles retain their own radii.
- `parts`: components assembled into the final `Herb` mesh.

Coordinates and dimensions are in Blender world units; Z points up. The current
herbs are generally 0.2–0.4 units tall. Materials are referenced by palette name.
The supplied palette includes the default `stem`, `leaf`, `vein`, `yellow`,
`gold`, `cream`, `red`, and `root` materials used by the primitives.

| Part | Required fields | Optional controls |
| --- | --- | --- |
| `stem` | `points` (at least two XYZ points), `radius` | `material`, `taper` (tip/start radius ratio) |
| `root` | `points`, `radius` | `material`, `taper`; combine paths for forks |
| `leaf` | `base`, `tip`, `width` | `shape`: `oval`, `lance`, `heart`, `lobed`; `normal`, `curl`, `serrated`, `veins`, `material`, `vein_material` |
| `flower` | `at`, `radius` | `shape`: `daisy`, `star`, `cup`, `bell`, `spike`, `thistle`; `normal`, `petals`, `depth`, `length`, `material`, `center_material` |
| `berries` | `at`, `radius` | `count`, `spread`, `junction`, `material`, `stem_material` |
| `fern` | `base`, `tip`, `width` | `pairs`, `radius`, `leaflet_width`, `serrated`, `material`, `stem_material` |

`normal` controls which way a leaf or flower faces. For flowers,
`[0, 0, 1]` faces up; tilting it toward the camera makes small flowers easier to
read. A bell is a flared, hollow cup; orient its normal downward for a hanging
bell. `depth` controls cup/bell length; `length` controls spike/thistle length.
`leaflet_width` is relative to the frond's local width.

For example, a white daisy on a curved green stalk:

```json
{
  "item": 144,
  "slug": "virgins_weed",
  "name": "Virgin's weed",
  "seed": 144,
  "scale": 1,
  "direction": "west",
  "parts": [
    {"type": "stem", "points": [[0, 0, 0], [0.02, 0, 0.14], [0, 0, 0.27]], "radius": 0.003},
    {"type": "flower", "at": [0, 0, 0.27], "radius": 0.05, "shape": "daisy", "petals": 13, "material": "white", "center_material": "gold"}
  ]
}
```
