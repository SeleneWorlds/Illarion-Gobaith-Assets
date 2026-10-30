"""Create wooden greaves from the metal source; run with Blender --python."""
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'models/items/armor/metal_greaves/metal_greaves.blend'
OUTPUT = ROOT / 'models/items/armor/wood_greaves/wood_greaves.blend'
WOOD = ROOT / 'models/materials/wood'

bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
with bpy.data.libraries.load(str(WOOD / 'wood_materials.blend'), link=False) as (_, imported):
    imported.materials = ['Wood_Conifer']
material = imported.materials[0]
for node in material.node_tree.nodes:
    if node.type == 'TEX_IMAGE' and node.image:
        node.image.filepath = str(WOOD / Path(node.image.filepath).name)

for obj in bpy.data.objects:
    if obj.type != 'MESH' or obj.name == 'Plane':
        continue
    for index in range(len(obj.data.materials)):
        obj.data.materials[index] = material
    # Project along the flat armor panels, with grain following each leg.
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index]
            co = obj.matrix_world @ vertex.co
            uv.data[loop_index].uv = (co.y * 2.0 + 0.5, co.x * 2.0 + 0.5)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), relative_remap=True)
for image in bpy.data.images:
    if image.source == 'FILE':
        image.filepath = bpy.path.relpath(bpy.path.abspath(image.filepath))
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
