"""Rebake campfire.blend's fire cache: blender -b --python scripts/bake_campfire.py."""
from pathlib import Path

import bpy

path = Path(__file__).resolve().parent.parent / 'models/structures/campfire/campfire.blend'
bpy.ops.wm.open_mainfile(filepath=str(path))
domain = bpy.data.objects['Fire_Domain']
bpy.ops.object.select_all(action='DESELECT')
domain.select_set(True)
bpy.context.view_layer.objects.active = domain
settings = domain.modifiers['Fire Simulation'].domain_settings
if settings.has_cache_baked_data:
    bpy.ops.fluid.free_all()
bpy.context.scene.frame_set(settings.cache_frame_start)
bpy.ops.fluid.bake_all()
bpy.context.scene.frame_set(33)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
