# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
"""Shims so one BakeLab build runs on Blender 4.2 LTS through 5.2.

Behavior is chosen by capability detection (RNA lookups, hasattr,
try/except), not by comparing version numbers; bpy.app.version appears
only in describe_environment() for the per-version test log.
"""

import bpy

# 5.0 added ImageFormatSettings.media_type, which filters file_format;
# the property does not exist on 4.2 - 4.5.
SUPPORTS_IMAGE_MEDIA_TYPE = 'media_type' in bpy.types.ImageFormatSettings.bl_rna.properties


def _detect_image_tiles():
    try:
        return ('tiles' in bpy.types.Image.bl_rna.properties and
                'TILED' in {item.identifier for item in
                            bpy.types.Image.bl_rna.properties['source'].enum_items})
    except (AttributeError, KeyError, RuntimeError, TypeError):
        return False


# UDIM images (Image.tiles + source='TILED') exist across 4.2 - 5.2, but the
# flag keeps the capability-detection contract: no build is assumed.
SUPPORTS_IMAGE_TILES = _detect_image_tiles()


def _detect_path_property_options():
    """4.5+ accepts PATH_SUPPORTS_BLEND_RELATIVE so a '//' value on a path
    property stops warning. Unknown option strings raise ValueError at class
    registration, and the flag does not exist before 4.5, so detect support by
    registering a throwaway property rather than hard-coding the set."""
    annotations = {
        'path': bpy.props.StringProperty(
            subtype='DIR_PATH', options={'PATH_SUPPORTS_BLEND_RELATIVE'}),
    }
    probe = type('BAKELAB_PATH_OPTION_PROBE', (bpy.types.PropertyGroup,),
                 {'__annotations__': annotations})
    try:
        bpy.utils.register_class(probe)
        return {'PATH_SUPPORTS_BLEND_RELATIVE'}
    except (ValueError, TypeError, RuntimeError):
        return set()
    finally:
        try:
            bpy.utils.unregister_class(probe)
        except (ValueError, TypeError, RuntimeError):
            pass


# RNA wants a plain set; frozenset is rejected with TypeError.
PATH_PROPERTY_OPTIONS = _detect_path_property_options()

# The live no-look identifier differs by build (5.2: 'None', 4.2 docs:
# 'NONE'); RNA enum_items only exposes a placeholder here, so assign each
# candidate and read back.
NONE_LOOK_CANDIDATES = ('None', 'NONE', '')

# Color space names are OCIO config entries, not API names; these are the
# spellings the default configs of the supported range use.
COLOR_SPACE_CANDIDATES = {
    'sRGB':      ('sRGB EOTF', 'Utility - sRGB - Texture', 'sRGB - Texture'),
    'Non-Color': ('Non-Colour Data', 'Utility - Raw', 'Raw', 'Data'),
}


def enum_values(rna_ptr, key):
    """Identifiers a dynamic enum currently exposes; empty when unknowable."""
    try:
        return {item.identifier for item in rna_ptr.bl_rna.properties[key].enum_items}
    except (AttributeError, KeyError, RuntimeError, TypeError):
        return set()


def set_enum(rna_ptr, key, value):
    """Assign an enum value remembered from another build, tolerating
    identifiers this build rejects. Returns True when the value stuck.

    AttributeError is deliberately NOT caught: a missing key means the caller
    misspelled a property, which is a bug to surface, not a version difference.
    The tolerated cases are builds rejecting a valid-but-unknown identifier."""
    if value is None:
        return False
    try:
        setattr(rna_ptr, key, value)
    except (TypeError, ValueError, RuntimeError):
        return False
    return True


def set_image_file_format(image_format_settings, file_format, media_type=None):
    """Set render.image_settings.file_format on any supported Blender.

    On 5.0+ file_format is filtered by media_type, so the accepted value
    is returned rather than assumed. media_type=None means plain images.
    """
    if SUPPORTS_IMAGE_MEDIA_TYPE:
        wanted = media_type or 'IMAGE'
        if image_format_settings.media_type != wanted:
            image_format_settings.media_type = wanted
    set_enum(image_format_settings, 'file_format', file_format)
    return image_format_settings.file_format


def set_none_look(view_settings):
    """Select 'no look'. Returns the accepted identifier, or None."""
    for candidate in NONE_LOOK_CANDIDATES:
        try:
            view_settings.look = candidate
        except (AttributeError, TypeError, ValueError, RuntimeError):
            continue
        return view_settings.look
    return None


def color_space_candidates(name):
    """`name` first, then the equivalents other OCIO configs use for it."""
    return (name,) + COLOR_SPACE_CANDIDATES.get(name, ())


def set_image_colorspace(colorspace_settings, name):
    """Assign the first accepted color space for `name`. None when none match."""
    ordered = list(color_space_candidates(name))
    accepted = enum_values(colorspace_settings, 'name')
    if accepted:
        ordered = ([c for c in ordered if c in accepted] +
                   [c for c in ordered if c not in accepted])
    for candidate in ordered:
        try:
            colorspace_settings.name = candidate
        except (AttributeError, TypeError, ValueError, RuntimeError):
            continue
        return colorspace_settings.name
    return None


def _matches(socket, key):
    # Display name and identifier differ: Mix Shader input 0 is 'Factor' / 'Fac'.
    return socket.name == key or socket.identifier == key


def socket_at(sockets, name=None, index=None):
    """Pick a node socket without trusting names or positions alone.

    Index matching `name` wins; a name matching exactly one socket is next;
    a bare index is the fallback, which is how ambiguous names (Mix Shader
    has two inputs named 'Shader') stay bound to the intended socket.
    """
    if index is not None and 0 <= index < len(sockets):
        socket = sockets[index]
        if name is None or _matches(socket, name):
            return socket
    if name is not None:
        hits = [s for s in sockets if _matches(s, name)]
        if len(hits) == 1:
            return hits[0]
    if index is not None and 0 <= index < len(sockets):
        return sockets[index]
    return None


def input_socket(node, name=None, index=None):
    return socket_at(node.inputs, name, index)


def output_socket(node, name=None, index=None):
    return socket_at(node.outputs, name, index)


def find_socket_by_alias(node, aliases):
    """First node input answering to any alias (name or identifier)."""
    folded = [alias.strip().casefold() for alias in aliases]
    for alias in folded:
        for socket in node.inputs:
            if socket.name.casefold() == alias or socket.identifier.casefold() == alias:
                return socket
    return None


def enable_nodes(material):
    """Turn on node editing for a freshly created material."""
    if not material.use_nodes:
        material.use_nodes = True
    return material.node_tree


def set_active_uv_layer(uv_layers, layer):
    """Make `layer` the active UV set. Setting the layer's own flag is
    valid on every supported build; assigning uv_layers.active is the
    fallback."""
    try:
        layer.active = True
        return True
    except (AttributeError, TypeError, RuntimeError):
        pass
    try:
        uv_layers.active = layer
        return True
    except (AttributeError, TypeError, RuntimeError):
        return False


def active_uv_name(obj):
    """Editing active UV name, '' when there is none. bake(uv_layer='')
    means 'use the active render UV', so '' degrades gracefully."""
    if obj is None or obj.type != 'MESH':
        return ''
    for layer in obj.data.uv_layers:
        if layer.active:
            return layer.name
    return ''


def new_tiled_image(name, width, height, alpha):
    """Create a UDIM image; it comes with an initialized tile 1001."""
    return bpy.data.images.new(name=name, width=width, height=height,
                               alpha=alpha, tiled=True)


def tile_numbers(image):
    return {tile.number for tile in image.tiles}


def _tile_is_initialized(tile):
    return tile is not None and tuple(tile.size) != (0, 0)


def remove_tile(context, image, tile):
    # tiles.active_index assignment does not switch the active tile; assigning
    # tiles.active does, and tile_remove operates on the active tile.
    image.tiles.active = tile
    with context.temp_override(edit_image=image):
        bpy.ops.image.tile_remove()


def add_tile(context, image, number, width, height, float_depth, color):
    """Give tile `number` a real pixel buffer. image.tiles.new() alone leaves
    tiles uninitialized (0x0) and bake/save then fail with 'Uninitialized
    image'; only image.tile_add with fill allocates pixels. Returns the
    initialized tile, or None."""
    tile = image.tiles.get(number)
    if _tile_is_initialized(tile):
        return tile
    with context.temp_override(edit_image=image):
        bpy.ops.image.tile_add(number=number, fill=True, width=width, height=height,
                               color=color, float=float_depth)
    tile = image.tiles.get(number)
    return tile if _tile_is_initialized(tile) else None


def ensure_tiles(context, image, numbers, width, height, float_depth, color):
    """Initialize every requested tile. Returns the numbers that failed, so
    callers can raise with the exact list."""
    failed = []
    for number in sorted(numbers):
        tile = image.tiles.get(number)
        if _tile_is_initialized(tile):
            continue
        if tile is not None:
            remove_tile(context, image, tile)  # uninitialized leftover
        if add_tile(context, image, number, width, height, float_depth, color) is None:
            failed.append(number)
    return failed


def prune_tiles(context, image, keep):
    """Drop tiles not in `keep` (freshly created images only — never on reuse,
    which would destroy baked pixels). Returns False when a removal did not
    take effect, so the caller can degrade to a warning about extra blank
    tile files instead of failing the bake."""
    for tile in [t for t in image.tiles if t.number not in keep]:
        remove_tile(context, image, tile)
    return tile_numbers(image) <= set(keep)


def enable_addon(module_ref):
    """Best-effort enable without writing the user's saved preferences
    (default_set=False creates no preferences.addons entry, so the caller
    must verify by re-reading whatever the add-on registers)."""
    import addon_utils
    try:
        addon_utils.enable(module_ref, default_set=False)
    except (ImportError, RuntimeError, ValueError):
        return False
    return True


def cycles_settings(scene):
    """scene.cycles, or None while the Cycles add-on is disabled."""
    return getattr(scene, 'cycles', None)


def ensure_cycles(scene):
    """Cycles settings for a bake, enabling the add-on if needed.
    The re-read is authoritative; enable() success alone means nothing."""
    cycles = cycles_settings(scene)
    if cycles is not None:
        return cycles
    for module_ref in ('cycles', 'bl_ext.blender_org.cycles'):
        enable_addon(module_ref)
        cycles = cycles_settings(scene)
        if cycles is not None:
            return cycles
    return None


def describe_environment():
    """One-line summary the regression suite prints per Blender version."""
    image = bpy.data.images.new('BAKELAB_COMPAT_PROBE', 1, 1)
    try:
        srgb = set_image_colorspace(image.colorspace_settings, 'sRGB')
        non_color = set_image_colorspace(image.colorspace_settings, 'Non-Color')
    finally:
        bpy.data.images.remove(image)
    view_settings = bpy.context.scene.render.image_settings.view_settings
    saved_look = view_settings.look
    try:
        look = set_none_look(view_settings)
    finally:
        set_enum(view_settings, 'look', saved_look)
    return ('blender=%s media_type=%s tiles=%s look=%r colorspace sRGB=%r Non-Color=%r cycles=%s'
            % ('.'.join(map(str, bpy.app.version)),
               SUPPORTS_IMAGE_MEDIA_TYPE, SUPPORTS_IMAGE_TILES, look, srgb, non_color,
               cycles_settings(bpy.context.scene) is not None))
