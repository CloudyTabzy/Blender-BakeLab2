import bpy

class BakeLabMapListUI(bpy.types.UIList):
    bl_idname = "BAKELAB_MAP_UL_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item.type == 'CustomPass':
                layout.label(text = item.pass_name, icon = 'NONE')
            else:
                layout.label(text = item.type, icon = 'NONE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text = "", icon = 'TEXTURE')
        layout.prop(item, 'enabled')
