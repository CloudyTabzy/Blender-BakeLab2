from bpy.types import PropertyGroup
from bpy.props import (
            IntProperty,
            EnumProperty,
            BoolProperty,
            FloatProperty,
            StringProperty
        )

MAP_TYPE_ITEMS = (
                ('Albedo',      'Albedo','Base color of the materials, without lighting'),
                ('Normal',      'Normal','Surface normals; use Non-Color, and 16-bit PNG or EXR against banding'),
                ('Glossy',      'Glossy','Glossy (specular) lighting pass; lit by the scene'),
                ('Roughness',   'Roughness','Microfacet roughness of the materials'),
                ('Emission',    'Emission','Emitted light of the materials'),
                ('Diffuse',     'Diffuse','Diffuse lighting pass; lit by the scene'),
                ('Subsurface',  'Subsurface','Subsurface Weight of the material'),
                ('Transmission','Transmission','Transmission lighting pass; lit by the scene'),
                ('Alpha',       'Alpha','Opacity of the material (wired Alpha inputs)'),
                ('Metallic',    'Metallic','Metalness of the material'),
                ('MatID',       'Material ID','A flat, distinct color per material'),
                ('Shadow',      'Shadow','Shadows cast by the scene lights'),
                ('Environment', 'Environment','World background as seen in the surface normal direction'),
                ('UV',          'UV','UV coordinates as red/green'),
                ('UVGrid',      'UV Grid','UV test grid - stretching shows as distorted squares'),
                ('ColorGrid',   'Color Grid','Color grid test pattern through the UV map'),
                ('Position',    'Position','World-space surface position; EXR keeps the full range'),
                None,
                ('Combined',    'Combined','Full render of the surface - lighting included; needs many samples'),
                ('CustomPass',  'Custom Pass','Any shader input by name (e.g. Specular IOR Level, Coat Weight)'),
                ('AO',          'Ambient Occlusion','Occlusion by nearby geometry; needs 32+ samples for a clean result'),
                ('AORM',        'AORM','Packed map: AO to red, Roughness to green, Metallic to blue'),
                ('Displacement','Displacement','Material displacement height; use 32 bit float and EXR')
        )

# Maps holding raw values rather than colors: the view transform must not
# touch them, and lossy compression distorts them
DATA_MAP_TYPES = {'Normal', 'Roughness', 'Metallic', 'AO', 'AORM', 'Alpha',
                  'Displacement', 'Position', 'Subsurface', 'UV'}
# Maps whose value comes from ray tracing, so few samples show as noise
NOISY_MAP_TYPES = {'AO', 'AORM', 'Combined', 'Shadow', 'Diffuse', 'Glossy',
                   'Transmission', 'Environment'}
NOISY_MIN_SAMPLES = 16
# Beyond this many pixels (width x height x anti-alias^2) a bake needs
# gigabytes of memory: 16k x 16k at 32-bit float RGBA is 4 GiB
LARGE_BAKE_PIXELS = 8192 * 8192

# Shared with the Add Map operator so both show the same advice
FILE_FORMAT_ITEMS = (
    ('PNG',      'PNG',     'Lossless; 8 or 16 bits, the usual choice'),
    ('JPEG',     'JPEG',    'Lossy and 8-bit only: small files, but no alpha and '
                            'artifacts on normal and other data maps'),
    ('OPEN_EXR', 'OpenEXR', 'Floating point: keeps values outside 0-1 '
                            '(Displacement, Position) and avoids banding'),
)
FLOAT_DEPTH_DESC = ('Bake into a 32-bit float buffer instead of 8-bit. Needed for '
                    'Displacement and Position, and avoids banding in normal maps')
UDIM_DESC = ('Bake one tile per UV tile (1001+). Tiles bake at final size; '
             'anti-aliasing is unavailable for UDIM maps')
PNG_DEPTH_ITEMS = (('8',  '8 bit',  '256 levels per channel; fine for color maps'),
                   ('16', '16 bit', '65536 levels; avoids banding in normal and '
                                    'height maps, twice the file size'))
PNG_COMPRESSION_DESC = ('Lossless zlib level: higher is smaller but slower to save; '
                        'image quality is identical')
JPG_QUALITY_DESC = 'Higher keeps more detail and makes larger files; 90+ for textures'
EXR_DEPTH_ITEMS = (('16', 'Half (16)', 'Half float: plenty for color and normals, half the size'),
                   ('32', 'Full (32)', 'Full float: needed for Position and precise displacement'))
EXR_CODEC_DESC = 'Compression; ZIP and PIZ are lossless, lossy codecs alter data maps'
_EXR_CODECS = (
    ('NONE', 'None',           'No compression'),
    ('PXR24','Pxr24 (lossy)',  'Lossy for 32-bit float, lossless for half'),
    ('ZIP',  'ZIP (lossless)', 'Lossless, good general choice'),
    ('PIZ',  'PIZ (lossless)', 'Lossless, best for noisy images'),
    ('RLE',  'RLE (lossless)', 'Lossless run-length, fast, only for flat images'),
    ('ZIPS', 'ZIPS (lossless)','Lossless, per scanline'),
)
EXR_CODEC_32_ITEMS = _EXR_CODECS + (('DWAA', 'DWAA (lossy)', 'Lossy, small files'),)
EXR_CODEC_16_ITEMS = _EXR_CODECS + (
    ('B44',  'B44 (lossy)',  'Lossy, fixed ratio'),
    ('B44A', 'B44A (lossy)', 'Lossy, fixed ratio, smaller on flat areas'),
    ('DWAA', 'DWAA (lossy)', 'Lossy, small files'),
)
NORMAL_FORMAT_ITEMS = (
    ('OPENGL',  'OpenGL (+Y)',  'Green points up: Blender, Unity, Godot, Substance default'),
    ('DIRECTX', 'DirectX (-Y)', 'Green points down: Unreal Engine, 3ds Max'),
)

class BakeLabMap(PropertyGroup):
    enabled : BoolProperty(name = '', default = True,
                           description = 'Bake this map')
    type : EnumProperty(
            name = 'Type',
            items =  MAP_TYPE_ITEMS,
            default = 'Albedo'
        )
    pass_name   : StringProperty(
        name = 'Property name',
        description = 'Shader input(s) to bake, comma separated and in priority '
                      'order; the first one a node has is used',
        default = 'Color,Base Color,Albedo,Paint Color')
    deep_search : BoolProperty(
        name = 'Deep Search',
        description = 'Search inside of node groups',
        default = True
    )

    img_name : StringProperty(
        name = 'Image name',
        description = "Name of the baked image; '*' is replaced by the object, "
                      "job or image name. Maps sharing a name overwrite each other",
        default = '*')

    clear_img: BoolProperty(
        name = 'Clear image',
        description = 'Start from a new transparent image. Off keeps an existing '
                      'image and bakes over it, preserving pixels outside the UVs',
        default = True
    )

    use_udim: BoolProperty(
        name = 'UDIM',
        description = UDIM_DESC,
        default = False
    )

    width  : IntProperty(
                name = 'Width',
                description = 'Image width in pixels (before anti-aliasing)',
                default = 1024 ,
                min = 1, soft_max = 16384
            )
    height : IntProperty(
                name = 'Height',
                description = 'Image height in pixels (before anti-aliasing)',
                default = 1024,
                min = 1, soft_max = 16384
            )
    target_width  : IntProperty(name = 'Target Width')
    target_height : IntProperty(name = 'Target Height')
    image_scale : FloatProperty(
                name = 'Image Scale',
                description = 'Multiplier on the adaptive size, e.g. 0.5 for a '
                              'half-resolution roughness map',
                default = 1,
                min = 0
            )
    aa_override : IntProperty(
                name = 'Anti-alias Override',
                description = 'Anti-aliasing for this map only (0 = use the global '
                              'value). Keep Normal maps at 1: averaging normals '
                              'shortens them',
                default = 0,
                min = 0, soft_max = 8
            )
    final_aa : IntProperty(name = 'Final Anti-alias')


    float_depth: BoolProperty(name = '32 bit float', description = FLOAT_DEPTH_DESC,
                              default = False)
    color_space : EnumProperty(
                name = 'Color Space',
                description = ('Color space of the baked image; data maps (Normal, '
                               'Roughness, etc.) should use Non-Color. The exact '
                               'name is matched against the active color management '
                               'config'),
                items =  (('sRGB','sRGB','Colors meant to be seen: albedo, emission, lighting'),
                        ('Non-Color','Non-Color','Raw values: normal, roughness, metallic, AO, height')),
                default = 'sRGB'
            )
    file_format : EnumProperty(
                name = 'Format',
                description = 'File format of the saved image',
                default = 'PNG',
                items =  FILE_FORMAT_ITEMS
            )
    png_channels : EnumProperty(
                name = 'Color',
                description = 'Channels written to the file',
                items =  (('BW','BW','Grayscale, one channel'),
                        ('RGB','RGB','Color, no alpha'),
                        ('RGBA','RGBA','Color with alpha')),
                default = 'RGB'
            )
    png_depth : EnumProperty(
                name = 'Depth',
                description = 'Color depth per channel',
                items =  PNG_DEPTH_ITEMS,
                default = '8'
            )
    png_compression : IntProperty(
                name = 'Compression',
                default = 15,
                description = PNG_COMPRESSION_DESC,
                min = 0, max = 100
            )
    jpg_channels : EnumProperty(
                name = 'Color',
                description = 'Channels written to the file',
                items =  (('BW','BW','Grayscale, one channel'),
                        ('RGB','RGB','Color')),
                default = 'RGB'
            )
    jpg_quality : IntProperty(
                name = 'Quality',
                default = 90,
                description = JPG_QUALITY_DESC,
                min = 0, max = 100
            )
    exr_channels : EnumProperty(
                name = 'Color',
                description = 'Channels written to the file',
                items =  (('RGB','RGB','Color, no alpha'),
                        ('RGBA','RGBA','Color with alpha')),
                default = 'RGB'
            )
    exr_depth : EnumProperty(
                name = 'Color Depth',
                description = 'Bits depth per channel',
                items =  EXR_DEPTH_ITEMS,
                default = '32'
            )
    exr_codec_32 : EnumProperty(
                name = 'Codec',
                description = EXR_CODEC_DESC,
                items =  EXR_CODEC_32_ITEMS,
                default = 'ZIP'
            )
    exr_codec_16 : EnumProperty(
                name = 'Codec',
                description = EXR_CODEC_DESC,
                items =  EXR_CODEC_16_ITEMS,
                default = 'ZIP'
            )
    samples : IntProperty(
                name = 'Samples',default = 6,
                description = 'Cycles samples per pixel. Material maps (Albedo, '
                              'Roughness...) need 1-4; AO, Combined and lighting '
                              'passes need 16-64+ or they come out noisy',
                min = 1, soft_max = 1024
            )

    normal_space : EnumProperty(
                name = 'Normal Space',
                description = 'Space of the baked normals',
                default = 'TANGENT',
                items =  (
                    ('TANGENT','Tangent Space','Relative to the surface; deforms '
                                               'with the mesh, the usual choice'),
                    ('OBJECT', 'Object Space','Relative to the object; only for '
                                              'rigid, non-deforming meshes')
                )
            )
    normal_format : EnumProperty(
                name = 'Normal Format',
                description = 'Green channel convention of the target application',
                default = 'OPENGL',
                items = NORMAL_FORMAT_ITEMS
            )

    bake_direct            : BoolProperty(name = 'Direct',       default = False,
                                          description = 'Include light arriving straight from lamps')
    bake_indirect          : BoolProperty(name = 'Indirect',     default = False,
                                          description = 'Include light bounced off other surfaces')
    bake_color             : BoolProperty(name = 'Color',        default = True,
                                          description = 'Include the material color '
                                                        '(off with a light: lighting only)')

    combined_direct            : BoolProperty(name = 'Direct',       default = True,
                                              description = 'Include direct lighting')
    combined_indirect          : BoolProperty(name = 'Indirect',     default = True,
                                              description = 'Include indirect (bounced) lighting')

    combined_diffuse           : BoolProperty(name = 'Diffuse',      default = True,
                                              description = 'Include diffuse contribution')
    combined_glossy            : BoolProperty(name = 'Glossy',       default = True,
                                              description = 'Include glossy contribution')
    combined_transmission      : BoolProperty(name = 'Transmission', default = True,
                                              description = 'Include transmission contribution')
    #combined_subsurface        : BoolProperty(name = 'Subsurface',   default = True)
    #combined_ambient_occlusion : BoolProperty(name = 'AO',           default = True)
    combined_emit              : BoolProperty(name = 'Emit',         default = True,
                                              description = 'Include emission')


MAP_TYPE_DEFAULTS = {
    'Albedo':       {'img_name': '*_t',      'samples': 4},
    'Combined':     {'img_name': '*_c',      'samples': 64},
    'Normal':       {'img_name': '*_n',      'samples': 16,
                     'color_space': 'Non-Color', 'aa_override': 1},
    'Displacement': {'img_name': '*_h',      'samples': 4,
                     'color_space': 'Non-Color'},
    'AO':           {'img_name': '*_ao',     'samples': 64,
                     'color_space': 'Non-Color'},
    'AORM':         {'img_name': '*_aorm',   'samples': 64,
                     'color_space': 'Non-Color'},
    'Shadow':       {'img_name': '*_sh',     'samples': 32},
    'Glossy':       {'img_name': '*_s',      'samples': 8},
    'Roughness':    {'img_name': '*_r',      'samples': 4,
                     'color_space': 'Non-Color'},
    'Diffuse':      {'img_name': '*_d',      'samples': 8},
    'Emission':     {'img_name': '*_e',      'samples': 4},
    'Transmission': {'img_name': '*_a',      'samples': 8},
    'Alpha':        {'img_name': '*_alpha',  'samples': 4,
                     'color_space': 'Non-Color'},
    'Metallic':     {'img_name': '*_m',      'samples': 4,
                     'color_space': 'Non-Color'},
    'MatID':        {'img_name': '*_id',     'samples': 1,
                     'color_space': 'Non-Color'},
    'Position':     {'img_name': '*_pos',    'samples': 1,
                     'color_space': 'Non-Color', 'file_format': 'OPEN_EXR'},
    'UV':           {'img_name': '*_uv',     'samples': 1,
                     'color_space': 'Non-Color'},
    'UVGrid':       {'img_name': '*_uvgrid', 'samples': 1},
    'ColorGrid':    {'img_name': '*_cgrid',  'samples': 1},
    'Environment':  {'img_name': '*_env',    'samples': 16},
    'Subsurface':   {'img_name': '*_sss',    'samples': 4,
                     'color_space': 'Non-Color'},
    'CustomPass':   {'img_name': '*_pass',   'samples': 4,
                     'color_space': 'Non-Color'},
}


def apply_type_defaults(item, map_type, overrides=None):
    """Type-specific defaults for a bake-map item, shared by the Add Map
    operator and the default map the baker inserts when none is configured.
    `overrides` (e.g. from the addon preferences' map-defaults table) wins
    over the shipped values for any field it names."""
    item.type = map_type
    spec = dict(MAP_TYPE_DEFAULTS.get(map_type, {}))
    if overrides:
        spec.update(overrides)
    for field, value in spec.items():
        setattr(item, field, value)


def map_advice(item, props):
    """Quality advice for one bake map as (level, text) pairs, terse enough
    for a sidebar label (tooltips carry the detail); level is
    'caution' (the result will likely be wrong or degraded) or 'info' (a
    better setting exists). Shared by the panel, the preflight checklist
    and the baker, so a headless run reports what the UI shows."""
    advice = []
    saving = props.save_or_pack == 'SAVE'
    if item.type in DATA_MAP_TYPES and item.color_space == 'sRGB':
        advice.append(('caution', 'Data map: use Non-Color'))
    if saving and item.file_format == 'JPEG' and item.type in DATA_MAP_TYPES:
        advice.append(('caution', 'JPEG distorts data maps'))
    if item.type in NOISY_MAP_TYPES and item.samples < NOISY_MIN_SAMPLES:
        advice.append(('info', 'Noisy: use %d+ samples' % NOISY_MIN_SAMPLES))
    if item.type in {'Displacement', 'Position'}:
        if not item.float_depth:
            advice.append(('info', 'Needs 32 bit float'))
        if saving and item.file_format != 'OPEN_EXR':
            advice.append(('info', 'Needs EXR for full range'))
    if item.type == 'Normal':
        if (item.aa_override or props.anti_alias) > 1 and not item.use_udim:
            advice.append(('info', 'AA shortens normals'))
        if saving and item.file_format == 'PNG' and item.png_depth == '8':
            advice.append(('info', '8-bit PNG: try 16 bit'))
    if props.image_size == 'FIXED':
        aa = 1 if item.use_udim else (item.aa_override or props.anti_alias)
        if item.width * item.height * aa * aa > LARGE_BAKE_PIXELS:
            advice.append(('caution', '%dx%d: GBs of RAM'
                                      % (item.width * aa, item.height * aa)))
    return advice
