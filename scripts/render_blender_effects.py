#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Render particle scenes: blender -b -t 4 --python scripts/render_blender_effects.py.

Preserves source .blend files. Fits one orthographic camera to the complete
simulation, samples game frame counts, and writes transparent effect sprites.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
EFFECTS = {'stars': ('swirlie', 41, (154, 153), 41),
           'rain': ('green_sparkle_rain', 16, (144, 236), 32),
           'blood': ('blood', 13, (66, 58), 32),
           'demfire': ('blood', 5, (160, 223), 32)}


PROMINENCE = {"stars": (1.0, 1.0), "rain": (3.0, 1.5), "blood": (2.5, 1.2), "demfire": (2.5, 1.2)}

def render(name, source, gfx, size, end):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'particles' / (source + '.blend')))
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 24
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    scene.use_nodes = False
    scene.world.color = (0.15, 0.15, 0.15)
    emitter = bpy.data.objects['Emitter']
    emitter.show_instancer_for_render = False
    source_sprite = bpy.data.objects['Particle']
    source_sprite.hide_render = True
    emitter.hide_render = True
    size_multiplier, count_multiplier = PROMINENCE[name]
    if name in ("blood", "demfire"):
        # Blood and its green variant share particle settings and material brightness.
        for material in source_sprite.data.materials:
            if material and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        if name == "demfire":
                            # Replace the linked material tint with the selected color.
                            for link in list(node.inputs["Base Color"].links):
                                material.node_tree.links.remove(link)
                        node.inputs["Base Color"].default_value = ((0.006, 0.38, 0.012, 1)
                            if name == "demfire" else (0.38, 0.006, 0.012, 1))
                        node.inputs["Emission Color"].default_value = ((0.002, 0.35, 0.004, 1)
                            if name == "demfire" else (0.35, 0.002, 0.004, 1))
                        node.inputs["Emission Strength"].default_value = 0.1
    rendered_particles = []
    for obj in scene.objects:
        if obj.name == 'Plane':
            obj.hide_render = True
    for system in emitter.particle_systems:
        system.settings.count = round(system.settings.count * count_multiplier)
        system.seed = 0
        system.point_cache.frame_end = end
    # Sequential evaluation warms the simulation; bounds include all live particles.
    positions = []
    for frame in range(1, end + 1):
        scene.frame_set(frame)
        evaluated = emitter.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for system in evaluated.particle_systems:
            positions.extend(tuple(p.location) for p in system.particles if p.alive_state == 'ALIVE')
    ymin, ymax = min(p[1] for p in positions), max(p[1] for p in positions)
    zmin, zmax = min(p[2] for p in positions), max(p[2] for p in positions)
    camera_data = bpy.data.cameras.new('EffectCamera')
    camera = bpy.data.objects.new('EffectCamera', camera_data)
    scene.collection.objects.link(camera)
    target = Vector((0, (ymin + ymax) / 2, (zmin + zmax) / 2))
    camera.location = target + Vector((10, 0, 0))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    # Ortho scale spans the longer image dimension.
    span_y, span_z = ymax - ymin + 0.3, zmax - zmin + 0.3
    aspect = size[0] / size[1]
    camera_data.ortho_scale = max(span_y / min(1, aspect),
                                       span_z * max(1, aspect)) * 1.12
    scene.camera = camera
    light_data = bpy.data.lights.new('EffectLight', 'AREA')
    light_data.energy = 400
    light_data.shape = 'DISK'
    light_data.size = 5
    light = bpy.data.objects.new('EffectLight', light_data)
    scene.collection.objects.link(light)
    light.location = target + Vector((4, -3, 5))
    light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    visual = json.loads((ROOT / f'client/data/illarion/visuals/gfx/gfx_{gfx}.json').read_text())
    samples = [round(1 + i * (end - 1) / (len(visual['textures']) - 1)) for i in range(len(visual['textures']))]
    # Replay from frame one after fitting the camera.
    index = 0
    for frame in range(1, end + 1):
        scene.frame_set(frame)
        if index < len(samples) and frame == samples[index]:
            # Materialize evaluated particles: legacy instancing differs across Blender versions.
            for obj in rendered_particles:
                bpy.data.objects.remove(obj, do_unlink=True)
            rendered_particles.clear()
            evaluated = emitter.evaluated_get(bpy.context.evaluated_depsgraph_get())
            for system in evaluated.particle_systems:
                for particle in system.particles:
                    if particle.alive_state != 'ALIVE':
                        continue
                    obj = source_sprite.copy()
                    obj.hide_render = False
                    obj.location = particle.location
                    obj.scale = source_sprite.scale * particle.size * size_multiplier
                    scene.collection.objects.link(obj)
                    rendered_particles.append(obj)
            path = ROOT / visual['textures'][index]
            path.parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            index += 1
    metadata = {'source': f'particles/{source}.blend', 'gfx': gfx,
                'size': size, 'duration': visual['duration'], 'simulation_frames': samples,
                'camera_center': list(target), 'ortho_scale': camera_data.ortho_scale,
                'engine': 'CYCLES', 'samples': scene.cycles.samples,
                'particle_size_multiplier': size_multiplier,
                'particle_count_multiplier': count_multiplier,
                'blender': bpy.app.version_string}
    directory = ROOT / 'particles' / f'{name}-preview'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'render_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else EFFECTS
    for name in names:
        render(name, *EFFECTS[name])
