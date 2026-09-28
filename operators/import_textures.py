import os
import re

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from bpy.props import (
            CollectionProperty,
            StringProperty
        )

from ..utils import compat
from ..utils.tools import CHANNEL_ALIASES, DATA_CHANNELS
from ..properties.prefs import addon_preferences, import_alias_map


IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr',
                    '.bmp', '.tga', '.webp', '.hdr')

_TOKEN_RE = re.compile(r'[_\-.]+')
_TILE_RE = re.compile(r'\d{4}')


def normalize_name(name):
    """'Sword-Low.01' and 'sword_low_1' refer to the same target."""
    return '_'.join(_TOKEN_RE.split(name.casefold()))


def parse_texture_file(filename, extra_aliases=None):
    """'sword_low_albedo_1001.png' -> ('sword_low', 'basecolor', 1001).

    The channel is the last token that names one; `extra_aliases`
    ({keyword: channel}) from the addon preferences are checked before
    the builtin table. A trailing 4-digit token before it is the UDIM
    tile number. Returns None when the filename has no recognizable
    channel suffix."""
    stem, _ext = os.path.splitext(os.path.basename(filename))
    tokens = _TOKEN_RE.split(stem)
    tile = None
    if len(tokens) > 1 and _TILE_RE.fullmatch(tokens[-1]):
        tile = int(tokens.pop())
    last = tokens[-1].casefold() if tokens else None
    channel = (extra_aliases or {}).get(last) or CHANNEL_ALIASES.get(last)
    if channel is None:
        return None
    tokens.pop()
    return '_'.join(tokens).casefold(), channel, tile


def principled_of(nodes):
    for node in nodes:
        if node.bl_idname == 'ShaderNodeBsdfPrincipled':
            return node
    return None


def find_or_make_image_node(nodes, stem, image):
    node = nodes.get(stem)
    if node is None or node.bl_idname != 'ShaderNodeTexImage':
        node = nodes.new(type='ShaderNodeTexImage')
        node.name = stem
    node.image = image
    return node


def base_color_socket(pbr):
    return compat.find_socket_by_alias(pbr, ('Base Color', 'Albedo', 'Color'))


def mix_color_socket(mix, name, sockets):
    """ShaderNodeMix carries an 'A'/'B' socket per data type; only the RGBA
    pair is live in color mode - names alone would bind the float one."""
    return next(s for s in sockets if s.name == name and s.type == 'RGBA')


def wire_ambient_occlusion(nodes, links, pbr, occlusion, origin):
    """Multiply whatever feeds Base Color by the `occlusion` output socket;
    a flat material still darkens through its stored default color. A
    re-import finds its multiply already in place and adds no second one."""
    if any(link.to_node.bl_idname == 'ShaderNodeMix' for link in occlusion.links):
        return
    base = base_color_socket(pbr)
    mix = nodes.new(type='ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = origin[0] - 180, origin[1]
    compat.input_socket(mix, 'Factor', 0).default_value = 1.0
    sock_a = mix_color_socket(mix, 'A', mix.inputs)
    sock_b = mix_color_socket(mix, 'B', mix.inputs)
    if base.is_linked:
        links.new(base.links[0].from_socket, sock_a)
        links.remove(base.links[0])
    else:
        sock_a.default_value = base.default_value
    links.new(occlusion, sock_b)
    links.new(next(s for s in mix.outputs if s.type == 'RGBA'), base)


def wire_channel(mat, stem, channel, image):
    """Add the image to the material and wire it into its channel. Returns
    the created image node so callers can position it."""
    tree = compat.enable_nodes(mat)
    nodes = tree.nodes
    links = tree.links
    pbr = principled_of(nodes)
    if pbr is None:
        pbr = nodes.new(type='ShaderNodeBsdfPrincipled')
        pbr.location = 0, 0
        out = next((n for n in nodes if n.bl_idname == 'ShaderNodeOutputMaterial'), None)
        if out is None:
            out = nodes.new(type='ShaderNodeOutputMaterial')
            out.location = 400, 0
        if not compat.input_socket(out, 'Surface', 0).is_linked:
            links.new(compat.output_socket(pbr, 'BSDF', 0),
                      compat.input_socket(out, 'Surface', 0))
    img_node = find_or_make_image_node(nodes, stem, image)
    img_node.label = channel.title()
    img_node.location = pbr.location[0] - 300, pbr.location[1] + 260
    color = compat.output_socket(img_node, 'Color', 0)

    if channel == 'basecolor':
        links.new(color, base_color_socket(pbr))
    elif channel == 'normal':
        socket = compat.input_socket(pbr, 'Normal')
        normal_map = next((link.from_node for link in socket.links
                           if link.from_node.bl_idname == 'ShaderNodeNormalMap'), None)
        if normal_map is None:
            normal_map = nodes.new(type='ShaderNodeNormalMap')
            normal_map.location = img_node.location[0] + 170, img_node.location[1]
            links.new(compat.output_socket(normal_map, 'Normal', 0), socket)
        links.new(color, compat.input_socket(normal_map, 'Color', 1))
    elif channel == 'aorm':
        sep = next((link.to_node for link in color.links
                    if link.to_node.bl_idname == 'ShaderNodeSeparateColor'), None)
        if sep is None:
            sep = nodes.new(type='ShaderNodeSeparateColor')
            links.new(color, compat.input_socket(sep, 'Color', 0))
        sep.location = img_node.location[0] + 170, img_node.location[1]
        links.new(compat.output_socket(sep, 'Green', 1), pbr.inputs['Roughness'])
        links.new(compat.output_socket(sep, 'Blue', 2), pbr.inputs['Metallic'])
        # Only the red channel is occlusion; the full color would tint Base
        # Color by roughness and metallic
        wire_ambient_occlusion(nodes, links, pbr,
                               compat.output_socket(sep, 'Red', 0), sep.location)
    elif channel == 'ao':
        wire_ambient_occlusion(nodes, links, pbr, color, img_node.location)
    elif channel == 'alpha':
        socket = compat.input_socket(pbr, 'Alpha')
        if socket is not None:
            links.new(color, socket)
            compat.enable_transparency(mat)
    elif channel == 'displacement':
        # Bump, not true displacement: needs no render feature flags
        bump = next((link.from_node for link in compat.input_socket(pbr, 'Normal').links
                     if link.from_node.bl_idname == 'ShaderNodeBump'), None)
        if bump is None:
            bump = nodes.new(type='ShaderNodeBump')
            bump.location = img_node.location[0] + 170, img_node.location[1]
            # 4.5 changed the Bump Distance default from 1.0 to 0.001; pin
            # it so imported height maps shade the same on 4.2 - 5.2
            compat.input_socket(bump, 'Distance', 1).default_value = 1.0
            links.new(compat.output_socket(bump, 'Normal', 0),
                      compat.input_socket(pbr, 'Normal'))
        links.new(color, compat.input_socket(bump, 'Height', 2))
    elif channel == 'emission':
        socket = compat.find_socket_by_alias(pbr, ('Emission Color', 'Emission'))
        if socket is not None:
            links.new(color, socket)
    else:
        socket = compat.find_socket_by_alias(
            pbr, {'roughness': ('Roughness',), 'metallic': ('Metallic', 'Metalness'),
                  'specular': ('Specular IOR Level', 'Specular')}[channel])
        if socket is not None:
            links.new(color, socket)
    return img_node


def load_udim_image(path):
    """The TILED image for one tile file of a UDIM set. Blender stores a
    set under its '<UDIM>' path, so the other tiles of the set (or a set
    loaded before) resolve to the same image."""
    root, ext = os.path.splitext(path)
    udim_path = os.path.normcase(os.path.abspath(root[:-4] + '<UDIM>' + ext))
    for image in bpy.data.images:
        if image.source == 'TILED' and udim_path == os.path.normcase(
                os.path.abspath(bpy.path.abspath(image.filepath))):
            return image
    image = bpy.data.images.load(path, check_existing=True)
    if image.source == 'FILE':
        image.source = 'TILED'  # Blender fills the remaining tiles
    return image


def target_materials(context, key):
    """Resolve a filename key ('sword_low') to materials. Object names win
    over material names; an empty key targets the active object."""
    normalized = {normalize_name(o.name): o
                  for o in context.scene.collection.all_objects
                  if hasattr(o.data, 'materials')}
    if key in normalized:
        obj = normalized[key]
        mat = obj.active_material
        if mat is None and obj.material_slots:
            mat = obj.material_slots[0].material
        if mat is None:
            mat = bpy.data.materials.new(obj.name + '_mat')
            if obj.material_slots:
                obj.material_slots[0].material = mat
            else:
                obj.data.materials.append(mat)
        return [mat]
    for mat in bpy.data.materials:
        if normalize_name(mat.name) == key:
            return [mat]
    return None


def import_textures(context, paths, report):
    """Wire image files into materials by filename: '<target>_<channel>.png'.
    Returns (wired, skipped) so callers/tests can assert on the outcome."""
    extra_aliases = import_alias_map(context)
    targets = {}     # normalized object/material key -> [materials]
    wired = []       # (stem, channel, material name)
    skipped = []     # (filename, reason)
    udim_sets = set()  # (key, channel, stem) already wired from another tile
    for path in sorted(paths):
        parsed = parse_texture_file(path, extra_aliases)
        if parsed is None:
            skipped.append((os.path.basename(path), 'no known channel suffix'))
            continue
        key, channel, tile = parsed
        mats = targets.get(key)
        if key not in targets:
            mats = target_materials(context, key) if key else \
                   target_materials(context, normalize_name(
                       context.active_object.name) if context.active_object else '')
            targets[key] = mats
        if not mats:
            skipped.append((os.path.basename(path),
                            'no object or material named "%s"' % key))
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        if tile is not None:
            # One image and node serve the whole set: name_1001, name_1002...
            stem = stem[:-4].rstrip('_-.')
            if (key, channel, stem) in udim_sets:
                continue
            udim_sets.add((key, channel, stem))
            image = load_udim_image(path)
        else:
            image = bpy.data.images.load(path, check_existing=True)
        compat.set_image_colorspace(
            image.colorspace_settings,
            'Non-Color' if channel in DATA_CHANNELS else 'sRGB')
        for mat in mats:
            wire_channel(mat, stem, channel, image)
            wired.append('%s -> %s (%s)' % (stem, mat.name, channel))
    for text in wired:
        report(type={'INFO'}, message='Wired ' + text)
    for name, reason in skipped:
        report(type={'WARNING'}, message='Skipped %s: %s' % (name, reason))
    return wired, skipped


class BakeLab_ImportTextures(Operator, ImportHelper):
    """Import images and wire them into materials by filename convention"""
    bl_label = 'Import Textures'
    bl_idname = 'bakelab.import_textures'
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(
        default='*' + ';*'.join(IMAGE_EXTENSIONS),
        options={'HIDDEN'})

    def execute(self, context):
        if self.files:
            paths = [os.path.join(self.directory, entry.name)
                     for entry in self.files]
        else:
            # A bare directory means "import every image in it"
            paths = [os.path.join(self.directory, name)
                     for name in sorted(os.listdir(self.directory))
                     if name.casefold().endswith(IMAGE_EXTENSIONS)]
        if not paths:
            self.report(type={'ERROR'}, message='No image files selected')
            return {'CANCELLED'}
        import_textures(context, paths, self.report)
        return {'FINISHED'}


class BakeLab_ImportAliasAdd(Operator):
    """Add a custom filename-suffix -> channel rule to the preferences"""
    bl_label = 'Add import alias'
    bl_idname = 'bakelab.import_alias_add'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = addon_preferences(context)
        if prefs is None:
            return {'CANCELLED'}
        prefs.import_aliases.add()
        prefs.import_aliases_index = len(prefs.import_aliases) - 1
        return {'FINISHED'}


class BakeLab_ImportAliasRemove(Operator):
    """Remove the active import alias"""
    bl_label = 'Remove import alias'
    bl_idname = 'bakelab.import_alias_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        prefs = addon_preferences(context)
        return prefs is not None and len(prefs.import_aliases) > 0

    def execute(self, context):
        prefs = addon_preferences(context)
        index = prefs.import_aliases_index
        prefs.import_aliases.remove(index)
        prefs.import_aliases_index = min(index, len(prefs.import_aliases) - 1)
        return {'FINISHED'}
