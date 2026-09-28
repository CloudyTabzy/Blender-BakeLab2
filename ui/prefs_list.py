import bpy

class BakeLabDefaultListUI(bpy.types.UIList):
    bl_idname = "BAKELAB_DEFAULT_UL_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text = item.type, icon = 'NONE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text = "", icon = 'TEXTURE')


class BakeLabAliasListUI(bpy.types.UIList):
    bl_idname = "BAKELAB_ALIAS_UL_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(text = item.keyword or '(new rule)')
            row.label(text = item.channel.title())
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text = "", icon = 'TEXTURE')
