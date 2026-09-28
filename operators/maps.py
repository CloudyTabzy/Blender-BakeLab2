from bpy.types import (
            Operator
        )
from bpy.props import (
            IntProperty,
            EnumProperty,
            BoolProperty,
            FloatProperty
        )
from ..properties.maps import (
            MAP_TYPE_ITEMS,
            FILE_FORMAT_ITEMS,
            FLOAT_DEPTH_DESC,
            UDIM_DESC,
            PNG_DEPTH_ITEMS,
            PNG_COMPRESSION_DESC,
            JPG_QUALITY_DESC,
            EXR_DEPTH_ITEMS,
            EXR_CODEC_DESC,
            EXR_CODEC_32_ITEMS,
            EXR_CODEC_16_ITEMS,
            apply_type_defaults
        )
from ..properties.prefs import (
            addon_preferences,
            map_default_overrides,
            seed_map_defaults
        )

class BakeLabAddMapItem(Operator):
    """Add a new bake map"""
    bl_idname = "bakelab.newmapitem"
    bl_label = "Add bake map"
    bl_options = {'REGISTER','UNDO'}

    type: EnumProperty(
            name = 'Type',
            items = MAP_TYPE_ITEMS,
            default = 'Albedo'
        )
    width: IntProperty(name = 'Width',default = 1024,
                       description = 'Image width in pixels (before anti-aliasing)',
                       min = 1, soft_max = 16384)
    height: IntProperty(name = 'Height',default = 1024,
                        description = 'Image height in pixels (before anti-aliasing)',
                        min = 1, soft_max = 16384)
    image_scale: FloatProperty(name = 'Image Scale',default = 1,
                               description = 'Multiplier on the adaptive size',
                               min = 0)

    float_depth: BoolProperty(name = '32 bit float', description = FLOAT_DEPTH_DESC,
                              default = False)
    use_udim: BoolProperty(
        name = 'UDIM',
        description = UDIM_DESC,
        default = False
    )
    file_format : EnumProperty(
                name = 'Format',
                description = 'File format of the saved image',
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

    def calcItemSettings(self,context,item):
        apply_type_defaults(item, self.type,
                            overrides=map_default_overrides(context, self.type))

    def draw(self,context):
        layout = self.layout
        props = context.scene.BakeLabProps
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(self, "type")
        if props.image_size == 'FIXED':
            col = layout.column(align = True)
            col.prop(self, "width")
            col.prop(self, "height")
        elif props.image_size == 'ADAPTIVE':
            layout.prop(self, "image_scale")

        layout.prop(self, "float_depth")
        layout.prop(self, "use_udim")
        if props.save_or_pack == 'SAVE':
            row = layout.row()
            row.prop(self, "file_format")

            col = layout.column()
            if self.file_format == "PNG":
                row = col.row()
                row.prop(self, "png_channels", expand = True)
                row = col.row()
                row.prop(self, "png_depth", expand = True)
                col.prop(self, "png_compression")
            if self.file_format == "JPEG":
                row = col.row()
                row.prop(self, "jpg_channels", expand = True)
                col.prop(self, "jpg_quality")
            if self.file_format == "OPEN_EXR":
                row = col.row()
                row.prop(self, "exr_channels", expand = True)
                row = col.row()
                row.prop(self, "exr_depth", expand = True)
                if self.exr_depth == '32':
                    col.prop(self, "exr_codec_32")
                if self.exr_depth == '16':
                    col.prop(self, "exr_codec_16")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self,context):
        if context.area:
            context.area.tag_redraw()
        item = context.scene.BakeLabMaps.add()

        item.type        = self.type
        item.width       = self.width
        item.height      = self.height
        item.image_scale = self.image_scale

        item.float_depth      = self.float_depth
        item.use_udim         = self.use_udim
        item.file_format      = self.file_format
        item.png_channels     = self.png_channels
        item.png_depth        = self.png_depth
        item.png_compression  = self.png_compression
        item.jpg_channels     = self.jpg_channels
        item.jpg_quality      = self.jpg_quality
        item.exr_channels     = self.exr_channels
        item.exr_depth        = self.exr_depth
        item.exr_codec_32     = self.exr_codec_32
        item.exr_codec_16     = self.exr_codec_16

        self.calcItemSettings(context, item)
        context.scene.BakeLabMapIndex = len(context.scene.BakeLabMaps)-1
        return {'FINISHED'}

class BakeLabRemoveMapItem(Operator):
    """Remove selected bake map"""
    bl_idname = "bakelab.removemapitem"
    bl_label = "remove bake map"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return context.scene.BakeLabMaps

    def execute(self,context):
        if context.area:
            context.area.tag_redraw()
        context.scene.BakeLabMaps.remove(context.scene.BakeLabMapIndex)
        context.scene.BakeLabMapIndex = max(context.scene.BakeLabMapIndex - 1,0)
        context.scene.BakeLabMapIndex = min(context.scene.BakeLabMapIndex, len(context.scene.BakeLabMaps))
        return {'FINISHED'}

class BakeLabShowPassPresets(Operator):
    """Show Presets"""
    bl_idname = "bakelab.show_pass_presets"
    bl_label = "BakeLab Show Pass Presets"
    pass_presets : EnumProperty(
            name   = 'Pass Presets',
            items  =  (
                ('Color,Base Color,Albedo,Paint Color',  'Color/Albedo',''),
                ('Metallic',                             'Metallic',''),
                ('Specular IOR Level,Specular,Glossiness,Glossy', 'Specular',''),
                ('Roughness',                            'Roughness',''),
                ('Anisotropic',                          'Anisotropic',''),
                ('Sheen Weight,Sheen',                    'Sheen',''),
                ('Coat Weight,Clearcoat',                 'Clearcoat',''),
                ('Transmission Weight,Transmission',     'Transmission ',''),
                ('Alpha',                                'Alpha ','')
            )
        )

    def execute(self,context):
        if context.area:
            context.area.tag_redraw()
        scene = context.scene
        if scene.BakeLabMapIndex>=0 and scene.BakeLabMaps:
            item = scene.BakeLabMaps[scene.BakeLabMapIndex]
            if item:
                item.pass_name = self.pass_presets
        return {'FINISHED'}


class BakeLabResetMapDefaults(Operator):
    """Restore the addon preferences' map-defaults table to the shipped
    per-type values"""
    bl_idname = "bakelab.reset_map_defaults"
    bl_label = "Reset map defaults"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return addon_preferences(context) is not None

    def execute(self, context):
        prefs = addon_preferences(context)
        prefs.map_defaults.clear()
        prefs.map_defaults_index = 0
        seed_map_defaults(prefs)
        self.report(type = {'INFO'}, message = 'Map defaults reset')
        return {'FINISHED'}
