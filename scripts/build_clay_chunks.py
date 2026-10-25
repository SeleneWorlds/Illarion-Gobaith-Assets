"""Generate the clay item model with irregular, softly rounded chunks."""
import bpy
import random
import json
from pathlib import Path
from mathutils import Vector
rng=random.Random(26)
root=Path(__file__).resolve().parents[1]/'models/items/materials/clay'
root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
m=bpy.data.materials.new('Damp raw clay');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.64
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=8;noise.inputs['Detail'].default_value=3
r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.17,.095,.045,1);r.color_ramp.elements[1].color=(.39,.25,.13,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=65;fine.inputs['Detail'].default_value=3;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.22;b.inputs['Distance'].default_value=.003;l.new(fine.outputs['Fac'],b.inputs['Height']);l.new(b.outputs['Normal'],p.inputs['Normal'])
names=[]
for i,(pos,scale) in enumerate([((-.11,-.07,0),(.14,.10,.085)),((.10,-.06,0),(.13,.11,.075)),((-.08,.11,0),(.11,.10,.10)),((.10,.12,0),(.10,.085,.09)),((.005,.025,.10),(.115,.09,.065))]):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=pos);o=bpy.context.object;o.name=f'ClayChunk_{i+1}'
 for v in o.data.vertices:
  v.co*=rng.uniform(.83,1.12)
  # Broad cut faces and dents distinguish chunks from smooth pebbles.
  v.co.z=min(v.co.z,.72)
 o.scale=scale;o.rotation_euler=(rng.uniform(-.4,.4),rng.uniform(-.4,.4),rng.uniform(0,6.28));o.data.materials.append(m)
 for f in o.data.polygons:f.use_smooth=True
 bpy.context.view_layer.update()
 if i<4:o.location.z-=min((o.matrix_world@Vector(v)).z for v in o.bound_box)
 bevel=o.modifiers.new('Soft clay edges','BEVEL');bevel.width=.08;bevel.segments=2
 names.append(o.name)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'clay.blend'))
d=dict(model='clay.blend',sprites='illarion/items/materials/clay/item_26',visual='items/item_26',direction='west',scale=.8,include=names)
(root/'clay.json').write_text(json.dumps(d,indent=2)+'\n')
