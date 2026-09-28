import bpy

class BakeLabSetListUI(bpy.types.UIList):
    bl_idname = "BAKELAB_SET_UL_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, 'name', text = '', emboss = False)
            members = sum(1 for m in item.objects if m.object is not None)
            layout.label(text = str(members), icon = 'MESH_DATA')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text = "", icon = 'TEXTURE')
        layout.prop(item, 'enabled')
