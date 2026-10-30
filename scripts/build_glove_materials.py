"""Set up cloth/leather glove materials; run with Blender --python."""
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'models/items/clothing/gloves'
bpy.ops.wm.open_mainfile(filepath=str(FOLDER / 'gloves.blend'))


def swatch(name, color):
    image = bpy.data.images.new(name, width=1, height=1)
    image.pixels[:] = color
    image.filepath_raw = str(FOLDER / (name + '.png'))
    image.file_format = 'PNG'
    image.save()
    return image


light = swatch('cloth_light_gray', (0.65, 0.65, 0.65, 1))
swatch('cloth_dark_gray', (0.30, 0.30, 0.30, 1))
swatch('leather_brown', (0.40, 0.19, 0.08, 1))
cloth = swatch('surface_cloth', (1, 1, 1, 1))
swatch('surface_leather', (0, 0, 0, 1))
nonmetal = swatch('nonmetal', (0, 0, 0, 1))
swatch('metal', (1, 1, 1, 1))
swatch('steel', (0.65, 0.68, 0.72, 1))
swatch('iron', (0.55, 0.55, 0.55, 1))
swatch('gold', (0.83, 0.63, 0.18, 1))

material = bpy.data.materials.get('Hand') or bpy.data.materials.get('GloveSurface') or bpy.data.materials.new('Hand')
material.name = 'Hand'
material.use_nodes = True
nodes, links = material.node_tree.nodes, material.node_tree.links
nodes.clear()
output = nodes.new('ShaderNodeOutputMaterial')
shader = nodes.new('ShaderNodeBsdfPrincipled')
links.new(shader.outputs['BSDF'], output.inputs['Surface'])
dye = nodes.new('ShaderNodeTexImage')
dye.name = 'Dye'
dye.image = light
links.new(dye.outputs['Color'], shader.inputs['Base Color'])
surface = nodes.new('ShaderNodeTexImage')
surface.name = 'Surface'
surface.image = cloth
coordinates = nodes.new('ShaderNodeTexCoord')
grain = nodes.new('ShaderNodeTexNoise')
grain.inputs['Scale'].default_value = 150
grain.inputs['Detail'].default_value = 3
links.new(coordinates.outputs['Generated'], grain.inputs['Vector'])
waves = []
for axis in ['X', 'Y']:
    wave = nodes.new('ShaderNodeTexWave')
    wave.bands_direction = axis
    wave.inputs['Scale'].default_value = 100
    links.new(coordinates.outputs['UV'], wave.inputs['Vector'])
    waves.append(wave)
weave = nodes.new('ShaderNodeMath')
weave.operation = 'MULTIPLY'
for index, wave in enumerate(waves):
    links.new(wave.outputs['Fac'], weave.inputs[index])
texture = nodes.new('ShaderNodeMixRGB')
links.new(surface.outputs['Color'], texture.inputs[0])
links.new(grain.outputs['Fac'], texture.inputs[1])
links.new(weave.outputs[0], texture.inputs[2])
bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.22
bump.inputs['Distance'].default_value = 0.001
links.new(texture.outputs[0], bump.inputs['Height'])
links.new(bump.outputs['Normal'], shader.inputs['Normal'])
roughness = nodes.new('ShaderNodeMapRange')
roughness.inputs['To Min'].default_value = 0.5
roughness.inputs['To Max'].default_value = 0.85
links.new(surface.outputs['Color'], roughness.inputs['Value'])
metal = nodes.new('ShaderNodeTexImage')
metal.name = 'Metal'
metal.image = nonmetal
links.new(metal.outputs['Color'], shader.inputs['Metallic'])
finish = nodes.new('ShaderNodeMixRGB')
finish.inputs[2].default_value = (0.28, 0.28, 0.28, 1)
links.new(metal.outputs['Color'], finish.inputs[0])
links.new(roughness.outputs['Result'], finish.inputs[1])
links.new(finish.outputs[0], shader.inputs['Roughness'])
relief = nodes.new('ShaderNodeMapRange')
relief.inputs['To Min'].default_value = 0.22
relief.inputs['To Max'].default_value = 0
links.new(metal.outputs['Color'], relief.inputs['Value'])
links.new(relief.outputs['Result'], bump.inputs['Strength'])
sheen = nodes.new('ShaderNodeMath')
sheen.operation = 'MULTIPLY'
sheen.inputs[1].default_value = 0.12
links.new(surface.outputs['Color'], sheen.inputs[0])
links.new(sheen.outputs[0], shader.inputs['Sheen Weight'])

obj = bpy.data.objects['Gloves']
# Preserve separate slots and face assignments for future armored variants.
if not obj.data.materials:
    obj.data.materials.append(material)
for name in ['Fingers', 'Knuckles']:
    old = bpy.data.materials.get(name)
    replacement = material.copy()
    if old:
        old.user_remap(replacement)
        bpy.data.materials.remove(old)
    replacement.name = name
bpy.context.preferences.filepaths.save_version = 0
for image in bpy.data.images:
    if image.source == 'FILE':
        image.filepath = bpy.path.relpath(bpy.path.abspath(image.filepath))
bpy.ops.wm.save_as_mainfile(filepath=str(FOLDER / 'gloves.blend'))
