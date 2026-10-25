# Reusable wood materials

Four 2048×2048 color textures share the grain, roughness, and OpenGL normal map
from [Wood 050 by CC0 Textures](https://cc0-textures.com/t/cc0t-wood-050), CC0.
Conifer is pale honey, cherry reddish brown, naldor dark brown, and apple golden
brown. The colors are art choices for readable item variants.

Append a `Wood_Conifer`, `Wood_Cherry`, `Wood_Naldor`, or `Wood_Apple` material
from `wood_materials.blend` into another model. These are marked as Blender
material assets. Keep image paths relative when saving the destination model.
The grain runs along UV U; use a UV map with U aligned to the wood's length.
Color textures use sRGB. `roughness.jpg` and `normal_gl.jpg` use Non-Color;
the latter connects through a Normal Map node. No displacement is required.

Regenerate colors from the included source (requires Pillow):

```sh
python3 scripts/generate_wood_textures.py
```

To replace the included 2K source maps from the original download:

```sh
python3 scripts/generate_wood_textures.py --source /path/to/Wood050_4K-JPG
```

Rebuild the material library and two-plank model, then render the board items:

```sh
blender -b --python scripts/build_wood_planks.py
python3 scripts/sprite_pipeline.py models/items/planks
```

The shared plank model uses material `PlankWood`. Each render config overrides
its `WoodColor` image node to select a wood type; shared roughness and normal
maps stay the same. Item mappings: conifer 2543, cherry 545, naldor 546, apple
2716. Two slightly offset beveled planks form the stack.
