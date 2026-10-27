"""Build renderable flame surfaces from baked Mantaflow torch grids.

Run with Blender after scripts/bake_fire.py; keeps the baked flame motion while
avoiding Eevee's rectangular volume rendering on this asset.
Pass -- --handheld to rebuild the portable torch with the same flame treatment.
"""
import gzip
from pathlib import Path
import struct
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models/furniture/wall_torch/wall_torch_lit.blend'


def surface(grid, level):
    # Split each voxel into six tetrahedra sharing the same cube diagonal.
    offsets = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)])
    cells = np.stack([grid[z:grid.shape[0]-1+z,
                           y:grid.shape[1]-1+y,
                           x:grid.shape[2]-1+x]
                      for z, y, x in offsets], axis=-1)
    active = (cells.min(axis=-1) < level) & (cells.max(axis=-1) >= level)
    origin = np.argwhere(active)
    positions = origin[:, None, :] + offsets[None, :, :]
    values = cells[active]
    triangles = []
    for tet in [(0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6),
                (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)]:
        points, scalars = positions[:, tet], values[:, tet]
        mask = ((scalars >= level) * np.array([1, 2, 4, 8])).sum(axis=1)
        for case in range(1, 15):
            selected = mask == case
            if not selected.any():
                continue
            inside = [i for i in range(4) if case & (1 << i)]
            outside = [i for i in range(4) if not case & (1 << i)]
            edges = [(a, b) for a in inside for b in outside]
            crossings = []
            for a, b in edges:
                t = (level-scalars[selected, a]) / (scalars[selected, b]-scalars[selected, a])
                crossings.append(points[selected, a] + t[:, None] *
                                 (points[selected, b]-points[selected, a]))
            if len(crossings) == 3:
                triangles.append(np.stack(crossings, axis=1))
            else:
                for indices in [(0, 1, 2), (1, 3, 2)]:
                    triangles.append(np.stack([crossings[i] for i in indices], axis=1))
    return np.concatenate(triangles).reshape(-1, 3)[:, ::-1]


def main():
    handheld = '--handheld' in sys.argv
    model = ROOT / 'models/items/lighting/torch/torch_lit.blend' if handheld else MODEL
    bpy.ops.wm.open_mainfile(filepath=str(model))
    for obj in list(bpy.data.objects):
        if obj.name.startswith('BakedFlame_'):
            bpy.data.objects.remove(obj, do_unlink=True)
    domain = bpy.data.objects['Fire_Domain']
    settings = domain.modifiers['Fire Simulation'].domain_settings
    cache = Path(bpy.path.abspath(settings.cache_directory)) / 'data'
    bounds = [domain.matrix_world @ Vector(c) for c in domain.bound_box]
    low = np.array([min(p[i] for p in bounds) for i in range(3)])
    size = np.array([max(p[i] for p in bounds) for i in range(3)]) - low
    materials = []
    for name, color, opacity, strength in [
        ('Flame orange', (1.0, .12, .003, 1), .35, 2),
        ('Flame yellow core', (1.0, .65, .07, 1), .85, 3),
    ]:
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = color
        emission.inputs['Strength'].default_value = strength
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = opacity
        output = nodes.new('ShaderNodeOutputMaterial')
        links = material.node_tree.links
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])
        if hasattr(material, 'surface_render_method'):
            material.surface_render_method = 'DITHERED'
        materials.append(material)
    for frame in range(33, 65):
        data = gzip.open(cache / f'flame_{frame:04d}.uni', 'rb').read()
        nx, ny, nz = struct.unpack_from('<3i', data, 4)
        grid = np.frombuffer(data, dtype='<f4', offset=292).reshape(nz, ny, nx)
        for layer, level in enumerate([.18, .65]):
            vertices = surface(grid, level)
            vertices = low + (vertices + .5) / np.array([nx, ny, nz]) * size
            # Keep the fire rooted at the wrapped head while shortening the plume.
            flame_base = .18 if handheld else 1.75
            vertices[:, 2] = flame_base + (vertices[:, 2] - flame_base) * .64
            mesh = bpy.data.meshes.new(f'Flame_{frame}_{layer}')
            mesh.from_pydata(vertices.tolist(), [],
                             np.arange(len(vertices)).reshape(-1, 3).tolist())
            mesh.update()
            obj = bpy.data.objects.new(f'BakedFlame_{frame}_{layer}', mesh)
            bpy.context.collection.objects.link(obj)
            mesh.materials.append(materials[layer])
            for polygon in mesh.polygons:
                polygon.use_smooth = True
            for key, hidden in [(1, True), (frame-1, True), (frame, False), (frame+1, True)]:
                obj.hide_render = hidden
                obj.keyframe_insert(data_path='hide_render', frame=key)
    # One root rotates every animation frame with the torch.
    root_name = 'HandheldTorchRoot' if handheld else 'WallTorchRoot'
    rig = bpy.data.objects.get(root_name)
    if rig is None:
        rig = bpy.data.objects.new(root_name, bpy.data.armatures.new(root_name))
        bpy.context.collection.objects.link(rig)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith('BakedFlame_') or obj.name == 'torch_2':
            world = obj.matrix_world.copy()
            obj.parent = rig
            obj.matrix_world = world
    domain.hide_render = True
    bpy.context.scene.frame_set(33)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(model), compress=True)


if __name__ == '__main__':
    main()
