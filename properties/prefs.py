from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import (
            CollectionProperty,
            EnumProperty,
            IntProperty,
            StringProperty
        )

# properties/prefs.py lives one level under the package root, so the
# registered add-on module name is the parent ('bl_ext.<repo>.bakelab',
# 'blender_bakelab', or the test loader name).
_ROOT_PACKAGE = __package__.rsplit('.', 1)[0]


def cycles_preferences(context):
    addon = context.preferences.addons.get('cycles')
    return addon.preferences if addon is not None else None


def addon_preferences(context):
    addon = context.preferences.addons.get(_ROOT_PACKAGE)
    return addon.preferences if addon is not None else None


def gpu_backend_items(self, context):
    items = [('AUTO', 'Auto', "Keep Blender's own Cycles backend setting")]
    cycles = cycles_preferences(context)
    if cycles is not None:
        try:
            items.extend((item[0], item[1], item[2])
                         for item in cycles.get_device_types(context))
        except RuntimeError:
            pass
    return items


def apply_gpu_backend(prefs, context):
    """Write the chosen backend through to Cycles and refresh its device
    list. AUTO leaves Blender's own setting alone; a stored backend that
    this machine lacks (e.g. OptiX without an NVIDIA GPU) is ignored."""
    backend = getattr(prefs, 'gpu_backend', 'AUTO')
    if backend == 'AUTO':
        return
    cycles = cycles_preferences(context)
    if cycles is None:
        return
    try:
        available = {item[0] for item in cycles.get_device_types(context)}
    except RuntimeError:
        available = set()
    if backend not in available:
        return
    cycles.compute_device_type = backend
    try:
        cycles.get_devices(context)
    except RuntimeError:
        pass


def gpu_fallback_reason(context):
    """Why a GPU bake will run on the CPU, or None when a GPU is ready (or
    Cycles cannot tell). Cycles silently uses the CPU without a device."""
    cycles = cycles_preferences(context)
    if cycles is None:
        return None
    try:
        ready = cycles.has_active_device()
    except (AttributeError, RuntimeError):
        return None
    if ready:
        return None
    return ('No GPU device is enabled for %s - Cycles bakes on the CPU. '
            'Enable one in Preferences > System' % cycles.compute_device_type)


def _gpu_backend_update(self, context):
    apply_gpu_backend(self, context)


def import_channel_items(self, context):
    from ..utils.tools import CHANNEL_SPECS
    return [(channel, channel.title(), '') for channel, _, _ in CHANNEL_SPECS]


class BakeLabMapDefault(PropertyGroup):
    """Per-type overrides for the Add Map operator and the auto-added
    default map. Rows are seeded from MAP_TYPE_DEFAULTS and persist."""
    type       : StringProperty(name = 'Type')
    img_name   : StringProperty(name = 'Name', default = '*',
                    description = 'Image name pattern; * is the job name')
    samples    : IntProperty(name = 'Samples', default = 4, min = 1,
                    soft_max = 512)
    color_space: EnumProperty(name = 'Color Space',
                    items = (('sRGB', 'sRGB', ''),
                             ('Non-Color', 'Non-Color', '')),
                    default = 'sRGB')


class BakeLabImportAlias(PropertyGroup):
    """An extra filename suffix the texture importer treats as a channel,
    e.g. keyword 'msk' -> 'alpha'. Checked before the builtin aliases."""
    keyword: StringProperty(name = 'Keyword')
    channel: EnumProperty(name = 'Channel', items = import_channel_items)


def seed_map_defaults(prefs):
    """Populate the defaults table from the shipped values. Only missing
    types are added, so a new map type in a later version appears in an
    existing table without resetting user edits."""
    from .maps import MAP_TYPE_ITEMS, MAP_TYPE_DEFAULTS
    have = {row.type for row in prefs.map_defaults}
    for item in MAP_TYPE_ITEMS:
        if item is None or item[0] in have:
            continue
        map_type = item[0]
        spec = MAP_TYPE_DEFAULTS.get(map_type, {})
        row = prefs.map_defaults.add()
        row.type = map_type
        row.img_name = spec.get('img_name', '*')
        row.samples = spec.get('samples', 4)
        row.color_space = spec.get('color_space', 'sRGB')


def overrides_from_prefs(prefs, map_type):
    row = next((r for r in prefs.map_defaults if r.type == map_type), None)
    if row is None:
        return None
    return {'img_name': row.img_name, 'samples': row.samples,
            'color_space': row.color_space}


def map_default_overrides(context, map_type):
    """Field overrides for apply_type_defaults, or None to keep shipped
    defaults (add-on not registered, or the type has no seeded row)."""
    prefs = addon_preferences(context)
    return overrides_from_prefs(prefs, map_type) if prefs is not None else None


def aliases_from_prefs(prefs):
    return {a.keyword.casefold(): a.channel
            for a in prefs.import_aliases if a.keyword}


def import_alias_map(context):
    """User keywords -> channel ids for parse_texture_file, or None."""
    prefs = addon_preferences(context)
    return aliases_from_prefs(prefs) if prefs is not None else None


class BakeLabPreferences(AddonPreferences):
    bl_idname = _ROOT_PACKAGE

    gpu_backend: EnumProperty(
        name = 'GPU Backend',
        description = 'Cycles compute backend used when Device is "GPU Compute" - '
                      'Auto keeps whatever Cycles preferences say',
        items = gpu_backend_items,
        update = _gpu_backend_update,
    )
    map_defaults      : CollectionProperty(type = BakeLabMapDefault)
    map_defaults_index: IntProperty()
    import_aliases    : CollectionProperty(type = BakeLabImportAlias)
    import_aliases_index: IntProperty()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'gpu_backend')
        if cycles_preferences(context) is None:
            layout.label(text = 'Cycles is not enabled', icon = 'ERROR')

        seed_map_defaults(self)
        box = layout.box()
        box.label(text = 'Map defaults used by Add Map / auto-add')
        row = box.row()
        row.template_list("BAKELAB_DEFAULT_UL_list", "",
                          self, "map_defaults", self, "map_defaults_index",
                          rows = 5)
        if 0 <= self.map_defaults_index < len(self.map_defaults):
            entry = self.map_defaults[self.map_defaults_index]
            col = box.column(align = True)
            col.prop(entry, 'img_name')
            col.prop(entry, 'samples')
            col.prop(entry, 'color_space')
        box.operator("bakelab.reset_map_defaults", icon = 'FILE_REFRESH')

        box = layout.box()
        box.label(text = 'Texture-import aliases - extra filename suffixes')
        row = box.row()
        row.template_list("BAKELAB_ALIAS_UL_list", "",
                          self, "import_aliases", self, "import_aliases_index",
                          rows = 3)
        ops = row.column(align = True)
        ops.operator("bakelab.import_alias_add", icon = 'ADD', text = "")
        ops.operator("bakelab.import_alias_remove", icon = 'REMOVE', text = "")
        if 0 <= self.import_aliases_index < len(self.import_aliases):
            entry = self.import_aliases[self.import_aliases_index]
            box.prop(entry, 'keyword')
            box.prop(entry, 'channel')
