"""Build a hops sprig with layered cone bracts for item 154.

Run with: blender -b --python scripts/build_hops.py
"""
from pathlib import Path
import json
import math
import random

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'models/items/plants/hops'
OUTPUT.mkdir(parents=True, exist_ok=True)
RNG = random.Random(154)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
root = bpy.data.objects.new('Hops', None)
bpy.context.collection.objects.link(root)


def material(name, dark, light):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .78
    shader.inputs['Subsurface Weight'].default_value = .025
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 18
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    links.new(ramp.outputs[0], shader.inputs['Base Color'])
    return mat


bracts = [material('Hop bracts '+str(i), (.20+.025*i, .34+.035*i, .025),
                   (.48+.035*i, .70+.035*i, .10)) for i in range(4)]
leaf_mat = material('Hop leaves', (.055, .22, .015), (.19, .53, .045))
stem_mat = material('Hop stems and veins', (.15, .25, .025), (.34, .48, .075))
core_mat = material('Hop cone core', (.10, .18, .012), (.23, .34, .025))


def mesh(name, vertices, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = root
    obj.data.materials.append(mat)
    return obj


def stem(name, points, radius=.003):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = 'AUTO'
        point.handle_right_type = 'AUTO'
    curve.materials.append(stem_mat)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.parent = root


def cone(name, top, direction, length, radius):
    top = Vector(top)
    rotation = Vector(direction).normalized().to_track_quat('Z', 'Y')
    def world(v):
        return top + rotation @ Vector(v)
    def profile(t):
        return radius * math.sin(math.pi*t)**.65 * (1.12-.35*t)
    # An underlying cone makes the overlapping scales opaque from every angle.
    vertices, faces = [], []
    for row in range(13):
        t = .025+.95*row/12
        r = profile(t)*.9
        for j in range(16):
            a = j*math.tau/16
            vertices.append(world((r*math.cos(a), r*math.sin(a), t*length)))
    for row in range(12):
        for j in range(16):
            a = row*16+j; b = row*16+(j+1)%16
            faces.append((a,b,b+16,a+16))
    mesh(name+' core', vertices, faces, core_mat)
    # Each bract has a raised central rib and a pointed, slightly lifted tip.
    for row in range(8):
        t = .07+row*.108
        r = profile(t)
        count = 7 if row in (0,7) else 9
        for j in range(count):
            angle = math.tau*(j+(row%2)*.5)/count
            radial = Vector((math.cos(angle), math.sin(angle), 0))
            tangent = Vector((-math.sin(angle), math.cos(angle), 0))
            center = radial*r + Vector((0,0,t*length))
            width = radius*(.45 if row not in (0,7) else .34)
            height = length*.19
            local = [center + radial*.006,
                     center-tangent*width-Vector((0,0,height*.24)),
                     center-tangent*width*.78+Vector((0,0,height*.44)),
                     center+Vector((0,0,height*.88))-radial*.008,
                     center+tangent*width*.78+Vector((0,0,height*.44)),
                     center+tangent*width-Vector((0,0,height*.24))]
            mesh(f'{name} bract {row}-{j}', [world(v) for v in local],
                 [(0,1,2),(0,2,3),(0,3,4),(0,4,5),(0,5,1)], RNG.choice(bracts))


def leaf(name, base, angle, size=1):
    # Lobed, toothed hop leaf; a lifted center gives a folded living surface.
    outline = [(0,0),(-.025,.025),(-.055,.02),(-.045,.05),(-.085,.075),
               (-.07,.085),(-.095,.115),(-.05,.12),(-.055,.165),
               (-.025,.15),(0,.22),(.025,.15),(.055,.165),(.05,.12),
               (.095,.115),(.07,.085),(.085,.075),(.045,.05),(.055,.02),(.025,.025)]
    base = Vector(base)
    def world(x,y,z=0):
        return base+Vector(((x*math.cos(angle)-y*math.sin(angle))*size,
                            (x*math.sin(angle)+y*math.cos(angle))*size,z*size))
    vertices = [world(0,.09,.016)]+[world(x,y,.002) for x,y in outline]
    mesh(name,vertices,[(0,j+1,(j+1)%len(outline)+1) for j in range(len(outline))],leaf_mat)
    stem(name+' midrib',[world(0,0,.005),world(0,.09,.019),world(0,.215,.005)],.0015)
    for side in [-1,1]:
        for y,tip_y,tip_x in [(.055,.08,.078),(.09,.115,.085),(.13,.158,.048)]:
            stem(name+' vein',[world(0,y,.013),world(side*tip_x,tip_y,.006)],.0008)


stem('Main hop bine',[(.015,.30,.035),(-.015,.20,.04),(.015,.08,.045),(.01,-.015,.05)],.004)
leaf('Left hop leaf',(-.015,.20,.05),.85,.95)
leaf('Right hop leaf',(.01,.13,.04),-.95,.78)
for name,top,direction,length,radius in [
    ('Left cone',(-.12,.075,.065),(-.10,-1,-.08),.235,.061),
    ('Center cone',(.045,-.015,.075),(.06,-1,-.05),.265,.072),
    ('Right cone',(.19,.08,.055),(.18,-1,-.08),.205,.055)]:
    stem(name+' stalk',[(0,.15,.05),(top[0]*.6,top[1]+.055,.065),top],.003)
    cone(name,top,direction,length,radius)

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/'hops.blend'))
config = dict(model='hops.blend',sprites='illarion/items/plants/hops/item_154',
              visual='items/item_154',direction='west',scale=1.15,include=['Hops'])
(OUTPUT/'hops.json').write_text(json.dumps(config,indent=2)+'\n')
