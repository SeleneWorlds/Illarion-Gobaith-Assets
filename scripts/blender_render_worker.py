#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector


DEFAULT_DIRECTIONS = ("north", "east", "south", "west")
DEFAULT_STATIC_DIRECTIONS = ("south",)
DIRECTION_ROTATIONS = {
    "north": math.radians(270.0),
    "east": math.radians(180.0),
    "south": math.radians(90.0),
    "west": 0.0,
}
RIG_COLLECTION_NAME = "_SpriteRenderRig"
SUN_LIGHT_NAME = "SpriteRenderSun"
STATIC_ACTION_NAME = "static"


@dataclass(frozen=True)
class CropRect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class RenderEntry:
    textures: list[str]
    offset_x: int
    offset_y: int
    frames: int
    crop: CropRect
    anchor: tuple[float, float]


@dataclass(frozen=True)
class ObjectState:
    location: Vector
    rotation_mode: str
    rotation_euler: Euler
    rotation_quaternion: tuple[float, float, float, float]
    rotation_axis_angle: tuple[float, float, float, float]
    scale: Vector


@dataclass(frozen=True)
class MaterialImageState:
    material_name: str
    node_name: str
    image_name: str | None


@dataclass(frozen=True)
class RenderVisibilityState:
    name: str
    hide_render: bool


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Render sprites from the currently opened .blend file."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-file", type=Path, required=True)
    parser.add_argument("--tile-width", type=int, required=True)
    parser.add_argument("--tile-height", type=int, required=True)
    parser.add_argument("--light-azimuth", type=float, required=True)
    parser.add_argument("--light-elevation", type=float, required=True)
    parser.add_argument("--light-strength", type=float, required=True)
    parser.add_argument("--ambient-strength", type=float, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--alpha-clip", type=float, default=None)
    parser.add_argument("--alpha-mask", type=Path, default=None)
    parser.add_argument("--materials-json", default=None)
    parser.add_argument("--include-object", action="append", dest="included_objects", default=None)
    parser.add_argument("--exclude-object", action="append", dest="excluded_objects", default=None)
    parser.add_argument(
        "--engine",
        choices=(
            "AUTO",
            "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT",
            "BLENDER_WORKBENCH",
            "CYCLES",
        ),
        default="AUTO",
    )
    parser.add_argument("--action", action="append", dest="actions", default=None)
    parser.add_argument("--direction", action="append", dest="directions", default=None)
    args = parser.parse_args(argv)
    if args.scale <= 0.0:
        raise RuntimeError("--scale must be a positive number")
    return args


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return sanitized or "unnamed"


def parse_material_overrides(raw: str | None) -> dict[str, dict[str, Path]] | None:
    if raw is None:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid --materials-json payload: {exc}") from exc

    if not isinstance(payload, dict) or not payload:
        raise RuntimeError("--materials-json must contain a non-empty object")

    materials: dict[str, dict[str, Path]] = {}
    for material_name, node_payload in payload.items():
        if not isinstance(material_name, str) or not material_name.strip():
            raise RuntimeError("--materials-json contains an empty material name")
        if not isinstance(node_payload, dict) or not node_payload:
            raise RuntimeError(
                f"Material override {material_name!r} must contain a non-empty object"
            )
        nodes: dict[str, Path] = {}
        for node_name, texture_path in node_payload.items():
            if not isinstance(node_name, str) or not node_name.strip():
                raise RuntimeError(
                    f"Material override {material_name!r} contains an empty node name"
                )
            if not isinstance(texture_path, str) or not texture_path.strip():
                raise RuntimeError(
                    f"Material override {material_name!r}/{node_name!r} must be a non-empty string path"
                )
            nodes[node_name.strip()] = Path(texture_path).resolve()
        materials[material_name.strip()] = nodes

    return materials


def collect_object_and_descendants(root: bpy.types.Object) -> list[bpy.types.Object]:
    objects = [root]
    for child in root.children:
        objects.extend(collect_object_and_descendants(child))
    return objects


def collect_named_objects(names: list[str] | None, flag_name: str) -> list[bpy.types.Object]:
    if not names:
        return []
    missing_names = sorted({name for name in names if bpy.data.objects.get(name) is None})
    if missing_names:
        raise RuntimeError(f"Unknown objects requested in {flag_name}: {', '.join(missing_names)}")
    resolved: list[bpy.types.Object] = []
    for name in names:
        obj = bpy.data.objects.get(name)
        assert obj is not None
        resolved.append(obj)
    return resolved


def apply_object_visibility_filters(
    included_names: list[str] | None,
    excluded_names: list[str] | None,
) -> list[RenderVisibilityState]:
    included_roots = collect_named_objects(included_names, "--include-object")
    excluded_roots = collect_named_objects(excluded_names, "--exclude-object")
    if not included_roots and not excluded_roots:
        return []

    original_states: list[RenderVisibilityState] = []
    for obj in bpy.data.objects:
        original_states.append(RenderVisibilityState(name=obj.name, hide_render=obj.hide_render))

    included_names_set: set[str] | None = None
    if included_roots:
        included_names_set = set()
        for root in included_roots:
            included_names_set.update(obj.name for obj in collect_object_and_descendants(root))

    excluded_names_set: set[str] = set()
    for root in excluded_roots:
        excluded_names_set.update(obj.name for obj in collect_object_and_descendants(root))

    for obj in bpy.data.objects:
        if included_names_set is not None:
            obj.hide_render = obj.name not in included_names_set
        if obj.name in excluded_names_set:
            obj.hide_render = True

    return original_states


def restore_object_visibility(states: list[RenderVisibilityState]) -> None:
    for state in states:
        obj = bpy.data.objects.get(state.name)
        if obj is not None:
            obj.hide_render = state.hide_render


def camera_x_degrees_for_tile(tile_width: int, tile_height: int) -> float:
    if tile_width <= 0 or tile_height <= 0:
        raise RuntimeError("tile width and height must be positive")
    if tile_height >= tile_width:
        raise RuntimeError(
            f"tile height must be smaller than tile width for an isometric footprint; got {tile_width}x{tile_height}"
        )
    ratio = tile_height / tile_width
    return math.degrees(math.acos(ratio))


def isometric_camera_rotation(tile_width: int, tile_height: int) -> Euler:
    return Euler(
        (
            math.radians(camera_x_degrees_for_tile(tile_width, tile_height)),
            0.0,
            math.radians(45.0),
        ),
        "XYZ",
    )


def find_render_root() -> bpy.types.Object | None:
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        return None
    return armatures[0]


def is_descendant_of(obj: bpy.types.Object, ancestor: bpy.types.Object) -> bool:
    parent = obj.parent
    while parent is not None:
        if parent == ancestor:
            return True
        parent = parent.parent
    return False


def uses_armature(obj: bpy.types.Object, armature: bpy.types.Object) -> bool:
    return any(
        modifier.type == "ARMATURE" and modifier.object == armature
        for modifier in obj.modifiers
    )


def collect_render_visible_object_names(
    collection: bpy.types.Collection,
    *,
    hidden_by_parent: bool = False,
) -> set[str]:
    if hidden_by_parent or collection.hide_render:
        return set()
    visible = {obj.name for obj in collection.objects}
    for child in collection.children:
        visible.update(
            collect_render_visible_object_names(
                child,
                hidden_by_parent=False,
            )
        )
    return visible


def is_render_visible_mesh(obj: bpy.types.Object, render_visible_names: set[str]) -> bool:
    if obj.type != "MESH" or obj.hide_render or obj.name not in render_visible_names:
        return False
    parent = obj.parent
    while parent is not None:
        if parent.hide_render:
            return False
        parent = parent.parent
    return True


def render_mesh_objects(scene: bpy.types.Scene, root: bpy.types.Object | None) -> list[bpy.types.Object]:
    render_visible_names = collect_render_visible_object_names(scene.collection)
    if root is None:
        meshes = [obj for obj in bpy.data.objects if is_render_visible_mesh(obj, render_visible_names)]
    else:
        meshes = [
            obj
            for obj in bpy.data.objects
            if is_render_visible_mesh(obj, render_visible_names)
            and (is_descendant_of(obj, root) or uses_armature(obj, root))
        ]
    if not meshes:
        raise RuntimeError("No renderable mesh objects were found in the blend file.")
    return meshes


def directional_rotation_targets(
    root: bpy.types.Object | None,
    meshes: list[bpy.types.Object],
) -> list[bpy.types.Object]:
    if root is None:
        return list(meshes)
    return [root] + [mesh for mesh in meshes if not is_descendant_of(mesh, root)]


def rotation_pivot(
    root: bpy.types.Object | None,
    rotation_targets: list[bpy.types.Object],
) -> Vector:
    if root is not None:
        return root.location.copy()
    total = Vector((0.0, 0.0, 0.0))
    for obj in rotation_targets:
        total += obj.location
    return total / max(len(rotation_targets), 1)


def capture_object_state(obj: bpy.types.Object) -> ObjectState:
    return ObjectState(
        location=obj.location.copy(),
        rotation_mode=obj.rotation_mode,
        rotation_euler=obj.rotation_euler.copy(),
        rotation_quaternion=tuple(obj.rotation_quaternion),
        rotation_axis_angle=tuple(obj.rotation_axis_angle),
        scale=obj.scale.copy(),
    )


def restore_object_state(obj: bpy.types.Object, state: ObjectState) -> None:
    obj.location = state.location.copy()
    obj.scale = state.scale.copy()
    obj.rotation_mode = state.rotation_mode
    if state.rotation_mode == "QUATERNION":
        obj.rotation_quaternion = state.rotation_quaternion
    elif state.rotation_mode == "AXIS_ANGLE":
        obj.rotation_axis_angle = state.rotation_axis_angle
    else:
        obj.rotation_euler = state.rotation_euler.copy()


def collect_actions(filter_names: list[str] | None) -> list[bpy.types.Action]:
    actions = sorted(bpy.data.actions, key=lambda action: action.name.lower())
    if filter_names is None:
        return actions
    requested = set(filter_names)
    selected = [action for action in actions if action.name in requested]
    missing = sorted(requested - {action.name for action in selected})
    if missing:
        raise RuntimeError(f"Unknown actions requested: {', '.join(missing)}")
    return selected


def ensure_animation_data(root: bpy.types.Object) -> bpy.types.AnimData:
    if root.animation_data is None:
        root.animation_data_create()
    assert root.animation_data is not None
    return root.animation_data


def iter_action_fcurves(action: bpy.types.Action):
    legacy_fcurves = getattr(action, "fcurves", None)
    if legacy_fcurves is not None and len(legacy_fcurves) > 0:
        yield from legacy_fcurves
        return
    layers = getattr(action, "layers", None)
    slots = getattr(action, "slots", None)
    if not layers or not slots:
        return
    for layer in layers:
        for strip in getattr(layer, "strips", ()):
            channelbag_getter = getattr(strip, "channelbag", None)
            if channelbag_getter is None:
                continue
            for slot in slots:
                try:
                    channelbag = channelbag_getter(slot)
                except RuntimeError:
                    continue
                if channelbag is None:
                    continue
                yield from channelbag.fcurves


def action_frame_numbers(action: bpy.types.Action) -> list[int]:
    start = math.floor(action.frame_range[0])
    end = math.ceil(action.frame_range[1])
    return list(range(start, end + 1))


def action_keyframe_numbers(action: bpy.types.Action) -> list[int]:
    keyed_frames = {
        int(round(keyframe.co.x))
        for fcurve in iter_action_fcurves(action)
        for keyframe in fcurve.keyframe_points
        if math.isfinite(keyframe.co.x)
    }
    if keyed_frames:
        return sorted(keyed_frames)
    return action_frame_numbers(action)


def sampled_action_frame_numbers(
    action: bpy.types.Action,
    source_fps: int,
    target_fps: int,
) -> list[int]:
    frames = action_keyframe_numbers(action)
    if target_fps >= source_fps:
        return frames

    frame_step = max(1, math.ceil(source_fps / target_fps))
    sampled = [frames[0]]
    last_kept_frame = frames[0]
    for frame in frames[1:]:
        if frame - last_kept_frame >= frame_step:
            sampled.append(frame)
            last_kept_frame = frame
    if sampled[-1] != frames[-1]:
        sampled.append(frames[-1])
    return sampled


def ensure_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    camera_object = scene.camera
    if camera_object is None or camera_object.type != "CAMERA":
        camera_data = bpy.data.cameras.new("SpriteRenderCamera")
        camera_object = bpy.data.objects.new("SpriteRenderCamera", camera_data)
        scene.collection.objects.link(camera_object)
        scene.camera = camera_object

    camera = camera_object.data
    assert isinstance(camera, bpy.types.Camera)
    camera.type = "ORTHO"
    camera_object.rotation_mode = "XYZ"
    camera.clip_start = 0.01
    camera.clip_end = 10000.0
    return camera_object


def ensure_rig_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    collection = bpy.data.collections.get(RIG_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(RIG_COLLECTION_NAME)
    if scene.collection.children.get(collection.name) is None:
        scene.collection.children.link(collection)
    return collection


def ensure_light_object(
    collection: bpy.types.Collection,
    name: str,
    light_type: str,
) -> bpy.types.Object:
    light_object = bpy.data.objects.get(name)
    if light_object is None or light_object.type != "LIGHT":
        light_data = bpy.data.lights.new(name=name, type=light_type)
        light_object = bpy.data.objects.new(name, light_data)
    elif light_object.data.type != light_type:
        light_object.data = bpy.data.lights.new(name=f"{name}Data", type=light_type)

    if collection.objects.get(light_object.name) is None:
        collection.objects.link(light_object)
    return light_object


def ensure_lighting(
    scene: bpy.types.Scene,
    azimuth: float,
    elevation: float,
    strength: float,
    ambient_strength: float,
) -> None:
    collection = ensure_rig_collection(scene)
    sun_object = ensure_light_object(collection, SUN_LIGHT_NAME, "SUN")
    sun_object.rotation_mode = "XYZ"
    sun_object.rotation_euler = Euler(
        (
            math.radians(max(min(elevation, 89.0), -89.0)),
            0.0,
            math.radians(azimuth),
        ),
        "XYZ",
    )
    sun_object.location = (0.0, 0.0, 10.0)
    sun_data = sun_object.data
    assert isinstance(sun_data, bpy.types.SunLight)
    sun_data.energy = strength
    sun_data.angle = math.radians(12.0)
    sun_data.color = (1.0, 0.96, 0.9)

    if scene.world is None:
        scene.world = bpy.data.worlds.new("SpriteRenderWorld")
    world = scene.world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.04, 0.04, 0.05, 1.0)
        background.inputs["Strength"].default_value = ambient_strength


def resolve_render_engine(scene: bpy.types.Scene, requested_engine: str) -> str:
    available = {
        item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items
    }
    if requested_engine == "AUTO":
        for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"):
            if candidate in available:
                return candidate
        raise RuntimeError(f"No supported render engine found. Available engines: {sorted(available)}")
    if requested_engine not in available:
        raise RuntimeError(
            f"Render engine {requested_engine!r} is not available. Available engines: {sorted(available)}"
        )
    return requested_engine


def configure_scene(scene: bpy.types.Scene, args: argparse.Namespace) -> None:
    if args.fps < 1:
        raise RuntimeError("--fps must be at least 1")
    render_size = max(512, args.tile_width * 8, args.tile_height * 16)
    scene.render.engine = resolve_render_engine(scene, args.engine)
    scene.render.resolution_x = render_size
    scene.render.resolution_y = render_size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.use_file_extension = True
    scene.render.fps = args.fps
    scene.frame_step = 1
    if scene.render.engine in {"BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"}:
        scene.eevee.taa_render_samples = 16
    elif scene.render.engine == "CYCLES":
        scene.cycles.samples = 32
        scene.cycles.use_adaptive_sampling = True


def apply_material_overrides(
    overrides: dict[str, dict[str, Path]] | None,
) -> tuple[list[MaterialImageState], set[str]]:
    if overrides is None:
        return [], set()

    original_states: list[MaterialImageState] = []
    loaded_image_names: set[str] = set()
    for material_name, node_overrides in overrides.items():
        material = bpy.data.materials.get(material_name)
        if material is None:
            raise RuntimeError(f"Unknown material requested in override: {material_name}")
        if not material.use_nodes or material.node_tree is None:
            raise RuntimeError(f"Material {material_name!r} does not use nodes")

        for node_name, texture_path in node_overrides.items():
            node = material.node_tree.nodes.get(node_name)
            if node is None:
                raise RuntimeError(
                    f"Material {material_name!r} does not contain node {node_name!r}"
                )
            if node.type != "TEX_IMAGE":
                raise RuntimeError(
                    f"Material {material_name!r} node {node_name!r} is not an image texture node"
                )
            if not texture_path.is_file():
                raise RuntimeError(
                    f"Material override texture does not exist for {material_name!r}/{node_name!r}: {texture_path}"
                )

            original_image = node.image
            original_states.append(
                MaterialImageState(
                    material_name=material_name,
                    node_name=node_name,
                    image_name=None if original_image is None else original_image.name,
                )
            )
            image = bpy.data.images.load(str(texture_path), check_existing=True)
            node.image = image
            loaded_image_names.add(image.name)

    return original_states, loaded_image_names


def restore_material_overrides(original_states: list[MaterialImageState]) -> None:
    for state in original_states:
        material = bpy.data.materials.get(state.material_name)
        if material is None or material.node_tree is None:
            continue
        node = material.node_tree.nodes.get(state.node_name)
        if node is None or node.type != "TEX_IMAGE":
            continue
        node.image = None if state.image_name is None else bpy.data.images.get(state.image_name)


def cleanup_loaded_images(image_names: set[str]) -> None:
    for image_name in image_names:
        image = bpy.data.images.get(image_name)
        if image is None:
            continue
        if image.users == 0:
            bpy.data.images.remove(image)


def evaluated_world_bbox(
    depsgraph: bpy.types.Depsgraph,
    obj: bpy.types.Object,
) -> list[Vector]:
    evaluated = obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        if evaluated_mesh is None or len(evaluated_mesh.vertices) == 0:
            return [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
        world_matrix = evaluated.matrix_world
        first_world = world_matrix @ evaluated_mesh.vertices[0].co
        min_x = max_x = first_world.x
        min_y = max_y = first_world.y
        min_z = max_z = first_world.z
        for vertex in evaluated_mesh.vertices[1:]:
            world_vertex = world_matrix @ vertex.co
            min_x = min(min_x, world_vertex.x)
            max_x = max(max_x, world_vertex.x)
            min_y = min(min_y, world_vertex.y)
            max_y = max(max_y, world_vertex.y)
            min_z = min(min_z, world_vertex.z)
            max_z = max(max_z, world_vertex.z)
        return [
            Vector((x, y, z))
            for x in (min_x, max_x)
            for y in (min_y, max_y)
            for z in (min_z, max_z)
        ]
    finally:
        evaluated.to_mesh_clear()


def apply_directional_rotation(
    rotation_targets: list[bpy.types.Object],
    original_states: dict[str, ObjectState],
    pivot: Vector,
    z_rotation: float,
) -> None:
    cosine = math.cos(z_rotation)
    sine = math.sin(z_rotation)
    for obj in rotation_targets:
        state = original_states[obj.name]
        offset = state.location - pivot
        obj.location = Vector(
            (
                pivot.x + (offset.x * cosine) - (offset.y * sine),
                pivot.y + (offset.x * sine) + (offset.y * cosine),
                state.location.z,
            )
        )
        obj.rotation_euler = Euler(
            (
                state.rotation_euler.x,
                state.rotation_euler.y,
                state.rotation_euler.z + z_rotation,
            ),
            "XYZ",
        )


def normalized_view_bounds(
    scene: bpy.types.Scene,
    camera_object: bpy.types.Object,
    points: list[Vector],
) -> tuple[float, float, float, float]:
    projected = [world_to_camera_view(scene, camera_object, point) for point in points]
    xs = [point.x for point in projected]
    ys = [point.y for point in projected]
    return min(xs), max(xs), min(ys), max(ys)


def crop_rect_from_bounds(
    bounds: tuple[float, float, float, float],
    resolution_x: int,
    resolution_y: int,
) -> CropRect:
    min_x, max_x, min_y, max_y = bounds
    min_x = min(max(min_x, 0.0), 1.0)
    max_x = min(max(max_x, 0.0), 1.0)
    min_y = min(max(min_y, 0.0), 1.0)
    max_y = min(max(max_y, 0.0), 1.0)
    left = max(0, min(resolution_x - 1, math.floor(min_x * resolution_x)))
    right = max(left + 1, min(resolution_x, math.ceil(max_x * resolution_x)))
    top = max(0, min(resolution_y - 1, math.floor((1.0 - max_y) * resolution_y)))
    bottom = max(top + 1, min(resolution_y, math.ceil((1.0 - min_y) * resolution_y)))
    return CropRect(left, top, right - left, bottom - top)


def project_point_to_render_pixels(
    scene: bpy.types.Scene,
    camera_object: bpy.types.Object,
    point: Vector,
) -> tuple[float, float]:
    projected = world_to_camera_view(scene, camera_object, point)
    pixel_x = projected.x * scene.render.resolution_x
    pixel_y = (1.0 - projected.y) * scene.render.resolution_y
    return pixel_x, pixel_y


def apply_render_border(scene: bpy.types.Scene, crop: CropRect) -> None:
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    scene.render.border_min_x = crop.x / scene.render.resolution_x
    scene.render.border_max_x = (crop.x + crop.width) / scene.render.resolution_x
    scene.render.border_min_y = 1.0 - ((crop.y + crop.height) / scene.render.resolution_y)
    scene.render.border_max_y = 1.0 - (crop.y / scene.render.resolution_y)


def clear_render_border(scene: bpy.types.Scene) -> None:
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.border_min_x = 0.0
    scene.render.border_max_x = 1.0
    scene.render.border_min_y = 0.0
    scene.render.border_max_y = 1.0


def full_frame_crop(scene: bpy.types.Scene) -> CropRect:
    return CropRect(0, 0, scene.render.resolution_x, scene.render.resolution_y)


def position_camera(
    camera_object: bpy.types.Object,
    scene: bpy.types.Scene,
    points: list[Vector],
    ortho_scale: float,
    tile_width: int,
    tile_height: int,
) -> None:
    flattened: list[float] = []
    for point in points:
        flattened.extend((point.x, point.y, point.z))
    camera_object.rotation_euler = isometric_camera_rotation(tile_width, tile_height)
    for _ in range(2):
        bpy.context.view_layer.update()
        fit_location, _ = camera_object.camera_fit_coords(
            bpy.context.evaluated_depsgraph_get(),
            flattened,
        )
        camera_object.location = fit_location
        camera = camera_object.data
        assert isinstance(camera, bpy.types.Camera)
        camera.ortho_scale = ortho_scale
    bpy.context.view_layer.update()


def calibrate_unit_cube_ortho_scale(
    scene: bpy.types.Scene,
    camera_object: bpy.types.Object,
    target_tile_width: int,
    tile_height: int,
) -> float:
    cube_points = [
        Vector((x, y, z))
        for x in (-0.5, 0.5)
        for y in (-0.5, 0.5)
        for z in (0.0, 1.0)
    ]
    position_camera(camera_object, scene, cube_points, 1.0, target_tile_width, tile_height)
    bounds = normalized_view_bounds(scene, camera_object, cube_points)
    current_width = (bounds[1] - bounds[0]) * scene.render.resolution_x
    if current_width <= 0.0:
        raise RuntimeError("Failed to calibrate unit cube width")
    return current_width / target_tile_width


def bbox_ground_point(points: list[Vector]) -> Vector:
    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)
    min_z = min(point.z for point in points)
    return Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, min_z))


def round_half_away_from_zero(value: float) -> int:
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def texture_relpath(output_dir: Path, file_path: Path) -> str:
    return file_path.resolve().relative_to(output_dir.resolve()).as_posix()


def apply_alpha_clip(file_path: Path, threshold: float) -> None:
    image = bpy.data.images.load(str(file_path), check_existing=False)
    try:
        pixels = list(image.pixels[:])
        for index in range(3, len(pixels), 4):
            pixels[index] = 1.0 if pixels[index] >= threshold else 0.0
        image.pixels[:] = pixels
        image.filepath_raw = str(file_path)
        image.save()
    finally:
        bpy.data.images.remove(image)


def dilate_opaque_pixels(pixels: list[float], width: int, height: int) -> list[float]:
    dilated = pixels[:]
    for y in range(height):
        for x in range(width):
            pixel_index = (y * width + x) * 4
            if pixels[pixel_index + 3] > 0.0:
                continue

            best_neighbor_index = None
            best_neighbor_alpha = 0.0
            for offset_y in (-1, 0, 1):
                neighbor_y = y + offset_y
                if neighbor_y < 0 or neighbor_y >= height:
                    continue
                for offset_x in (-1, 0, 1):
                    neighbor_x = x + offset_x
                    if offset_x == 0 and offset_y == 0:
                        continue
                    if neighbor_x < 0 or neighbor_x >= width:
                        continue

                    neighbor_index = (neighbor_y * width + neighbor_x) * 4
                    neighbor_alpha = pixels[neighbor_index + 3]
                    if neighbor_alpha <= best_neighbor_alpha:
                        continue
                    best_neighbor_index = neighbor_index
                    best_neighbor_alpha = neighbor_alpha

            if best_neighbor_index is None:
                continue

            dilated[pixel_index : pixel_index + 4] = pixels[
                best_neighbor_index : best_neighbor_index + 4
            ]
    return dilated


def mask_alpha_on_render_grid(
    mask_pixels: list[float],
    mask_width: int,
    mask_height: int,
    image_width: int,
    image_height: int,
    offset_x: int = 0,
    offset_y: int = 0,
) -> list[float]:
    mask_alpha = [0.0] * (image_width * image_height)
    start_x = max(0, min(offset_x, image_width - 1)) if image_width > 0 else 0
    start_y = max(0, min(offset_y, image_height - 1)) if image_height > 0 else 0
    overlap_width = min(mask_width, image_width - start_x)
    overlap_height = min(mask_height, image_height - start_y)
    for y in range(overlap_height):
        for x in range(overlap_width):
            mask_alpha[((start_y + y) * image_width) + start_x + x] = mask_pixels[
                ((y * mask_width) + x) * 4 + 3
            ]
    return mask_alpha


def apply_alpha_mask(file_path: Path, mask_path: Path) -> None:
    image = bpy.data.images.load(str(file_path), check_existing=False)
    mask = bpy.data.images.load(str(mask_path), check_existing=False)
    try:
        image_width, image_height = tuple(image.size)
        mask_width, mask_height = tuple(mask.size)
        if (image_width, image_height) != (mask_width, mask_height):
            print(
                "Warning:"
                f" applying alpha mask {mask_path.name} with overlap only;"
                f" mask size {(mask_width, mask_height)}, render size {(image_width, image_height)}",
                file=sys.stderr,
            )
        pixels = dilate_opaque_pixels(list(image.pixels[:]), image_width, image_height)
        mask_pixels = list(mask.pixels[:])
        mask_offset_x = 0
        mask_offset_y = 0
        opaque_columns: list[int] = []
        opaque_rows: list[int] = []
        for pixel_index in range(image_width * image_height):
            if pixels[pixel_index * 4 + 3] <= 0.0:
                continue
            opaque_columns.append(pixel_index % image_width)
            opaque_rows.append(pixel_index // image_width)
        if mask_width < image_width:
            if opaque_columns:
                opaque_left = min(opaque_columns)
                opaque_right = max(opaque_columns) + 1
                if opaque_left > (image_width - opaque_right):
                    mask_offset_x = max(0, min(image_width - mask_width, opaque_right - mask_width))
        if mask_height < image_height:
            if opaque_rows:
                opaque_bottom = min(opaque_rows)
                opaque_top = max(opaque_rows) + 1
                if opaque_bottom > (image_height - opaque_top):
                    mask_offset_y = max(0, min(image_height - mask_height, opaque_top - mask_height))
        mask_alpha = mask_alpha_on_render_grid(
            mask_pixels,
            mask_width,
            mask_height,
            image_width,
            image_height,
            mask_offset_x,
            mask_offset_y,
        )
        for index in range(3, len(pixels), 4):
            pixels[index] = 1.0 if mask_alpha[index // 4] > 0.0 else 0.0
        image.pixels[:] = pixels
        image.filepath_raw = str(file_path)
        image.save()
    finally:
        bpy.data.images.remove(image)
        bpy.data.images.remove(mask)


def render_entries(
    scene: bpy.types.Scene,
    camera_object: bpy.types.Object,
    root: bpy.types.Object | None,
    meshes: list[bpy.types.Object],
    rotation_targets: list[bpy.types.Object],
    base_states: dict[str, ObjectState],
    pivot: Vector,
    actions: list[bpy.types.Action],
    directions: tuple[str, ...],
    output_dir: Path,
    ortho_scale: float,
    render_scale: float,
    source_fps: int,
    target_fps: int,
    tile_width: int,
    tile_height: int,
    alpha_clip: float | None,
    alpha_mask: Path | None,
) -> dict[str, RenderEntry]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    entries: dict[str, RenderEntry] = {}
    original_action = None
    animation_data = None
    if root is not None:
        animation_data = ensure_animation_data(root)
        original_action = animation_data.action

    try:
        if actions:
            assert animation_data is not None
            for action in actions:
                safe_action = sanitize_name(action.name)
                visual_action = safe_action.lower()
                frames = sampled_action_frame_numbers(action, source_fps, target_fps)
                animation_data.action = action
                for direction in directions:
                    apply_directional_rotation(
                        rotation_targets,
                        base_states,
                        pivot,
                        DIRECTION_ROTATIONS[direction],
                    )
                    direction_points = []
                    for frame in frames:
                        scene.frame_set(frame)
                        bpy.context.view_layer.update()
                        for mesh in meshes:
                            direction_points.extend(evaluated_world_bbox(depsgraph, mesh))
                    position_camera(
                        camera_object,
                        scene,
                        direction_points,
                        ortho_scale / render_scale,
                        tile_width,
                        tile_height,
                    )

                    anchor_point = Vector((0.0, 0.0, 0.0))
                    crop = full_frame_crop(scene)
                    anchor_x, anchor_y = project_point_to_render_pixels(scene, camera_object, anchor_point)
                    clear_render_border(scene)

                    direction_dir = output_dir / safe_action / direction
                    direction_dir.mkdir(parents=True, exist_ok=True)
                    textures: list[str] = []
                    for index, frame in enumerate(frames, start=1):
                        scene.frame_set(frame)
                        scene.render.filepath = str(direction_dir / f"{index:04d}")
                        bpy.ops.render.render(write_still=True)
                        rendered_file = direction_dir / f"{index:04d}.png"
                        if alpha_mask is not None:
                            apply_alpha_mask(rendered_file, alpha_mask)
                        elif alpha_clip is not None:
                            apply_alpha_clip(rendered_file, alpha_clip)
                        textures.append(texture_relpath(output_dir, rendered_file))

                    entries[f"{visual_action}/{direction}"] = RenderEntry(
                        textures=textures,
                        offset_x=round_half_away_from_zero((crop.x + (crop.width / 2.0)) - anchor_x),
                        offset_y=round_half_away_from_zero(anchor_y - crop.y - crop.height),
                        frames=len(frames),
                        crop=crop,
                        anchor=(anchor_x - crop.x, anchor_y - crop.y),
                    )
        else:
            for direction in directions:
                apply_directional_rotation(
                    rotation_targets,
                    base_states,
                    pivot,
                    DIRECTION_ROTATIONS[direction],
                )
                bpy.context.view_layer.update()
                frame_points: list[Vector] = []
                for mesh in meshes:
                    frame_points.extend(evaluated_world_bbox(depsgraph, mesh))
                position_camera(
                    camera_object,
                    scene,
                    frame_points,
                    ortho_scale / render_scale,
                    tile_width,
                    tile_height,
                )
                crop = full_frame_crop(scene)
                anchor_point = Vector((0.0, 0.0, 0.0))
                anchor_x, anchor_y = project_point_to_render_pixels(scene, camera_object, anchor_point)
                clear_render_border(scene)

                direction_dir = output_dir / STATIC_ACTION_NAME / direction
                direction_dir.mkdir(parents=True, exist_ok=True)
                scene.render.filepath = str(direction_dir / "0001")
                bpy.ops.render.render(write_still=True)
                rendered_file = direction_dir / "0001.png"
                if alpha_mask is not None:
                    apply_alpha_mask(rendered_file, alpha_mask)
                elif alpha_clip is not None:
                    apply_alpha_clip(rendered_file, alpha_clip)
                texture = texture_relpath(output_dir, rendered_file)

                entries[f"{STATIC_ACTION_NAME}/{direction}"] = RenderEntry(
                    textures=[texture],
                    offset_x=round_half_away_from_zero((crop.x + (crop.width / 2.0)) - anchor_x),
                    offset_y=round_half_away_from_zero(anchor_y - crop.y - crop.height),
                    frames=1,
                    crop=crop,
                    anchor=(anchor_x - crop.x, anchor_y - crop.y),
                )
    finally:
        for obj in rotation_targets:
            restore_object_state(obj, base_states[obj.name])
        if animation_data is not None:
            animation_data.action = original_action
        bpy.context.view_layer.update()

    return entries


def build_metadata(
    args: argparse.Namespace,
    entries: dict[str, RenderEntry],
) -> dict[str, object]:
    payload_entries: dict[str, object] = {}
    for key, entry in sorted(entries.items()):
        payload_entries[key] = {
            "textures": entry.textures,
            "offsetX": entry.offset_x,
            "offsetY": entry.offset_y,
            "frames": entry.frames,
            "crop": {
                "x": entry.crop.x,
                "y": entry.crop.y,
                "width": entry.crop.width,
                "height": entry.crop.height,
            },
            "anchor": {
                "x": entry.anchor[0],
                "y": entry.anchor[1],
            },
        }
    return {
        "fps": args.fps,
        "tileSize": {
            "width": args.tile_width,
            "height": args.tile_height,
        },
        "entries": payload_entries,
    }


def main() -> None:
    if not bpy.data.filepath:
        raise RuntimeError("This script must be run with a .blend file open.")

    args = parse_args()
    output_dir = args.output_dir.resolve()
    metadata_file = args.metadata_file.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    material_overrides = parse_material_overrides(args.materials_json)
    visibility_states = apply_object_visibility_filters(
        args.included_objects,
        args.excluded_objects,
    )

    scene = bpy.context.scene
    source_fps = scene.render.fps
    configure_scene(scene, args)
    ensure_lighting(
        scene,
        args.light_azimuth,
        args.light_elevation,
        args.light_strength,
        args.ambient_strength,
    )

    root = find_render_root()
    meshes = render_mesh_objects(scene, root)
    actions = collect_actions(args.actions)
    if root is None and args.actions is None:
        actions = []
    if args.actions is not None and actions and root is None:
        raise RuntimeError("Named actions were requested, but no armature exists in the blend file.")
    directions = tuple(args.directions) if args.directions is not None else (
        DEFAULT_DIRECTIONS if actions else DEFAULT_STATIC_DIRECTIONS
    )
    for direction in directions:
        if direction not in DIRECTION_ROTATIONS:
            raise RuntimeError(f"Unknown direction {direction!r}")

    camera_object = ensure_camera(scene)
    rotation_targets = directional_rotation_targets(root, meshes)
    base_states = {obj.name: capture_object_state(obj) for obj in rotation_targets}
    for obj in rotation_targets:
        obj.rotation_mode = "XYZ"
    pivot = rotation_pivot(root, rotation_targets)

    original_frame = scene.frame_current
    original_border_settings = (
        scene.render.use_border,
        scene.render.use_crop_to_border,
        scene.render.border_min_x,
        scene.render.border_max_x,
        scene.render.border_min_y,
        scene.render.border_max_y,
    )
    material_states: list[MaterialImageState] = []
    loaded_image_names: set[str] = set()

    try:
        material_states, loaded_image_names = apply_material_overrides(material_overrides)
        unit_cube_ortho_scale = calibrate_unit_cube_ortho_scale(
            scene,
            camera_object,
            args.tile_width,
            args.tile_height,
        )
        entries = render_entries(
            scene,
            camera_object,
            root,
            meshes,
            rotation_targets,
            base_states,
            pivot,
            actions,
            directions,
            output_dir,
            unit_cube_ortho_scale,
            args.scale,
            source_fps,
            args.fps,
            args.tile_width,
            args.tile_height,
            args.alpha_clip,
            args.alpha_mask,
        )
        metadata = build_metadata(args, entries)
        metadata_file.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    finally:
        (
            scene.render.use_border,
            scene.render.use_crop_to_border,
            scene.render.border_min_x,
            scene.render.border_max_x,
            scene.render.border_min_y,
            scene.render.border_max_y,
        ) = original_border_settings
        restore_material_overrides(material_states)
        cleanup_loaded_images(loaded_image_names)
        restore_object_visibility(visibility_states)
        for obj in rotation_targets:
            restore_object_state(obj, base_states[obj.name])
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()


if __name__ == "__main__":
    main()
