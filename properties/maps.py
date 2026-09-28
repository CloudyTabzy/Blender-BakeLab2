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
