"""Build sand, coarse sand and ash piles with procedural materials in Blender."""
import bpy
import math
import random
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'models/items/materials/piles'
DEST.mkdir(parents=True,exist_ok=True)

def surface(r,a):
    edge=1+.065*math.sin(5*a)+.035*math.sin(9*a+1)
    x=.27*r*edge*math.cos(a);y=.23*r*edge*math.sin(a)
    z=.205*max(0,1-r)**1.15*(1+.10*math.sin(3*a)*r)+.008*math.sin(a*7+r*18)*r*(1-r)
    return x,y,z

for name,item,dark,light,grain in [
    ('sand',316,(.36,.24,.09),(.83,.65,.33),180),
    ('coarse_sand',726,(.025,.012,.005),(.18,.085,.03),65),
    ('ash',314,(.075,.07,.065),(.40,.38,.34),110)]:
    rng=random.Random(item)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Roughness'].default_value=1
    noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=grain;noise.inputs['Detail'].default_value=3
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(*dark,1);ramp.color_ramp.elements[1].color=(*light,1)
    l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.4;bump.inputs['Distance'].default_value=.002 if name=='sand' else .005;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],p.inputs['Normal'])
    N=64;R=18;verts=[(0,0,.205)];faces=[]
    for j in range(1,R+1):
        for i in range(N):verts.append(surface(j/R,i*math.tau/N))
    for i in range(N):faces.append((0,1+i,1+(i+1)%N))
    for j in range(R-1):
        for i in range(N):
            a=1+j*N+i;b=1+j*N+(i+1)%N;faces.append((a,a+N,b+N,b))
    faces.append(tuple(reversed([1+(R-1)*N+i for i in range(N)])))
    mesh=bpy.data.meshes.new(name+' pile');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Pile',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(m)
    for f in mesh.polygons:f.use_smooth=True
    debris_material=m
    if name=='coarse_sand':
        debris_material=m.copy();debris_material.name='Green plant debris'
        debris_ramp=next(node for node in debris_material.node_tree.nodes if node.type=='VALTORGB')
        debris_ramp.color_ramp.elements[0].color=(.018,.05,.005,1)
        debris_ramp.color_ramp.elements[1].color=(.17,.32,.035,1)
    pieces=[]
    for j in range(160 if name=='coarse_sand' else (65 if name=='ash' else 35)):
        r=rng.random()**.5;a=rng.random()*math.tau;x,y,z=surface(r,a)
        size=rng.uniform(.004,.010) if name=='coarse_sand' else rng.uniform(.002,.005)
        if j%6==0:
            r=rng.uniform(1.02,1.18);x,y,_=surface(r,a);z=0
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=size,location=(x,y,z+size*.25));t=bpy.context.object;t.scale=(1,rng.uniform(.7,1.3),.25 if name=='ash' else .65);t.rotation_euler=(rng.random(),rng.random(),rng.random()*6);t.data.materials.append(debris_material);pieces.append(t)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True)
    for t in pieces:t.select_set(True)
    bpy.context.view_layer.objects.active=o;bpy.ops.object.join();o.name='Pile'
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(DEST/(name+'.blend')))
    d=dict(model=name+'.blend',sprites=f'illarion/items/materials/piles/item_{item}',visual=f'items/item_{item}',direction='west',scale=.8,include=['Pile'])
    (DEST/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
