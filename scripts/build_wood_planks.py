"""Run with blender -b --python scripts/build_wood_planks.py to rebuild wood assets."""
import math
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
WOOD = ROOT / 'models/materials/wood'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0


def wood_material(name):
    mat = bpy.data.materials.new('Wood_' + name.title())
    mat.use_nodes = True
    mat.use_fake_user = True
    mat.asset_mark()
    mat.asset_data.description = f'{name.title()} wood, recolored CC0 Textures Wood 050; grain runs along UV U'
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.location = (120, 0)
    shader.inputs['Roughness'].default_value = 0.65
    for node_name, file, y, noncolor in [('WoodColor', f'{name}_color.jpg', 260, False), ('WoodRoughness', 'roughness.jpg', 0, True), ('WoodNormal', 'normal_gl.jpg', -260, True)]:
        node = nodes.new('ShaderNodeTexImage'); node.name = node_name; node.label = node_name
        node.location = (-500, y)
        node.image = bpy.data.images.load(str(WOOD / file), check_existing=True)
        if noncolor: node.image.colorspace_settings.name = 'Non-Color'
        if node_name == 'WoodColor': links.new(node.outputs['Color'], shader.inputs['Base Color'])
        elif node_name == 'WoodRoughness': links.new(node.outputs['Color'], shader.inputs['Roughness'])
        else:
            normal = nodes.new('ShaderNodeNormalMap'); normal.location = (-130, -220)
            normal.inputs['Strength'].default_value = 0.22
            links.new(node.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    return mat

materials = {name: wood_material(name) for name in ('conifer', 'cherry', 'naldor', 'apple')}
bpy.ops.wm.save_as_mainfile(filepath=str(WOOD / 'wood_materials.blend'), relative_remap=True)
# One shared material slot permits the existing sprite pipeline's image overrides.
material = materials['conifer']
material.name = 'PlankWood'
for index, (location, angle) in enumerate([((-0.035, -0.045, 0.045), 0), ((0.035, 0.035, 0.138), math.radians(4))]):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object; obj.name = f'Plank_{index + 1}'
    obj.dimensions = (0.95, 0.28, 0.085)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Face-aligned UVs keep the long grain running down each board. Offset the
    # top plank's grain to avoid an identical repeated knot pattern.
    uv = obj.data.uv_layers.active
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            if abs(polygon.normal.z) > 0.5: u, v = co.x, co.y
            elif abs(polygon.normal.y) > 0.5: u, v = co.x, co.z
            else: u, v = co.y * 0.35, co.z  # Compressed grain on the cut ends.
            uv.data[loop_index].uv = (u * 0.85 + 0.5, v * 0.85 + 0.3 + index * 0.4)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new('Soft sawn edges', 'BEVEL'); bevel.width = 0.006; bevel.segments = 2
    obj.rotation_euler.z = angle
for mat in list(bpy.data.materials):
    if mat != material: bpy.data.materials.remove(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'models/items/planks/planks.blend'), relative_remap=True)
# Save relative image paths explicitly for portable library and model files.
for image in bpy.data.images:
    if image.source == 'FILE': image.filepath = bpy.path.relpath(image.filepath)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
