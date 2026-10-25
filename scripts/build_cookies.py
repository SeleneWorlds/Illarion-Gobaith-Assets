"""Generate three golden cookies with scattered chocolate chips."""
import bpy,math,random,json
from pathlib import Path
rng=random.Random(453)
root=Path(__file__).resolve().parents[1]/'models/items/food/cookies';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
m=bpy.data.materials.new('Golden baked cookie');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=.86
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=9;noise.inputs['Detail'].default_value=4;r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.27,.105,.025,1);r.color_ramp.elements[1].color=(.76,.43,.13,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=85;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.3;b.inputs['Distance'].default_value=.002;l.new(fine.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
choc=bpy.data.materials.new('Dark chocolate chips');choc.use_nodes=True;p=choc.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.055,.018,.006,1);p.inputs['Roughness'].default_value=.62
names=[]
for j,(x,y,z) in enumerate([(-.075,-.035,0),(.075,-.015,.004),(.005,.065,.033)]):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=20,radius=1);o=bpy.context.object;o.name=f'Cookie_{j+1}';phase=rng.random()*6
 for v in o.data.vertices:
  a=math.atan2(v.co.y,v.co.x);w=1+.035*math.sin(a*7+phase)+.02*math.sin(a*11);v.co.x*=.105*w;v.co.y*=.10*w;v.co.z=max(.002,(v.co.z+1)*.015)
 o.location=(x,y,z);o.data.materials.append(m)
 for p in o.data.polygons:p.use_smooth=True
 names.append(o.name)
 for k in range(11):
  angle=k*2.39996+phase;rad=.083*math.sqrt((k+.5)/11);cx=rad*math.cos(angle);cy=rad*math.sin(angle);top=.015+.015*math.sqrt(max(0,1-(rad/.105)**2))
  bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=rng.uniform(.006,.009),location=(x+cx,y+cy,z+top-.001));chip=bpy.context.object;chip.name=f'Chip_{j}_{k}';chip.scale=(1,rng.uniform(.7,1.1),.55);chip.rotation_euler.z=rng.random()*6;chip.data.materials.append(choc);names.append(chip.name)
bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=bpy.data.objects['Cookie_1'];bpy.ops.object.join();bpy.context.object.name='Cookies'
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'cookies.blend'))
d=dict(model='cookies.blend',sprites='illarion/items/food/cookies/item_453',visual='items/item_453',direction='west',scale=1,include=['Cookies']);(root/'cookies.json').write_text(json.dumps(d,indent=2)+'\n')
