"""Generate an irregular beeswax honeycomb piece with open hexagonal cells."""
import bpy,math,random,json
from pathlib import Path
rng=random.Random(2529)
root=Path(__file__).resolve().parents[1]/'models/items/food/honeycomb';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def material(name,color,rough,sss):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Subsurface Weight'].default_value=sss;return m
wax=material('Golden beeswax',(.78,.42,.055),.48,.04)
honey=material('Amber honey inside cells',(.32,.115,.008),.24,.02)
verts=[];faces=[];slots=[];r=.045
for q in range(-2,3):
 for t in range(-2,3):
  if abs(q+t)>2 or (q,t) in [(-2,2),(2,0)]:continue
  x=r*1.5*q;y=r*math.sqrt(3)*(t+q/2);z=rng.uniform(.037,.052);start=len(verts)
  for radius,height in [(r,0),(r,z),(r-.005,z-.001),(r-.005,.006)]:
   for i in range(6):
    a=i*math.tau/6;verts.append((x+radius*math.cos(a),y+radius*math.sin(a),height))
  for i in range(6):
   j=(i+1)%6
   for f in [(start+i,start+j,start+6+j,start+6+i),(start+6+i,start+6+j,start+12+j,start+12+i),(start+12+i,start+12+j,start+18+j,start+18+i)]:faces.append(f);slots.append(0)
  faces.append(tuple(start+18+i for i in range(6)));slots.append(1)
  faces.append(tuple(start+i for i in reversed(range(6))));slots.append(0)
mesh=bpy.data.meshes.new('Open hexagonal wax cells');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Honeycomb',mesh);bpy.context.collection.objects.link(o);mesh.materials.append(wax);mesh.materials.append(honey)
for p,s in zip(mesh.polygons,slots):p.material_index=s
bevel=o.modifiers.new('Soft wax rims','BEVEL');bevel.width=.001;bevel.segments=2;o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');o.rotation_euler.z=.18
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'honeycomb.blend'))
d=dict(model='honeycomb.blend',sprites='illarion/items/food/honeycomb/item_2529',visual='items/item_2529',direction='west',scale=1,include=['Honeycomb']);(root/'honeycomb.json').write_text(json.dumps(d,indent=2)+'\n')
