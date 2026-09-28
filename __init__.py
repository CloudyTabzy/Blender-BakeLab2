# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Supports Blender 4.2 LTS through 5.2 from a single build. Version
# differences are handled in utils/compat.py by capability detection.

bl_info = {
    "name" : "BakeLab",
    "author" : "Tabzy",
    "description" : "Bake textures easily",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "View3D > Properties > BakeLab",
    "category" : "Baking"
}

if "bpy" in locals():
    import importlib
    for _mod in (compat, tools, maps, baked_data, scene,
                 bake, post, uv, map_ops, panel, map_list):
        importlib.reload(_mod)
    del _mod
else:
    from .utils import compat as compat, tools as tools
    from .properties import maps, baked_data, scene
    from .operators import bake, post, uv, maps as map_ops
    from .ui import panel, map_list

import bpy

from bpy.props import (
            IntProperty,
            PointerProperty,
            CollectionProperty
        )

classes = (
    scene.BakeLabProperties,

    maps.BakeLabMap,
    baked_data.BakeObjData,
    baked_data.BakeMapData,
    baked_data.BakeLab_BakedData,

    bake.Baker,
    uv.Unwrapper,
    uv.ClearUV,

    post.BakeLab_GenerateMaterials,
    post.BakeLab_ApplyAO,
    post.BakeLab_ApplyDisplace,
    post.BakeLab_Finish,

    map_ops.BakeLabAddMapItem,
    map_ops.BakeLabRemoveMapItem,
    map_ops.BakeLabShowPassPresets,

    map_list.BakeLabMapListUI,
    panel.BakeLabUI
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.BakeLabProps = PointerProperty(type = scene.BakeLabProperties)
    bpy.types.Scene.BakeLabMaps = CollectionProperty(type = maps.BakeLabMap)
    bpy.types.Scene.BakeLab_Data = CollectionProperty(type = baked_data.BakeLab_BakedData)
    bpy.types.Scene.BakeLabMapIndex = IntProperty(name = 'BakeLab Map List Index')

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.BakeLabProps
    del bpy.types.Scene.BakeLabMaps
    del bpy.types.Scene.BakeLab_Data
    del bpy.types.Scene.BakeLabMapIndex

if __name__ == "__main__":
    register()
