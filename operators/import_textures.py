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


IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr',
                    '.bmp', '.tga', '.webp', '.hdr')

# Filename suffix token -> channel; aliases cover common pipelines
# (Substance 'basecolor', Marmoset-style 'albedo', Unity 'metallic'...).
# 'color' channels carry a view transform; everything else is raw data.
CHANNEL_SPECS = (
    ('aorm',         ('aorm', 'orm'),                                   True),
    ('basecolor',    ('basecolor', 'base_color', 'albedo', 'diffuse',
                      'diff', 'col', 'color', 'base'),                  False),
    ('normal',       ('normal', 'nrm', 'nor'),                          True),
    ('roughness',    ('roughness', 'rough'),                            True),
    ('metallic',     ('metallic', 'metal', 'metalness'),                True),
    ('specular',     ('specular', 'spec'),                              True),
    ('emission',     ('emission', 'emissive', 'emit', 'glow'),          False),
    ('alpha',        ('alpha', 'opacity'),                              True),
    ('ao',           ('ao', 'occlusion', 'ambientocclusion'),           True),
    ('displacement', ('height', 'displacement', 'disp', 'bump'),        True),
)
_CHANNEL_ALIASES = {alias: channel
                    for channel, aliases, _ in CHANNEL_SPECS
                    for alias in aliases}
_DATA_CHANNELS = {channel for channel, _, is_data in CHANNEL_SPECS if is_data}

_TOKEN_RE = re.compile(r'[_\-.]+')
_TILE_RE = re.compile(r'\d{4}')


def normalize_name(name):
    """'Sword-Low.01' and 'sword_low_1' refer to the same target."""
    return '_'.join(_TOKEN_RE.split(name.casefold()))


def parse_texture_file(filename):
    """'sword_low_albedo_1001.png' -> ('sword_low', 'basecolor', 1001).

    The channel is the last token that names one; a trailing 4-digit token
    before it is the UDIM tile number. Returns None when the filename has
    no recognizable channel suffix."""
    stem, _ext = os.path.splitext(os.path.basename(filename))
    tokens = _TOKEN_RE.split(stem)
    tile = None
    if len(tokens) > 1 and _TILE_RE.fullmatch(tokens[-1]):
        tile = int(tokens.pop())
    channel = _CHANNEL_ALIASES.get(tokens[-1].casefold()) if tokens else None
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


def wire_ambient_occlusion(nodes, links, pbr, img_node, origin):
    """Multiply whatever feeds Base Color by the occlusion map; a flat
    material still darkens through its stored default color."""
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
    links.new(compat.output_socket(img_node, 'Color', 0), sock_b)
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
        sep = nodes.new(type='ShaderNodeSeparateColor')
        sep.location = img_node.location[0] + 170, img_node.location[1]
        links.new(color, compat.input_socket(sep, 'Color', 0))
        links.new(compat.output_socket(sep, 'Green', 1), pbr.inputs['Roughness'])
        links.new(compat.output_socket(sep, 'Blue', 2), pbr.inputs['Metallic'])
        wire_ambient_occlusion(nodes, links, pbr, img_node, sep.location)
    elif channel == 'ao':
        wire_ambient_occlusion(nodes, links, pbr, img_node, img_node.location)
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
    targets = {}     # normalized object/material key -> [materials]
    wired = []       # (stem, channel, material name)
    skipped = []     # (filename, reason)
    for path in sorted(paths):
        parsed = parse_texture_file(path)
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
        image = bpy.data.images.load(path, check_existing=True)
        if tile is not None and getattr(image, 'source', None) == 'FILE':
            image.source = 'TILED'  # Blender fills the remaining tiles
        compat.set_image_colorspace(
            image.colorspace_settings,
            'Non-Color' if channel in _DATA_CHANNELS else 'sRGB')
        stem = os.path.splitext(os.path.basename(path))[0]
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
