"""Generate a softly kneaded dough blob with a procedural floury surface."""
import bpy,math,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'models/items/food/dough';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=40,radius=1)
o=bpy.context.object;o.name='Dough'
for v in o.data.vertices:
 x,y,z=v.co;a=math.atan2(y,x);w=1+.065*math.sin(a*3+.7)+.035*math.sin(a*5)
 v.co.x=x*.235*w+.018*z;v.co.y=y*.185*w
 v.co.z=max(.006,(z+1)*.095)+.008*math.sin(x*4+y*3)*max(0,z)
for f in o.data.polygons:f.use_smooth=True
m=bpy.data.materials.new('Soft floury dough');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.78;p.inputs['Subsurface Weight'].default_value=.06;p.inputs['Subsurface Radius'].default_value=(.4,.25,.12)
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5;noise.inputs['Detail'].default_value=3;r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.57,.43,.24,1);r.color_ramp.elements[1].color=(.89,.77,.54,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=120;fine.inputs['Detail'].default_value=2;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.12;b.inputs['Distance'].default_value=.001;l.new(fine.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal']);o.data.materials.append(m)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'dough.blend'))
d=dict(model='dough.blend',sprites='illarion/items/food/dough/item_5',visual='items/item_5',direction='west',scale=.85,include=['Dough']);(root/'dough.json').write_text(json.dumps(d,indent=2)+'\n')
