"""Bake a fire model: blender -b --python scripts/bake_fire.py -- path/to/model.blend."""
import argparse
from pathlib import Path
import sys

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    path = args.model.resolve()
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
    bpy.context.scene.frame_set(min(settings.cache_frame_end, settings.cache_frame_start + 32))
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)


if __name__ == '__main__':
    main()
