"""Create a bright steel variant of the metal greaves; run with Blender --python."""
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'models/items/armor/metal_greaves/metal_greaves.blend'
OUTPUT = ROOT / 'models/items/armor/steel_greaves/steel_greaves.blend'

bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
for name, color in [('Metal', 0.65), ('LightMetal', 0.8)]:
    material = bpy.data.materials[name]
    material.name = 'Steel' if name == 'Metal' else 'LightSteel'
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (color, color, color, 1)
    shader.inputs['Metallic'].default_value = 0.92
    shader.inputs['Roughness'].default_value = 0.32

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), relative_remap=True)
