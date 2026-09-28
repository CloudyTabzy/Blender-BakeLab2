import bpy
from bpy.types import (
            Operator
        )


def selected_meshes(context):
    return [obj for obj in context.selected_objects
            if obj.type == 'MESH' and len(obj.data.polygons) > 0]


def unique_set_name(scene):
    names = {ts.name for ts in scene.BakeLabTextureSets}
    name = 'Set1'
    while name in names:
        name = 'Set%d' % (int(name[3:]) + 1) if name[3:].isdigit() \
               else name + '1'
    return name


def remove_object_everywhere(scene, obj):
    for ts in scene.BakeLabTextureSets:
        for i in range(len(ts.objects) - 1, -1, -1):
            if ts.objects[i].object == obj:
                ts.objects.remove(i)


def active_set(context):
    sets = context.scene.BakeLabTextureSets
    index = context.scene.BakeLabTextureSetIndex
    return sets[index] if 0 <= index < len(sets) else None


class BakeLab_TextureSetAdd(Operator):
    """Add a texture set; the selected mesh objects become its members"""
    bl_idname = "bakelab.texture_set_add"
    bl_label = "Add texture set"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        ts = scene.BakeLabTextureSets.add()
        ts.name = unique_set_name(scene)
        scene.BakeLabTextureSetIndex = len(scene.BakeLabTextureSets) - 1
        members = selected_meshes(context)
        for obj in members:
            remove_object_everywhere(scene, obj)  # one set per object
            ts.objects.add().object = obj
        if members:
            self.report(type = {'INFO'},
                        message = 'Set "%s" holds %d selected object%s'
                                  % (ts.name, len(members),
                                     's' if len(members) != 1 else ''))
        return {'FINISHED'}


class BakeLab_TextureSetRemove(Operator):
    """Remove the active texture set (its objects are not deleted)"""
    bl_idname = "bakelab.texture_set_remove"
    bl_label = "Remove texture set"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.BakeLabTextureSets) > 0

    def execute(self, context):
        scene = context.scene
        index = scene.BakeLabTextureSetIndex
        scene.BakeLabTextureSets.remove(index)
        scene.BakeLabTextureSetIndex = min(index, len(scene.BakeLabTextureSets) - 1)
        return {'FINISHED'}


class BakeLab_TextureSetAssign(Operator):
    """Move the selected mesh objects into the active texture set. An
    object can only live in one set, so it leaves any other set."""
    bl_idname = "bakelab.texture_set_assign"
    bl_label = "Assign selected to set"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_set(context) is not None

    def execute(self, context):
        scene = context.scene
        ts = active_set(context)
        added = 0
        for obj in selected_meshes(context):
            if ts.has_object(obj):
                continue
            remove_object_everywhere(scene, obj)
            ts.objects.add().object = obj
            added += 1
        self.report(type = {'INFO'},
                    message = 'Assigned %d object%s to "%s"'
                              % (added, 's' if added != 1 else '', ts.name))
        return {'FINISHED'}


class BakeLab_TextureSetUnassign(Operator):
    """Remove the selected objects from whichever set they belong to"""
    bl_idname = "bakelab.texture_set_unassign"
    bl_label = "Remove selected from sets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in selected_meshes(context):
            remove_object_everywhere(context.scene, obj)
        return {'FINISHED'}


class BakeLab_TextureSetSelect(Operator):
    """Select the active set's objects in the viewport"""
    bl_idname = "bakelab.texture_set_select"
    bl_label = "Select set members"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_set(context) is not None

    def execute(self, context):
        ts = active_set(context)
        members = [m.object for m in ts.objects
                   if m.object is not None]
        if not members:
            self.report(type = {'INFO'},
                        message = 'Set "%s" has no members' % ts.name)
            return {'CANCELLED'}
        bpy.ops.object.select_all(action = 'DESELECT')
        for obj in members:
            obj.select_set(True)
        context.view_layer.objects.active = members[0]
        return {'FINISHED'}
