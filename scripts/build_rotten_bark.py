"""Build a ragged bark strip using the shared conifer bark textures."""
import bpy,math,random,json
from pathlib import Path
rng=random.Random(157)
base=Path(__file__).resolve().parents[1];root=base/'models/items/plants/rotten_bark';root.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
rows,cols=24,6;verts=[];faces=[]
left=[rng.uniform(.80,1.14) for _ in range(rows+1)];right=[rng.uniform(.78,1.16) for _ in range(rows+1)]
for j in range(rows+1):
 t=j/rows;y=(t-.5)*.43;tip=.65+.35*math.sin(math.pi*t)**.4
 for k in range(cols+1):
  u=k/cols*2-1;edge=left[j] if u<0 else right[j];x=u*.065*tip*edge
  yy=y+(rng.uniform(-.014,.014) if j in (0,rows) else 0)
  z=.012+.020*u*u+.009*math.sin(t*math.pi*1.4)+rng.uniform(-.002,.002)
  verts.append((x,yy,z))
for j in range(rows):
 for k in range(cols):
  a=j*(cols+1)+k;faces.append((a,a+1,a+cols+2,a+cols+1))
mesh=bpy.data.meshes.new('Ragged bark strip');mesh.from_pydata(verts,[],faces);mesh.update();uv=mesh.uv_layers.new(name='BarkUV')
for p in mesh.polygons:
 p.use_smooth=True
 for idx in p.loop_indices:
  v=mesh.loops[idx].vertex_index;uv.data[idx].uv=((v%(cols+1))/cols,(v//(cols+1))/rows)
o=bpy.data.objects.new('RottenBark',mesh);bpy.context.collection.objects.link(o)
solid=o.modifiers.new('Bark thickness','SOLIDIFY');solid.thickness=.009
bevel=o.modifiers.new('Worn edges','BEVEL');bevel.width=.001;bevel.segments=2
m=bpy.data.materials.new('Weathered conifer bark');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
images={}
for name,file in [('Color','conifer_bark_color.jpg'),('Roughness','bark_roughness.jpg'),('Normal','bark_normal_gl.jpg')]:
 image=bpy.data.images.load(str(base/'models/materials/wood'/file),check_existing=True);image.pack()
 if name!='Color':image.colorspace_settings.name='Non-Color'
 tex=n.new('ShaderNodeTexImage');tex.name=name;tex.image=image;images[name]=tex
hue=n.new('ShaderNodeHueSaturation');hue.inputs['Saturation'].default_value=.7;hue.inputs['Value'].default_value=.65;l.new(images['Color'].outputs['Color'],hue.inputs['Color']);l.new(hue.outputs['Color'],p.inputs['Base Color'])
l.new(images['Roughness'].outputs['Color'],p.inputs['Roughness']);normal=n.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.7;l.new(images['Normal'].outputs['Color'],normal.inputs['Color']);l.new(normal.outputs[0],p.inputs['Normal']);mesh.materials.append(m)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'rotten_bark.blend'))
d=dict(model='rotten_bark.blend',sprites='illarion/items/plants/rotten_bark/item_157',visual='items/item_157',direction='west',scale=1.2,include=['RottenBark']);(root/'rotten_bark.json').write_text(json.dumps(d,indent=2)+'\n')
