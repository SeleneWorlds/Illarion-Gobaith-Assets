"""Generate three ripe cherries joined at a common branching stem."""
import bpy,math,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'models/items/food/cherries';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
m=bpy.data.materials.new('Ripe red cherry skin');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.24;p.inputs['Coat Weight'].default_value=.35;p.inputs['Coat Roughness'].default_value=.18;p.inputs['Subsurface Weight'].default_value=.025
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3;r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.19,.002,.008,1);r.color_ramp.elements[1].color=(.65,.012,.025,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
stem=bpy.data.materials.new('Olive cherry stems');stem.use_nodes=True;p=stem.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.16,.20,.025,1);p.inputs['Roughness'].default_value=.78
names=[]
curve=bpy.data.curves.new('Joined cherry stems','CURVE');curve.dimensions='3D';curve.resolution_u=20;curve.bevel_depth=.004;curve.bevel_resolution=3
for j,(x,y,z) in enumerate([(-.078,-.025,.073),(.075,-.015,.075),(.006,.095,.078)]):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=32,radius=1);o=bpy.context.object;o.name=f'Cherry_{j+1}'
 for v in o.data.vertices:
  xx,yy,zz=v.co;rad=xx*xx+yy*yy;indent=.018*math.exp(-rad/.10) if zz>0 else 0
  v.co=(xx*.071*(1+.025*yy),yy*.067,zz*.071-indent)
 o.location=(x,y,z);o.data.materials.append(m)
 for p in o.data.polygons:p.use_smooth=True
 names.append(o.name)
 points=[(x,y,z+.052),(x*.85,y*.85,.20),(x*.35+.012,.035,.285),(0,.035,.32)]
 s=curve.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
 for p,co in zip(s.bezier_points,points):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
curve.materials.append(stem);o=bpy.data.objects.new('CherryStems',curve);bpy.context.collection.objects.link(o);names.append(o.name)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'cherries.blend'))
d=dict(model='cherries.blend',sprites='illarion/items/food/cherries/item_302',visual='items/item_302',direction='west',scale=1,include=names);(root/'cherries.json').write_text(json.dumps(d,indent=2)+'\n')
