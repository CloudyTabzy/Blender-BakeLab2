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
    "version" : (3, 9, 1),
    "location" : "View3D > Properties > BakeLab",
    "category" : "Baking"
}

if "bpy" in locals():
    import importlib
    for _mod in (compat, tools, maps, baked_data, scene, prefs, sets,
                 bake, post, uv, map_ops, import_textures, texture_sets,
                 panel, map_list, set_list, prefs_list):
        importlib.reload(_mod)
    del _mod
else:
    from .utils import compat as compat, tools as tools
    from .properties import maps, baked_data, scene, prefs, sets
    from .operators import bake, post, uv, maps as map_ops, import_textures, texture_sets
    from .ui import panel, map_list, set_list, prefs_list

import bpy

from bpy.props import (
            IntProperty,
            PointerProperty,
            CollectionProperty
        )

classes = (
    prefs.BakeLabMapDefault,
    prefs.BakeLabImportAlias,
    prefs.BakeLabPreferences,
    scene.BakeLabProperties,

    sets.BakeLabTextureSetMember,
    sets.BakeLabTextureSet,
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
    post.BakeLab_Cleanup,
    import_textures.BakeLab_ImportTextures,
    import_textures.BakeLab_ImportAliasAdd,
    import_textures.BakeLab_ImportAliasRemove,

    texture_sets.BakeLab_TextureSetAdd,
    texture_sets.BakeLab_TextureSetRemove,
    texture_sets.BakeLab_TextureSetAssign,
    texture_sets.BakeLab_TextureSetUnassign,
    texture_sets.BakeLab_TextureSetSelect,

    map_ops.BakeLabAddMapItem,
    map_ops.BakeLabRemoveMapItem,
    map_ops.BakeLabShowPassPresets,
    map_ops.BakeLabResetMapDefaults,

    map_list.BakeLabMapListUI,
    set_list.BakeLabSetListUI,
    prefs_list.BakeLabDefaultListUI,
    prefs_list.BakeLabAliasListUI,
    panel.BakeLabUI
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.BakeLabProps = PointerProperty(type = scene.BakeLabProperties)
    bpy.types.Scene.BakeLabMaps = CollectionProperty(type = maps.BakeLabMap)
    bpy.types.Scene.BakeLab_Data = CollectionProperty(type = baked_data.BakeLab_BakedData)
    bpy.types.Scene.BakeLabMapIndex = IntProperty(name = 'BakeLab Map List Index')
    bpy.types.Scene.BakeLabTextureSets = CollectionProperty(type = sets.BakeLabTextureSet)
    bpy.types.Scene.BakeLabTextureSetIndex = IntProperty(name = 'BakeLab Texture Set Index')

def unregister():
    # Delete scene properties before the classes they point at, and
    # tolerate a partially torn-down RNA when Blender calls this during
    # shutdown (unregister_class can then raise "missing bl_rna").
    for prop in ("BakeLabProps", "BakeLabMaps", "BakeLab_Data", "BakeLabMapIndex",
                 "BakeLabTextureSets", "BakeLabTextureSetIndex"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

if __name__ == "__main__":
    register()
