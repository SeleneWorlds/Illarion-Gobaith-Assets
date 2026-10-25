"""Rebuild reusable bark/end materials and a three-log stack using Blender."""
import math
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
WOOD = ROOT / 'models/materials/wood'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0


def material(wood, kind):
    mat = bpy.data.materials.new(f'{kind.title()}_{wood.title()}')
    mat.use_nodes = True
    mat.use_fake_user = True
    mat.asset_mark()
    mat.asset_data.description = f'{wood.title()} {kind}; CC0 Textures ' + ('Bark 007' if kind == 'bark' else 'Tree End 001')
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF'); shader.location = (120, 0)
    for name, file, y, noncolor in [('WoodColor', f'{wood}_{kind}_color.jpg', 260, False), ('WoodRoughness', f'{kind}_roughness.jpg', 0, True), ('WoodNormal', f'{kind}_normal_gl.jpg', -260, True)]:
        node = nodes.new('ShaderNodeTexImage'); node.name = name; node.label = name; node.location = (-500, y)
        node.image = bpy.data.images.load(str(WOOD / file), check_existing=True)
        if noncolor: node.image.colorspace_settings.name = 'Non-Color'
        if name == 'WoodColor': links.new(node.outputs['Color'], shader.inputs['Base Color'])
        elif name == 'WoodRoughness': links.new(node.outputs['Color'], shader.inputs['Roughness'])
        else:
            normal = nodes.new('ShaderNodeNormalMap'); normal.location = (-130, -220)
            normal.inputs['Strength'].default_value = 0.8 if kind == 'bark' else 0.25
            links.new(node.outputs['Color'], normal.inputs['Color']); links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    return mat


materials = {(wood, kind): material(wood, kind) for wood in ('conifer', 'cherry', 'naldor', 'apple') for kind in ('bark', 'end')}
bpy.ops.wm.save_as_mainfile(filepath=str(WOOD / 'log_materials.blend'), relative_remap=True)
bark, end = materials['conifer', 'bark'], materials['conifer', 'end']
bark.name, end.name = 'LogBark', 'LogEnd'


def log(name, location, length, radius, yaw, seed):
    # Axis along Y: exposed near ends project toward the lower left.
    count = 32
    verts, faces, face_uvs, indices = [], [], [], []
    radii = [radius*(1 + 0.035*math.sin(i*5*math.tau/count + seed) + 0.02*math.cos(i*3*math.tau/count + seed)) for i in range(count)]
    # Bark rings, then slightly recessed cut-face rings with a thin bark rim.
    for y, factor in [(-length/2,1), (length/2,0.97), (-length/2+0.003,0.94), (length/2-0.003,0.91)]:
        for i,r in enumerate(radii):
            a=i*math.tau/count
            verts.append((r*factor*math.cos(a),y,r*factor*math.sin(a)))
    for i in range(count):
        j=(i+1)%count
        faces.append((i,j,count+j,count+i)); indices.append(0)
        # Bark source grain is vertical, matching the log's length along V.
        face_uvs.append([(i/count+seed*.13,0),( (i+1)/count+seed*.13,0),((i+1)/count+seed*.13,1),(i/count+seed*.13,1)])
        for outer,inner,reverse in [(0,2*count,True),(count,3*count,False)]:
            face=(outer+i,inner+i,inner+j,outer+j)
            if reverse: face=tuple(reversed(face))
            faces.append(face);indices.append(0)
            face_uvs.append([(i/count,0), (i/count,.04),((i+1)/count,.04),((i+1)/count,0)])
    for ring,reverse in [(2*count,False),(3*count,True)]:
        face=tuple(ring+i for i in range(count))
        if reverse: face=tuple(reversed(face))
        faces.append(face);indices.append(1)
        # Stay inside the photographed wood, avoiding the black outer backdrop.
        face_uvs.append([(.5+.405*math.cos((v-ring)*math.tau/count+seed*.8),.5+.405*math.sin((v-ring)*math.tau/count+seed*.8)) for v in face])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.location=location;obj.rotation_euler.z=yaw
    mesh.materials.append(bark);mesh.materials.append(end)
    uv=mesh.uv_layers.new(name='LogUV')
    for polygon, coords, material_index in zip(mesh.polygons,face_uvs,indices):
        polygon.material_index=material_index
        polygon.use_smooth=material_index==0 and polygon.index < count*3 and polygon.index%3==0
        for loop,coord in zip(polygon.loop_indices,coords): uv.data[loop].uv=coord
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges),name
    bm.to_mesh(mesh);bm.free()
    return obj


log('LowerLeft',(-.115,0,.115),1.16,.115,0,0)
log('LowerRight',(.115,-.025,.12),1.2,.12,math.radians(-2),1)
log('Top',(-.01,.055,.315),1.0,.105,math.radians(-12),2)
for mat in list(bpy.data.materials):
    if mat not in (bark,end): bpy.data.materials.remove(mat)
path=ROOT/'models/items/logs/logs.blend';path.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=True)
print('Verified three closed log meshes with separate bark and cut-end surfaces.')
