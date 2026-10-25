"""Generate six distinct small piles of seeds with deterministic layouts."""
import bpy,math,random,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'models/items/food/seeds';root.mkdir(parents=True,exist_ok=True)
# name, item, kernel dimensions, color, count, surface shape
variants=[('onion',534,(.022,.018,.017),(.34,.32,.29),34,'angular'),('tobacco',773,(.014,.010,.009),(.32,.18,.085),72,'round'),('carrot',2494,(.032,.013,.010),(.42,.26,.10),38,'ribbed'),('tomato',2917,(.035,.025,.006),(.79,.61,.28),25,'teardrop'),('sugarcane',779,(.050,.010,.009),(.65,.48,.22),28,'husk'),('hop',728,(.030,.026,.021),(.32,.09,.035),26,'round')]
for name,item,size,color,count,shape in variants:
 rng=random.Random(item);bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);mats=[]
 for j,factor in enumerate([.72,1,1.23]):
  m=bpy.data.materials.new(name+f' seed {j}');m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=tuple(min(1,c*factor) for c in color)+(1,);p.inputs['Roughness'].default_value=.85
  noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=35;b=m.node_tree.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.18;b.inputs['Distance'].default_value=.0005;m.node_tree.links.new(noise.outputs['Fac'],b.inputs['Height']);m.node_tree.links.new(b.outputs[0],p.inputs['Normal']);mats.append(m)
 seeds=[]
 for j in range(count):
  a=j*2.399963+rng.uniform(-.2,.2);r=math.sqrt((j+.5)/count);x=.105*r*math.cos(a);y=.078*r*math.sin(a);z=.022*max(0,1-r*r)
  if shape=='angular':bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1)
  else:bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=10,radius=1)
  o=bpy.context.object;o.name='Seed'
  for v in o.data.vertices:
   if shape=='teardrop':v.co.y*=.65+.35*(v.co.x+1)/2
   if shape in ('ribbed','husk'):
    angle=math.atan2(v.co.z,v.co.y);factor=1+.13*math.cos(angle*7);v.co.y*=factor;v.co.z*=factor
   if shape=='angular':v.co*=rng.uniform(.8,1.15)
  scale=rng.uniform(.85,1.15);o.scale=tuple(d*.5*scale for d in size);o.location=(x,y,z+size[2]*.5);o.rotation_euler=(rng.uniform(-.25,.25),rng.uniform(-.2,.2),rng.random()*math.tau);o.data.materials.append(rng.choices(mats,[2,6,2])[0])
  for p in o.data.polygons:p.use_smooth=shape!='angular'
  seeds.append(o)
 bpy.ops.object.select_all(action='DESELECT')
 for o in seeds:o.select_set(True)
 bpy.context.view_layer.objects.active=seeds[0];bpy.ops.object.join();seeds[0].name='SeedPile'
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/(name+'_seeds.blend')))
 d=dict(model=name+'_seeds.blend',sprites=f'illarion/items/food/seeds/item_{item}',visual=f'items/item_{item}',direction='west',scale=1.4,include=['SeedPile']);(root/(name+'_seeds.json')).write_text(json.dumps(d,indent=2)+'\n')
