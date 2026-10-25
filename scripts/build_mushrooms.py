"""Generate mushroom meshes and materials; run with Blender --background --python."""
import bpy
import math
import random
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'models/foliage/mushrooms'
rng = random.Random(740)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)

def material(name, dark, light, spots=False):
    m=bpy.data.materials.new(name); m.use_nodes=True
    n=m.node_tree.nodes; l=m.node_tree.links; p=n.get('Principled BSDF')
    p.inputs['Roughness'].default_value=.72
    noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=7; noise.inputs['Detail'].default_value=3
    ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(*dark,1); ramp.color_ramp.elements[1].color=(*light,1)
    l.new(noise.outputs['Fac'],ramp.inputs[0]); color=ramp.outputs['Color']
    if spots:
        v=n.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value=11
        r=n.new('ShaderNodeMath');r.operation='LESS_THAN';r.inputs[1].default_value=.19;l.new(v.outputs['Distance'],r.inputs[0])
        mix=n.new('ShaderNodeMixRGB');mix.inputs[2].default_value=(.88,.82,.63,1);l.new(r.outputs[0],mix.inputs[0]);l.new(color,mix.inputs[1]);color=mix.outputs[0]
    l.new(color,p.inputs['Base Color'])
    fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=85
    b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.16;b.inputs['Distance'].default_value=.002;l.new(fine.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
    return m
stem=material('Ivory fibrous stems',(.32,.27,.16),(.85,.79,.59))
gills=material('Pale gills',(.28,.23,.15),(.67,.57,.39))
colors={'green':((.05,.16,.008),(.42,.7,.035)), 'red':((.28,.009,.005),(.78,.055,.025)), 'ochre':((.22,.12,.015),(.58,.39,.05)), 'brown':((.13,.075,.03),(.56,.39,.20)), 'cream':((.39,.31,.20),(.88,.81,.64)), 'grey':((.09,.09,.07),(.38,.37,.29)), 'purple':((.20,.012,.30),(.66,.10,.8)), 'blue':((.005,.13,.28),(.025,.65,.8))}
mats={k:material(k+' cap',a,b,k in ('red','brown')) for k,(a,b) in colors.items()}
parts=[]
def mesh(name,verts,faces,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(mat);parts.append(o)
    for p in me.polygons:p.use_smooth=True
    return o

def tube(points,radius,mat):
    verts=[];faces=[]
    for j,pt in enumerate(points):
        tangent=Vector(points[min(j+1,len(points)-1)])-Vector(points[max(0,j-1)])
        q=tangent.to_track_quat('Z','Y')
        for i in range(10):
            a=2*math.pi*i/10;v=q@Vector((radius*(1-.5*j/len(points))*math.cos(a),radius*(1-.5*j/len(points))*math.sin(a),0));verts.append(Vector(pt)+v)
    for j in range(len(points)-1):
        for i in range(10):a=j*10+i;b=j*10+(i+1)%10;faces.append((a,b,b+10,a+10))
    faces += [tuple(reversed(range(10))),tuple(range((len(points)-1)*10,len(points)*10))]
    return mesh('Stem',verts,faces,mat)

def mushroom(x,y,h,r,color,shape='dome'):
    bend=.025*rng.uniform(-1,1);z=h*.65
    tube([(x,y,0),(x+bend,y+.008,z*.5),(x+bend,y,z)],r*.17,stem)
    profiles={'dome':[(0,h),(.28,h*.99),(.60,h*.92),(.86,h*.79),(1,z),(.82,z-.012),(0,z-.018)],'flat':[(0,h),(.45,h*.98),(.82,h*.93),(1,z),(.80,z-.012),(0,z-.02)],'inkcap':[(0,h),(.55,h*.99),(.88,h*.92),(1,h*.48),(.75,h*.43),(0,h*.43)],'bell':[(0,h),(.3,h*.98),(.55,h*.88),(.78,h*.64),(1,z),(.8,z-.01),(0,z-.02)]}
    if shape=='flat': z=h*.86
    profile=profiles.get(shape,profiles['dome']);verts=[];faces=[];N=48
    for k,(rad,zz) in enumerate(profile):
        for i in range(N):
            a=2*math.pi*i/N;rr=r*rad*(1+.025*math.sin(a*5+1)+.015*math.sin(a*9));verts.append((x+bend+rr*math.cos(a),y+rr*math.sin(a),zz+.003*rad*math.sin(a*5)))
    for k in range(len(profile)-1):
        for i in range(N):faces.append((k*N+i,k*N+(i+1)%N,(k+1)*N+(i+1)%N,(k+1)*N+i))
    o=mesh('Cap',verts,faces,mats[color]);o.data.materials.append(gills)
    for p in o.data.polygons:
        if p.index//N>=len(profile)-3:p.material_index=1
    # Radial ribs under the overhanging cap.
    for i in range(0 if shape=='inkcap' else 20):
        a=i*math.tau/20
        tube([(x+bend+r*.2*math.cos(a),y+r*.2*math.sin(a),z-.014),(x+bend+r*.88*math.cos(a),y+r*.88*math.sin(a),z-.008)],.0018,gills)

def bare(x,y,h):
    tube([(x,y,0),(x+.015,y,h*.5),(x+.035,y,h)],.018,stem)

def wall(color,multi=False,bare_only=False):
    # Curled lateral stems, with roots at the wall and outward-facing shelves.
    for j in range(4 if multi else 1):
        x=(j%2)*.13-.07;y=(j//2)*.09;z=j*.065
        tube([(x,.13,z),(x,-.015,z+.025),(x,-.11,z+.13)],.018,stem)
        for k in range(4):
            dx=rng.uniform(-.09,.09);tube([(x,.13,z),(x+dx,.15,z-.04),(x+dx*1.5,.16,z-.10)],.003,stem)
        if not bare_only:
            before=len(parts);mushroom(x,-.14,.11,.11 if multi else .16,color,'flat')
            for o in parts[before:]:o.location.z+=z+.07

def finish(item):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();parts[0].name=f'Mushroom_{item}';parts.clear()

ids=[158,159,160,161,162,163,*range(405,428),1790]
for item in ids:
    state=rng.getstate()
    if item<=163:
        color={158:'green',159:'red',160:'ochre',161:'brown',162:'grey',163:'cream'}[item]
        mushroom(0,0, .18 if item==163 else (.30 if item!=160 else .21), .085 if item==163 else (.14 if item not in (160,162) else .065), color, 'inkcap' if item==162 else ('bell' if item==160 else 'dome'))
    elif item==1790:
        for j in range(11):
            a=j*math.tau/11;mushroom(.34*math.cos(a),.34*math.sin(a),rng.uniform(.10,.16),rng.uniform(.045,.065),'brown')
    elif item in (405,420,421,422,426):
        color={405:'green',420:'purple',421:'green',422:'blue',426:'grey'}[item]
        for j,(x,y,h) in enumerate([(-.11,-.07,.19),(.10,0,.28),(-.06,.13,.22)]):
            if item==426:bare(x,y,h)
            else:mushroom(x,y,h,.10,(['blue','purple','green'][j] if item==405 else color))
    elif item in (406,407):
        for j,color in enumerate(['green','blue','purple']):mushroom((j-1)*.14,(j%2)*.10,.13,.13,color,'flat')
    else:
        color={408:'purple',409:'blue',410:'green',411:'green',412:'blue',413:'purple',414:'green',415:'blue',416:'purple',417:'green',418:'blue',419:'purple'}.get(item,'grey')
        wall(color,item in range(414,420) or item in (424,425),item>=423)
    finish(item)
    if item==163:rng.setstate(state)

DEST.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(DEST/'procedural_mushrooms.blend'))
# Replace existing render recipes, preserving their established sprite destinations/directions.
existing={}
for p in DEST.glob('*.json'):
    d=json.loads(p.read_text());existing[int(d['visual'].split('_')[-1])]=(p,d)
for item in ids:
    state=rng.getstate()
    if item in existing:p,d=existing[item]
    else:
        p=DEST/f'mushroom_{item}.json';d={'sprites':f'illarion/items/foliage/mushrooms/item_{item}','visual':f'items/item_{item}','direction':'south'}
    d.update(model='procedural_mushrooms.blend',include=[f'Mushroom_{item}'],scale=1)
    # Preserve wall attachment anchors rather than centering them on the tile.
    if 408<=item<=419 or item in (423,424,425,427):
        v=json.loads((ROOT/f'client/data/illarion/visuals/items/item_{item}.json').read_text())
        d.update(offsetX=v['offsetX'],offsetY=v['offsetY'])
    p.write_text(json.dumps(d,indent=2)+'\n')
