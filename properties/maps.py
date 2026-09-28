from bpy.types import PropertyGroup
from bpy.props import (
            IntProperty,
            EnumProperty,
            BoolProperty,
            FloatProperty,
            StringProperty
        )

MAP_TYPE_ITEMS = (
                ('Albedo',      'Albedo',''),
                ('Normal',      'Normal',''),
                ('Glossy',      'Glossy',''),
                ('Roughness',   'Roughness',''),
                ('Emission',    'Emission',''),
                ('Diffuse',     'Diffuse',''),
                ('Subsurface',  'Subsurface','Subsurface Weight of the material'),
                ('Transmission','Transmission',''),
                ('Shadow',      'Shadow',''),
                ('Environment', 'Environment',''),
                ('UV',          'UV',''),
                None,
                ('Combined',    'Combined',''),
                ('CustomPass',  'Custom Pass',''),
                ('AO',          'Ambient Occlusion',''),
                ('Displacement','Displacement','')
        )

class BakeLabMap(PropertyGroup):
    enabled : BoolProperty(name = '', default = True)
    type : EnumProperty(
            name = 'Type',
            items =  MAP_TYPE_ITEMS,
            default = 'Albedo'
        )
    pass_name   : StringProperty(name = 'Property name', default = 'Color,Base Color,Albedo,Paint Color')
    deep_search : BoolProperty(
        name = 'Deep Search',
        description = 'Search inside of node groups',
        default = True
    )

    img_name : StringProperty(name = 'Image name', default = '*')

    clear_img: BoolProperty(
        name = 'Clear image',
        description = 'Clear image before baking',
        default = True
    )

    use_udim: BoolProperty(
        name = 'UDIM',
        description = 'Bake one tile per UV tile (1001+). Tiles bake at final '
                      'size; anti-aliasing is unavailable for UDIM maps',
        default = False
    )

    width  : IntProperty(
                name = 'Width',
                default = 1024 ,
                min = 1, soft_max = 16384
            )
    height : IntProperty(
                name = 'Height',
                default = 1024,
                min = 1, soft_max = 16384
            )
    target_width  : IntProperty(name = 'Target Width')
    target_height : IntProperty(name = 'Target Height')
    image_scale : FloatProperty(
                name = 'Image Scale',
                default = 1,
                min = 0
            )
    aa_override : IntProperty(
                name = 'Anti-alias Override',
                description = 'Use individual anti-aliasing (0 to use global value)',
                default = 0,
                min = 0, soft_max = 8
            )
    final_aa : IntProperty(name = 'Final Anti-alias')


    float_depth: BoolProperty(name = '32 bit float', default = False)
    color_space : EnumProperty(
                name = 'Color Space',
                description = ('Color space of the baked image; data maps (Normal, '
                               'Roughness, etc.) should use Non-Color. The exact '
                               'name is matched against the active color management '
                               'config'),
                items =  (('sRGB','sRGB',''),
                        ('Non-Color','Non-Color','')),
                default = 'sRGB'
            )
    file_format : EnumProperty(
                name = 'Format',
                default = 'PNG',
                items =  (
                    ('PNG',  'PNG', ''),
                    ('JPEG', 'JPEG', ''),
                    ('OPEN_EXR',  'OpenEXR', '')
                )
            )
    png_channels : EnumProperty(
                name = 'Color',
                items =  (('BW','BW',''),
                        ('RGB','RGB',''),
                        ('RGBA','RGBA','')),
                default = 'RGB'
            )
    png_depth : EnumProperty(
                name = 'Depth',
                description = 'Color Depth',
                items =  (('8','8 byte',''),
                        ('16','16 byte','')),
                default = '8'
            )
    png_compression : IntProperty(
                name = 'Compression',
                default = 15,
                description = 'Compression',
                min = 0, max = 100
            )
    jpg_channels : EnumProperty(
                name = 'Color',
                items =  (('BW','BW',''),
                        ('RGB','RGB','')),
                default = 'RGB'
            )
    jpg_quality : IntProperty(
                name = 'Quality',
                default = 90,
                description = 'Quality',
                min = 0, max = 100
            )
    exr_channels : EnumProperty(
                name = 'Color',
                items =  (('RGB','RGB',''),
                        ('RGBA','RGBA','')),
                default = 'RGB'
            )
    exr_depth : EnumProperty(
                name = 'Color Depth',
                description = 'Bits depth per channel',
                items =  (('16', 'Half (16)',''),
                        ('32',   'Full (32)','')),
                default = '32'
            )
    exr_codec_32 : EnumProperty(
                name = 'Codec',
                items =  (
                    ('NONE', 'None',           ''),
                    ('PXR24','Pxr24 (lossy)',  ''),
                    ('ZIP',  'ZIP (lossless)', ''),
                    ('PIZ',  'PIZ (lossless)', ''),
                    ('RLE',  'RLE (lossless)', ''),
                    ('ZIPS', 'ZIPS (lossless)',''),
                    ('DWAA', 'DWAA (lossy)',   '')
                ),
                default = 'ZIP'
            )
    exr_codec_16 : EnumProperty(
                name = 'Codec',
                items =  (
                    ('NONE', 'None',           ''),
                    ('PXR24','Pxr24 (lossy)',  ''),
                    ('ZIP',  'ZIP (lossless)', ''),
                    ('PIZ',  'PIZ (lossless)', ''),
                    ('RLE',  'RLE (lossless)', ''),
                    ('ZIPS', 'ZIPS (lossless)',''),
                    ('B44',  'B44 (lossy)',   ''),
                    ('B44A', 'B44A (lossy)',   ''),
                    ('DWAA', 'DWAA (lossy)',   '')
                ),
                default = 'ZIP'
            )
    samples : IntProperty(
                name = 'Samples',default = 6,
                description = 'Amount of Samples',
                min = 1, soft_max = 1024
            )

    normal_space : EnumProperty(
                name = 'Normal Space',
                default = 'TANGENT',
                items =  (
                    ('TANGENT','Tangent Space',''),
                    ('OBJECT', 'Object Space','')
                )
            )

    bake_direct            : BoolProperty(name = 'Direct',       default = False)
    bake_indirect          : BoolProperty(name = 'Indirect',     default = False)
    bake_color             : BoolProperty(name = 'Color',        default = True)

    combined_direct            : BoolProperty(name = 'Direct',       default = True)
    combined_indirect          : BoolProperty(name = 'Indirect',     default = True)

    combined_diffuse           : BoolProperty(name = 'Diffuse',      default = True)
    combined_glossy            : BoolProperty(name = 'Glossy',       default = True)
    combined_transmission      : BoolProperty(name = 'Transmission', default = True)
    #combined_subsurface        : BoolProperty(name = 'Subsurface',   default = True)
    #combined_ambient_occlusion : BoolProperty(name = 'AO',           default = True)
    combined_emit              : BoolProperty(name = 'Emit',         default = True)


def apply_type_defaults(item, map_type):
    """Type-specific defaults for a bake-map item, shared by the Add Map
    operator and the default map the baker inserts when none is configured."""
    item.type = map_type
    if map_type == 'Albedo':
        item.img_name = '*_t'
        item.samples  = 4
    if map_type == 'Combined':
        item.img_name = '*_c'
        item.samples  = 64
    if map_type == 'Normal':
        item.img_name = '*_n'
        item.samples  = 16
        item.color_space = 'Non-Color'
        item.aa_override = 1 #Because cycles has buildin anti-aliasing for normals
    if map_type == 'Displacement':
        item.img_name = '*_h'
        item.samples  = 4
        item.color_space = 'Non-Color'
    if map_type == 'AO':
        item.img_name = '*_ao'
        item.samples  = 64
        item.color_space = 'Non-Color'
    if map_type == 'Shadow':
        item.img_name = '*_sh'
        item.samples  = 32
    if map_type == 'Glossy':
        item.img_name = '*_s'
        item.samples  = 8
    if map_type == 'Roughness':
        item.img_name = '*_r'
        item.samples  = 4
        item.color_space = 'Non-Color'
    if map_type == 'Diffuse':
        item.img_name = '*_d'
        item.samples  = 8
    if map_type == 'Emission':
        item.img_name = '*_e'
        item.samples  = 4
    if map_type == 'Transmission':
        item.img_name = '*_a'
        item.samples  = 8
    if map_type == 'UV':
        item.img_name = '*_uv'
        item.samples  = 1
    if map_type == 'Environment':
        item.img_name = '*_env'
        item.samples  = 16
    if map_type == 'Subsurface':
        item.img_name = '*_sss'
        item.samples  = 4
        item.color_space = 'Non-Color'
    if map_type == 'CustomPass':
        item.img_name = '*_pass'
        item.samples  = 4
        item.color_space = 'Non-Color'
