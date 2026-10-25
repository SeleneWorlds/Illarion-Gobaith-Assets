"""Generate red berries, blueberries and purple grapes attached to branching stems."""
import bpy,math,random,json,sys
from pathlib import Path
base=Path(__file__).resolve().parents[1]/'models/items/food'
targets=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
for name,item in [('berries',81),('grapes',388),('blueberries',753)]:
 if targets and name not in targets:continue
 rng=random.Random(item);root=base/name;root.mkdir(parents=True,exist_ok=True);bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 m=bpy.data.materials.new(name+' skin');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.55 if name=='blueberries' else (.32 if name=='berries' else .43);p.inputs['Coat Weight'].default_value=.18;p.inputs['Subsurface Weight'].default_value=.025
 noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=4;r=n.new('ShaderNodeValToRGB')
 colors=[(.25,.004,.009,1),(.66,.025,.035,1)] if name=='berries' else ([ (.025,.065,.18,1),(.12,.28,.58,1)] if name=='blueberries' else [(.10,.012,.19,1),(.34,.075,.44,1)])
 for e,c in zip(r.color_ramp.elements,colors):e.color=c
 l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
 sm=bpy.data.materials.new('Branching green stems');sm.use_nodes=True;p=sm.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.14,.20,.035,1);p.inputs['Roughness'].default_value=.8
 curve=bpy.data.curves.new('Connected stems','CURVE');curve.dimensions='3D';curve.resolution_u=12;curve.bevel_depth=.0035;curve.bevel_resolution=2
 def branch(points):
  s=curve.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
  for b,co in zip(s.bezier_points,points):b.co=co;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 branch([(0,0,.035),(.006,0,.20),(-.01,0,.32),(.025,0,.37)])
 positions=[]
 if name=='grapes':
  for j,count in enumerate([1,4,6,7,5]):
   radius=[0,.037,.064,.075,.055][j]
   for k in range(count):
    a=k*math.tau/count+j*.65;positions.append((radius*math.cos(a),radius*math.sin(a),.055+j*.046,.037*rng.uniform(.94,1.06)))
 else:
  for j in range(5):
   for side in [-1,1]:positions.append((side*(.07+.012*math.sin(j)),rng.uniform(-.035,.035),.065+j*.045,.030*rng.uniform(.85,1.05)))
 names=[]
 for j,(x,y,z,rad) in enumerate(positions):
  bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=rad,location=(x,y,z));o=bpy.context.object;o.name=f'{name}_{j+1}';o.scale.z=1.12 if name=='grapes' else 1;o.data.materials.append(m)
  for f in o.data.polygons:f.use_smooth=True
  names.append(o.name);branch([(0,0,z+.03),(x*.5,y*.5,z+.035),(x,y,z+rad*.7)])
 curve.materials.append(sm);o=bpy.data.objects.new('Stems',curve);bpy.context.collection.objects.link(o);names.append(o.name)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/(name+'.blend')))
 d=dict(model=name+'.blend',sprites=f'illarion/items/food/{name}/item_{item}',visual=f'items/item_{item}',direction='west',scale=1.2,include=names);(root/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
