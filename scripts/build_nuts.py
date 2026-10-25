"""Generate a small pile of ridged walnuts in their shells."""
import bpy,math,random,json
from pathlib import Path
rng=random.Random(759)
root=Path(__file__).resolve().parents[1]/'models/items/food/nuts';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
m=bpy.data.materials.new('Ridged walnut shell');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.9
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=9;noise.inputs['Detail'].default_value=4;r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.16,.065,.018,1);r.color_ramp.elements[1].color=(.56,.31,.10,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
v=n.new('ShaderNodeTexVoronoi');v.feature='DISTANCE_TO_EDGE';v.inputs['Scale'].default_value=16;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.6;b.inputs['Distance'].default_value=.004;l.new(v.outputs['Distance'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
names=[]
for j,(x,y,z,rot) in enumerate([(-.075,-.035,.065,(.3,.6,-.4)),(.075,-.025,.061,(.5,-.3,.8)),(-.045,.095,.063,(-.4,.2,.4)),(.04,.055,.125,(.8,.4,-.6))]):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=40,radius=1);o=bpy.context.object;o.name=f'Walnut_{j+1}'
 for vertex in o.data.vertices:
  xx,yy,zz=vertex.co;a=math.atan2(yy,xx);t=math.acos(max(-1,min(1,zz)))
  ridge=1+.045*math.sin(12*a+2*math.sin(t*5))+.018*math.sin(a*21-t*11)
  # A recessed shell seam runs from pole to pole between the two halves.
  seam=.04*math.exp(-(yy/.045)**2)
  vertex.co=(xx*.061*(ridge-seam),yy*.057*ridge,zz*.076*ridge)
 o.location=(x,y,z);o.rotation_euler=rot;o.data.materials.append(m)
 for f in o.data.polygons:f.use_smooth=True
 names.append(o.name)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'nuts.blend'))
d=dict(model='nuts.blend',sprites='illarion/items/food/nuts/item_759',visual='items/item_759',direction='west',scale=1,include=names);(root/'nuts.json').write_text(json.dumps(d,indent=2)+'\n')
