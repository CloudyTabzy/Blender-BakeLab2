from bpy.types import AddonPreferences
from bpy.props import EnumProperty

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


def _gpu_backend_update(self, context):
    apply_gpu_backend(self, context)


class BakeLabPreferences(AddonPreferences):
    bl_idname = _ROOT_PACKAGE

    gpu_backend: EnumProperty(
        name = 'GPU Backend',
        description = 'Cycles compute backend used when Device is "GPU Compute" - '
                      'Auto keeps whatever Cycles preferences say',
        items = gpu_backend_items,
        update = _gpu_backend_update,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'gpu_backend')
        if cycles_preferences(context) is None:
            layout.label(text = 'Cycles is not enabled', icon = 'ERROR')
