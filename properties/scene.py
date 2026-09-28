import bpy
from os.path import expanduser

from bpy.types import PropertyGroup
from bpy.props import (
            IntProperty,
            EnumProperty,
            BoolProperty,
            FloatProperty,
            StringProperty,
            PointerProperty
        )
from ..utils import compat

# Only assign when the value changes: assigning a property runs its update
# callback again, so unconditional assignments here recurse until Blender crashes
def updateAdaptiveImageMinSize(self, context):
    if self.image_min_size > self.image_max_size:
        self.image_min_size = self.image_max_size

def updateAdaptiveImageMaxSize(self, context):
    if self.image_max_size < self.image_min_size:
        self.image_max_size = self.image_min_size

def updateSavePath(self, context):
    if bpy.data.is_saved:
        abs_path = bpy.path.abspath(self.save_path)
        if abs_path != self.save_path:
            self.save_path = abs_path

def output_folder_problem(props):
    """Why the Save output folder cannot be used, or None. A '//' path in
    an unsaved file would resolve against Blender's working directory."""
    if not props.save_path.strip():
        return 'No output folder set'
    if props.save_path.startswith('//') and not bpy.data.is_saved:
        return 'Save .blend for // folder'
    return None

class BakeLabProperties(PropertyGroup):
    bake_state: EnumProperty(
            items = (
                ("NONE",   "None",   ""),
                ("BAKING", "Baking", ""),
                ("BAKED",  "Baked",  "")
            ),
            default = "NONE"
        )
    bake_mode: EnumProperty(
            name = "Mode",
            description = 'Baking mode',
            items = (
                ("INDIVIDUAL", "Individual Objects",
                 "One image set per object, named after it", "PIVOT_INDIVIDUAL", 1),
                ("ALL_TO_ONE", "All To One Image",
                 "One shared image set (atlas) for all objects; their UVs must "
                 "not overlap", "PROP_ON", 2),
                ("TO_ACTIVE",  "Selected to active",
                 "Project the selected (high-poly) objects onto the active "
                 "(low-poly) one; only the active object needs UVs", "PIVOT_ACTIVE", 3)
            ),
            default = "INDIVIDUAL"
        )
    batch_source : EnumProperty(
            name = 'Batch',
            description = 'What forms the bake jobs; each job runs the bake mode on its object set',
            items = (
                ('SELECTION',  'Selection',   'One job: the current selection'),
                ('MATERIAL',   'By Material', 'One job per material on the selected objects'),
                ('COLLECTION', 'Collection',  'One job per collection'),
                ('SCENE',      'Scene',       'One job: every mesh object in the scene'),
                ('NAME_PAIRS', 'High-Low Pairs',
                               'One job per *_low mesh in the scene, baked Selected to Active '
                               'from its matching *_high* sources'),
                ('TEXTURE_SETS', 'Texture Sets',
                               'One job per enabled texture set, baked All To One into '
                               'maps named after the set')
            ),
            default = 'SELECTION'
        )
    batch_collection : PointerProperty(
            type = bpy.types.Collection,
            name = 'Collection',
            description = 'Collection to bake; empty = every child collection of the scene collection'
        )
    batch_include_children : BoolProperty(
            name = 'Include Child Collections',
            description = 'Also make one job per nested collection',
            default = True
        )
    cage_extrusion : FloatProperty(
            name = 'Cage Extrusion', default = 0.05,
            description = 'Distance the target surface is pushed outward to cast '
                          'rays inward; raise it when parts of the high-poly are '
                          'missing, lower it when neighboring parts bleed in',
            min = 0, soft_max = 1
        )
    max_ray_distance : FloatProperty(
            name = 'Max Ray Distance', default = 0.0,
            description = 'Maximum ray distance for selected to active baking (0 = unlimited)',
            min = 0, soft_max = 1
        )
    pre_join_mesh : BoolProperty(
            name = 'Pre-Join Meshes', default = False,
            description = 'Create one merged mesh and bake to it using ray-tracing. '
                          'Keeps overlapping objects from baking over each other, '
                          'at the cost of a projection (Cage Extrusion) step',
        )
    image_size : EnumProperty(
            name = 'Image Size',
            items = (
                ('FIXED',    'Fixed',    "Each map sets its own width and height"),
                ('ADAPTIVE', 'Adaptive', "Size from the objects' surface area and "
                                         "Texels Per Unit, for consistent texel density")
            ),
            default = 'FIXED'
        )
    adaptive_image_Settings : BoolProperty(
            name = '',
            default = True
        )
    texel_per_unit : FloatProperty(
            name = 'Texels Per Unit',
            description = 'Pixels per scene unit (meter) of surface; 512-1024 for '
                          'hero assets, 100-256 for background props',
            default = 100,
            min = 0
        )
    image_min_size    : IntProperty(
            name = 'Min Size',
            description = 'Smallest adaptive image size in pixels',
            default = 32,
            min = 1,
            update=updateAdaptiveImageMaxSize
        )
    image_max_size    : IntProperty(
            name = 'Max Size',
            description = 'Largest adaptive image size in pixels',
            default = 2048,
            min = 1,
            update=updateAdaptiveImageMinSize
        )
    round_adaptive_image : BoolProperty(
        name = 'Round to power of two',
        description = 'Round adaptive sizes to 256, 512, 1024... which game '
                      'engines mipmap and compress best',
        default = True
    )
    margin_type : EnumProperty(
            name = 'Margin Type',
            description = 'How the margin is filled',
            items = (
                ('ADJACENT_FACES', 'Adjacent Faces',
                 'Fill with pixels from the neighboring faces across the seam; '
                 'hides seams best'),
                ('EXTEND', 'Extend', 'Repeat the edge pixels outward; the '
                                     'classic, faster fill'),
            ),
            default = 'ADJACENT_FACES'
        )
    anti_alias : IntProperty(
            name = 'Anti-aliasing', default = 1,
            description = 'Bake at N times the size and scale down, smoothing '
                          'jagged edges (1 = off). Costs N x N the time and memory',
            min = 1, soft_max = 8
        )
    bake_margin    : IntProperty(
            name = 'Bake Margin',
            description = 'Pixels the result is extended past UV island edges, so '
                          'mipmaps and filtering do not pull in the background. '
                          '4-8 for 1K, 16 for 4K',
            default = 4,
            min = 0,
            soft_max = 64
        )
    global_image_name  : StringProperty(
            name = 'Image Name',
            description = "Replaces '*' in the map image names when all objects "
                          "bake into one image set",
            default = "Atlas",
        )
    compute_device : EnumProperty(
            name = 'Device',
            description = 'Device Cycles bakes on',
            items =  (
                ('GPU','GPU Compute','Much faster when a GPU is set up in '
                                     'Preferences > System; falls back to the CPU otherwise'),
                ('CPU','CPU','Always available; slower')
            )
        )
    save_or_pack : EnumProperty(
                name  = 'Output',
                description = 'Where baked images go',
                items =  (
                    ('PACK','Pack','Keep images inside the .blend file'),
                    ('SAVE','Save','Write image files to the output folder')
                ),
                default = 'PACK'
            )
    create_folder : BoolProperty(
        name="Create folder",
        description="Automatically creates a folder named after the object(s)",
        default = True
        )
    folder_name  : StringProperty(
            name = 'Folder name',
            description = 'Subfolder for a single All To One bake; batches '
                          'use one folder per job',
            default = "Selection",
        )
    save_path : StringProperty(
                default=expanduser("~"),
                name="Folder",
                description="Output folder for saved images",
                subtype="DIR_PATH",
                options=compat.PATH_PROPERTY_OPTIONS,
                update=updateSavePath
            )
    show_bake_settings : BoolProperty(name = '', default = False)
    show_map_settings  : BoolProperty(name = '', default = False)
    show_file_settings : BoolProperty(name = '', default = False)

    apply_only_selected : BoolProperty(
        name = 'Apply only to Selected',
        description = 'Only change the selected objects when applying results',
        default = True
    )
    make_single_user : BoolProperty(
        name = 'Make single user',
        description = 'Give each object its own mesh copy first, so shared '
                      'meshes elsewhere keep their materials',
        default = True
    )
    # Display
    baking_obj_count : IntProperty(
            name = 'Baking object count',
            default = 0
        )
    baking_obj_index : IntProperty(
            name = 'Current baking object',
            default = 0
        )
    baking_obj_name : StringProperty(
            name = 'Current baking object',
            default = ""
        )
    baking_map_count : IntProperty(
            name = 'Baking map count',
            default = 0
        )
    baking_map_index : IntProperty(
            name = 'Current baking map',
            default = 0
        )
    baking_map_type : StringProperty(
            name = 'Current baking map type',
            default = ""
        )
    baking_map_name : StringProperty(
            name = 'Current baking image',
            default = ""
        )
    baking_map_size : StringProperty(
            name = 'Current baking size',
            default = ""
        )
    baking_job_count : IntProperty(
            name = 'Baking job count',
            default = 0
        )
    baking_job_index : IntProperty(
            name = 'Current baking job',
            default = 0
        )
    baking_job_name : StringProperty(
            name = 'Current baking job',
            default = ""
        )
