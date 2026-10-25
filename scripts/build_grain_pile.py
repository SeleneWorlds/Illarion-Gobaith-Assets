"""Generate a mound of grooved wheat kernels with deterministic placement."""
import bpy,math,random,json
from pathlib import Path
from mathutils import Vector,Euler
rng=random.Random(259)
root=Path(__file__).resolve().parents[1]/'models/items/food/grains';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mats=[]
for name,color in [('Golden wheat',(.57,.33,.085,1)),('Pale wheat',(.75,.51,.18,1)),('Dark wheat',(.40,.21,.04,1))]:
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Roughness'].default_value=.8;mats.append(m)
verts=[];faces=[];slots=[]
# Kernels densely cover a rounded mound, with a few spilled around its foot.
for j in range(780):
 r=rng.random()**.5;a=rng.random()*math.tau
 if j>735:r=rng.uniform(1,1.22)
 x=.23*r*math.cos(a);y=.19*r*math.sin(a);z=.14*max(0,1-r*r)**1.2+.004
 length=rng.uniform(.023,.033);width=rng.uniform(.009,.012);height=width*.7
 rot=Euler((rng.uniform(-.2,.2),rng.uniform(-.4,.4),rng.random()*math.tau)).to_matrix();start=len(verts);mat=rng.choices([0,1,2],[6,3,1])[0]
 for k in range(9):
  t=math.pi*k/8;xx=length*.5*math.cos(t);rad=math.sin(t)
  for q in range(10):
   angle=q*math.tau/10;yy=width*.5*rad*math.cos(angle);zz=height*.5*rad*math.sin(angle)
   if zz>0:zz-=.0018*math.exp(-(yy/.0018)**2)*rad
   v=rot@Vector((xx,yy,zz));verts.append((x+v.x,y+v.y,z+v.z))
 for k in range(8):
  for q in range(10):faces.append((start+k*10+q,start+k*10+(q+1)%10,start+(k+1)*10+(q+1)%10,start+(k+1)*10+q));slots.append(mat)
mesh=bpy.data.meshes.new('Individual grooved kernels');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('GrainPile',mesh);bpy.context.collection.objects.link(o)
for m in mats:mesh.materials.append(m)
for p,slot in zip(mesh.polygons,slots):p.material_index=slot;p.use_smooth=True
# A compact core fills gaps between the surface kernels.
bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=(0,0,-.025));core=bpy.context.object;core.name='GrainCore';core.scale=(.215,.175,.155);core.data.materials.append(mats[0])
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for v in core.data.vertices:
 if v.co.z>0:
  radius=(v.co.x/.23)**2+(v.co.y/.19)**2
  v.co.z=max(0,.14*max(0,1-radius)**1.2-.012)
 else:v.co.z=0
for p in core.data.polygons:p.use_smooth=True
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'grains.blend'))
d=dict(model='grains.blend',sprites='illarion/items/food/grains/item_259',visual='items/item_259',direction='west',scale=.8,include=['GrainPile','GrainCore']);(root/'grains.json').write_text(json.dumps(d,indent=2)+'\n')
