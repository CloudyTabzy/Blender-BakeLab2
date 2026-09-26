import bpy
from . import bakelab_map

from bpy.types import (
            Operator,
            PropertyGroup, 
            Panel
        )
from bpy.props import (
            IntProperty,
            EnumProperty,
            BoolProperty,
            FloatProperty,
            StringProperty,
            PointerProperty,
            CollectionProperty
        )
class BakeObjData(PropertyGroup):
    obj : PointerProperty(
        type=bpy.types.Object
    )
    uv_layer : StringProperty(name='Bake UV Map')
class BakeMapData(PropertyGroup):
    bake_map : PointerProperty(
        type=bakelab_map.BakeLabMap
    )
    image : PointerProperty(
        type=bpy.types.Image
    )

class BakeLab_BakedData(PropertyGroup):
    obj_list : CollectionProperty(
        type=BakeObjData
    )
    map_list : CollectionProperty(
        type=BakeMapData
    )
    
    def AddObj(self, obj):
        item = self.obj_list.add()
        item.obj = obj
        uv_layer = obj.data.uv_layers.active
        item.uv_layer = uv_layer.name if uv_layer else ''

    def AddMap(self, bake_map, image):
        item = self.map_list.add()
        
        item.bake_map.type = bake_map.type
        item.bake_map.pass_name = bake_map.pass_name
        item.bake_map.normal_space = bake_map.normal_space
        
        item.image = image
