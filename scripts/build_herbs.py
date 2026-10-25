"""Build herb models from a JSON catalog using Blender's Python API.

Run: blender -b --python scripts/build_herbs.py -- [--only ITEM_OR_SLUG ...]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / 'scripts/data/herbs.json'
DEFAULT_OUTPUT = ROOT / 'models/items/plants/herbs'
PART_TYPES = {'stem', 'leaf', 'flower', 'berries', 'root', 'fern'}
LEAF_SHAPES = {'oval', 'lance', 'heart', 'lobed'}
FLOWER_SHAPES = {'daisy', 'star', 'cup', 'bell', 'spike', 'thistle'}


def vector(value, label):
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in value
    ):
        raise ValueError(f'{label} must contain three finite numbers')
    return Vector(value)


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{label} must be positive')


def validate(catalog):
    """Reject invalid catalogs before writing any models or render recipes."""
    if catalog.get('version') != 1:
        raise ValueError('Unsupported herb catalog version')
    materials = catalog['materials']
    for name, spec in materials.items():
        for field in ('color', 'light'):
            values = list(vector(spec.get(field, spec['color']), f'{name}.{field}'))
            if any(v < 0 or v > 1 for v in values):
                raise ValueError(f'{name}.{field} must use linear RGB values between 0 and 1')
    ids, slugs = set(), set()
    for herb in catalog['herbs']:
        item, slug = herb['item'], herb['slug']
        if not isinstance(item, int) or item <= 0 or item in ids:
            raise ValueError(f'Invalid or duplicate item: {item}')
        if not slug or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in slug) or slug in slugs:
            raise ValueError(f'Invalid or duplicate slug: {slug}')
        ids.add(item)
        slugs.add(slug)
        positive(herb.get('scale', 1), f'{slug}.scale')
        positive(herb.get('stem_thickness', 1), f'{slug}.stem_thickness')
        if herb.get('direction', 'west') not in ('north', 'east', 'south', 'west', 'handheld'):
            raise ValueError(f'{slug}: unsupported render direction')
        if not herb.get('parts'):
            raise ValueError(f'{slug}: at least one part is required')
        for part in herb['parts']:
            kind = part['type']
            if kind not in PART_TYPES:
                raise ValueError(f'{slug}: unsupported part type {kind}')
            for field in ('material', 'center_material', 'stem_material', 'vein_material'):
                if field in part and part[field] not in materials:
                    raise ValueError(f'{slug}: unknown {field}: {part[field]}')
            if kind in ('stem', 'root'):
                if len(part['points']) < 2:
                    raise ValueError(f'{slug}: paths need at least two points')
                for point in part['points']:
                    vector(point, f'{slug}.points')
                positive(part['radius'], f'{slug}.radius')
                if any(Vector(a) == Vector(b) for a, b in zip(part['points'], part['points'][1:])):
                    raise ValueError(f'{slug}: consecutive path points must differ')
            if kind in ('leaf', 'fern'):
                a, b = vector(part['base'], slug), vector(part['tip'], slug)
                if (b-a).length < .001:
                    raise ValueError(f'{slug}: base and tip must differ')
                positive(part['width'], f'{slug}.width')
                if kind == 'leaf' and part.get('shape', 'oval') not in LEAF_SHAPES:
                    raise ValueError(f'{slug}: unsupported leaf shape')
            if kind in ('flower', 'berries'):
                vector(part['at'], slug)
                positive(part['radius'], f'{slug}.radius')
            if kind == 'flower':
                if part.get('shape', 'daisy') not in FLOWER_SHAPES:
                    raise ValueError(f'{slug}: unsupported flower shape')
                if vector(part.get('normal', [.3, -.5, .8]), slug).length < .001:
                    raise ValueError(f'{slug}: flower normal must not be zero')
            for field in ('count', 'petals', 'pairs'):
                if field in part and (not isinstance(part[field], int) or part[field] < 1):
                    raise ValueError(f'{slug}.{field} must be a positive integer')
    return catalog


class HerbBuilder:
    def __init__(self, herb, palette):
        self.herb = herb
        self.rng = random.Random(herb.get('seed', herb['item']))
        self.stem_thickness = herb.get('stem_thickness', 1)
        self.materials = {}
        self.objects = []
        for name, spec in palette.items():
            mat = bpy.data.materials.new(name)
            mat.use_nodes = True
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            shader = nodes.get('Principled BSDF')
            shader.inputs['Roughness'].default_value = spec.get('roughness', .8)
            shader.inputs['Subsurface Weight'].default_value = spec.get('subsurface', .02)
            tex = nodes.new('ShaderNodeTexNoise')
            tex.inputs['Scale'].default_value = 5
            tex.inputs['Detail'].default_value = 2
            ramp = nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color = (*spec['color'], 1)
            ramp.color_ramp.elements[1].color = (*spec.get('light', spec['color']), 1)
            links.new(tex.outputs['Fac'], ramp.inputs[0])
            links.new(ramp.outputs[0], shader.inputs['Base Color'])
            self.materials[name] = mat

    def mesh(self, name, verts, faces, material):
        data = bpy.data.meshes.new(name)
        data.from_pydata(verts, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        data.materials.append(self.materials[material])
        for face in data.polygons:
            face.use_smooth = True
        self.objects.append(obj)
        return obj

    def path(self, points, radius, material='stem', taper=.6, name='Stem'):
        # Sample Catmull–Rom paths directly. Blender's curve cap tessellation can
        # reorder faces between runs; explicit tube topology stays deterministic.
        if name in ('Stem', 'Berry stalk'):
            radius *= self.stem_thickness
        points = [Vector(p) for p in points]
        samples = []
        for j in range(len(points)-1):
            p0, p1 = points[max(0,j-1)], points[j]
            p2, p3 = points[j+1], points[min(j+2,len(points)-1)]
            for step in range(8):
                t = step/8
                samples.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
        samples.append(points[-1])
        verts, faces = [], []
        sides = 10
        for j, center in enumerate(samples):
            tangent = samples[min(j+1,len(samples)-1)]-samples[max(0,j-1)]
            orient = tangent.to_track_quat('Z','Y')
            r = radius*(1+(taper-1)*j/(len(samples)-1))
            for i in range(sides):
                angle = math.tau*i/sides
                verts.append(center+orient@Vector((r*math.cos(angle),r*math.sin(angle),0)))
        for j in range(len(samples)-1):
            for i in range(sides):
                a=j*sides+i
                b=j*sides+(i+1)%sides
                faces.append((a,b,b+sides,a+sides))
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple(range((len(samples)-1)*sides,len(samples)*sides)))
        return self.mesh(name, verts, faces, material)

    def sphere(self, center, radii, material, name='Berry'):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=1, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.scale = radii
        obj.data.materials.append(self.materials[material])
        for face in obj.data.polygons:
            face.use_smooth = True
        self.objects.append(obj)
        return obj

    def leaf(self, spec):
        base, tip = Vector(spec['base']), Vector(spec['tip'])
        axis = tip-base
        along = axis.normalized()
        normal = Vector(spec.get('normal', [0, 0, 1])).normalized()
        side = along.cross(normal)
        if side.length < .01:
            side = along.cross(Vector((0, 1, 0)))
        side.normalize()
        normal = side.cross(along).normalized()
        width = spec['width']
        shape = spec.get('shape', 'oval')
        curl = spec.get('curl', .02)
        rows, cols = 24, 4
        verts, faces, midrib = [], [], []
        for j in range(rows+1):
            t = j/rows
            profile = math.sin(math.pi*t)**(.72 if shape == 'oval' else 1)
            if shape == 'heart':
                profile = math.sin(math.pi*t)**.6*(1.35-.7*t)
            if shape == 'lobed':
                profile *= .72+.28*math.cos(t*math.pi*10)
            if spec.get('serrated') and j not in (0, rows):
                profile *= 1 if j % 2 else .78
            center = base + axis*t + normal*(curl*math.sin(math.pi*t))
            midrib.append(center + normal*.001)
            for k in range(cols+1):
                u = k/cols*2-1
                v = center + side*(u*width*.5*profile) - normal*(abs(u)*width*.09*profile)
                verts.append(v)
        for j in range(rows):
            for k in range(cols):
                a = j*(cols+1)+k
                faces.append((a, a+1, a+cols+2, a+cols+1))
        self.mesh('Leaf', verts, faces, spec.get('material', 'leaf'))
        if spec.get('veins', True):
            veinmat = spec.get('vein_material', 'vein')
            self.path(midrib[::4], .0009, veinmat, .3, 'Leaf midrib')
            if width > .045:
                for j in (6, 10, 14, 18):
                    for sign in (-1, 1):
                        end = verts[(j+3)*(cols+1)+(cols if sign > 0 else 0)]
                        self.path([midrib[j], (midrib[j]+end)*.5+normal*.001, end], .00045, veinmat, .2, 'Leaf vein')

    def flower(self, spec):
        origin = Vector(spec['at'])
        normal = Vector(spec.get('normal', [.3, -.5, .8])).normalized()
        orient = normal.to_track_quat('Z', 'Y')
        radius = spec['radius']
        mat = spec.get('material', 'yellow')
        shape = spec.get('shape', 'daisy')
        petals = spec.get('petals', 10 if shape == 'daisy' else 5)
        def world(v):
            return origin + orient @ Vector(v)
        if shape in ('cup', 'bell'):
            verts, faces = [], []
            depth = spec.get('depth', radius*1.2)
            segments, rings = 48, 10
            # Outer and inner surfaces meet at the rim, giving the cup a visible thickness.
            profile = []
            for j in range(rings+1):
                t = j/rings
                profile.append((radius*(.16+.84*t), depth*t**1.5))
            profile += [(r-.0015, z-.0015) for r, z in reversed(profile)]
            for j, (r, z) in enumerate(profile):
                for i in range(segments):
                    a = math.tau*i/segments
                    rim = .06*radius*math.cos(a*petals)*(r/radius)**5
                    verts.append(world((r*math.cos(a), r*math.sin(a), z+rim)))
            for j in range(len(profile)-1):
                for i in range(segments):
                    a = j*segments+i
                    b = j*segments+(i+1)%segments
                    faces.append((a,b,b+segments,a+segments))
            self.mesh('Flower cup', verts, faces, mat)
            self.sphere(world((0,0,depth*.12)), (radius*.22,)*3, spec.get('center_material', 'gold'), 'Pollen')
        elif shape in ('spike', 'thistle'):
            length = spec.get('length', radius*3)
            if shape == 'thistle':
                obj = self.sphere(origin, (radius*.65, radius*.65, length*.5), mat, 'Thistle head')
                obj.rotation_euler = orient.to_euler()
                for i in range(26):
                    a = i*math.tau/26
                    self.path([world((radius*.45*math.cos(a),radius*.45*math.sin(a),0)), world((radius*math.cos(a),radius*math.sin(a),length*.4)), world((radius*1.1*math.cos(a),radius*1.1*math.sin(a),length*.64))], .001, spec.get('center_material','cream'), .15, 'Thistle bristle')
            else:
                self.path([origin, world((0,0,length))], .002, 'stem', .4)
                for j in range(8):
                    for i in range(3):
                        a=i*math.tau/3+j*.8
                        r=radius*(1-.65*j/8)
                        self.sphere(world((r*math.cos(a),r*math.sin(a),j*length/8)), (radius*.38,)*3, mat, 'Spike blossom')
        else:
            for i in range(petals):
                angle = math.tau*i/petals
                verts, faces = [], []
                for j in range(9):
                    t=j/8
                    width=radius*(.30 if shape=='daisy' else .44)*math.sin(math.pi*t)**(.5 if shape=='daisy' else 1)
                    for u in (-1,0,1):
                        x=radius*(.13+.87*t)
                        y=width*u*.5
                        z=radius*(.10*math.sin(math.pi*t)+.12*t*t-.05*abs(u))
                        verts.append(world((x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle),z)))
                for j in range(8):
                    for k in range(2):
                        a=j*3+k;faces.append((a,a+1,a+4,a+3))
                self.mesh('Petal', verts, faces, mat)
            self.sphere(origin+normal*radius*.08, (radius*.23,)*3, spec.get('center_material', 'gold'), 'Flower center')

    def berries(self, spec):
        center = Vector(spec['at'])
        radius = spec['radius']
        count = spec.get('count', 5)
        spread = spec.get('spread', radius*1.7)
        for i in range(count):
            angle=i*2.399963
            distance=spread*math.sqrt(i/max(count-1,1))
            pos=center+Vector((distance*math.cos(angle),distance*math.sin(angle),self.rng.uniform(-radius*.3,radius*.3)))
            r=radius*self.rng.uniform(.9,1.1)
            self.sphere(pos, (r,r,r*.95), spec.get('material','red'), 'Berry')
            junction=Vector(spec.get('junction',list(center+Vector((0,0,radius*2.8)))))
            self.path([junction,(junction+pos)*.5+Vector((0,0,.008)),pos+Vector((0,0,r*.85))], .0018, spec.get('stem_material','stem'), .5, 'Berry stalk')
            # Small sepals mark the fruit attachment and keep the berries recognizable.
            for j in range(5):
                a=j*math.tau/5
                self.mesh('Berry sepal', [pos+Vector((0,0,r*.98)), pos+Vector((r*.35*math.cos(a),r*.35*math.sin(a),r*1.02)), pos+Vector((r*.12*math.cos(a+.7),r*.12*math.sin(a+.7),r*.98))], [(0,1,2)], spec.get('stem_material','stem'))

    def fern(self, spec):
        base, tip = Vector(spec['base']), Vector(spec['tip'])
        axis=tip-base;along=axis.normalized()
        side=along.cross(Vector((0,0,1)))
        if side.length < .01:
            side=Vector((1,0,0))
        side.normalize()
        self.path([base,base+axis*.5+Vector((0,0,.012)),tip], spec.get('radius',.003), spec.get('stem_material','stem'), .2)
        count=spec.get('pairs',9)
        for j in range(count):
            t=.12+.8*j/count
            width=spec['width']*(1-t)**.7
            for sign in (-1,1):
                b=base+axis*t
                end=b+side*sign*width*.5+along*width*.22
                self.leaf({'base':list(b),'tip':list(end),'width':width*spec.get('leaflet_width',.18),'material':spec.get('material','leaf'),'serrated':spec.get('serrated',False),'shape':'lance','curl':.004,'veins':False})

    def build(self):
        for spec in self.herb['parts']:
            kind=spec['type']
            if kind in ('stem','root'):
                self.path(spec['points'],spec['radius'],spec.get('material','root' if kind=='root' else 'stem'),spec.get('taper',.1 if kind=='root' else .6),kind.title())
            else:
                getattr(self,kind)(spec)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in self.objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active=self.objects[0]
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.join()
        obj=bpy.context.object
        obj.name='Herb'
        # Drop unused palette entries, keeping only self-contained materials used by this herb.
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        return obj


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=DEFAULT_CATALOG)
    parser.add_argument('--output-dir',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--only',nargs='+',default=[],help='Item IDs or slugs to rebuild')
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    catalog=validate(json.loads(args.config.read_text()))
    selected=[h for h in catalog['herbs'] if not args.only or str(h['item']) in args.only or h['slug'] in args.only]
    known={str(h['item']) for h in catalog['herbs']}|{h['slug'] for h in catalog['herbs']}
    if set(args.only)-known:
        raise ValueError(f'Unknown herbs: {sorted(set(args.only)-known)}')
    if args.validate_only:
        print(f'Validated {len(selected)} herb configurations')
        return
    args.output_dir.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0
    for herb in selected:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        builder=HerbBuilder(herb,catalog['materials'])
        obj=builder.build()
        if not obj.data.vertices or any(not math.isfinite(v) for vertex in obj.data.vertices for v in vertex.co):
            raise ValueError(f"{herb['slug']}: invalid generated geometry")
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str((args.output_dir/(herb['slug']+'.blend')).resolve()))
        recipe={'model':herb['slug']+'.blend','sprites':f"illarion/items/plants/herbs/item_{herb['item']}",'visual':f"items/item_{herb['item']}",'direction':herb.get('direction','west'),'scale':herb.get('scale',1),'include':['Herb']}
        (args.output_dir/(herb['slug']+'.json')).write_text(json.dumps(recipe,indent=2)+'\n')
        print(f"Built {herb['item']}: {herb['name']}")


if __name__=='__main__':
    main()
