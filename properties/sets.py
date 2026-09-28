from bpy.types import PropertyGroup, Object
from bpy.props import (
            BoolProperty,
            CollectionProperty,
            IntProperty,
            PointerProperty,
            StringProperty
        )


class BakeLabTextureSetMember(PropertyGroup):
    object: PointerProperty(type = Object)


class BakeLabTextureSet(PropertyGroup):
    """A named group of objects that bake together into one shared image
    set - the Substance-Painter-style texture set. Batch source TEXTURE_SETS
    turns each enabled set into an All-To-One job named after the set."""
    name   : StringProperty(name = 'Name', default = 'Set')
    enabled: BoolProperty(name = '', default = True,
                description = 'Include this set in the bake queue')
    objects: CollectionProperty(type = BakeLabTextureSetMember)
    objects_index: IntProperty()

    def has_object(self, obj):
        return any(member.object == obj for member in self.objects)


def sets_membership(scene):
    """Object -> set name for every enabled texture set, first set wins.
    Returns (membership, duplicates): duplicates lists object names that
    appear in more than one enabled set (they bake under the first)."""
    membership = {}
    duplicates = []
    for ts in scene.BakeLabTextureSets:
        if not ts.enabled:
            continue
        for member in ts.objects:
            obj = member.object
            if obj is None:
                continue
            if obj in membership:
                duplicates.append(obj.name)
            else:
                membership[obj] = ts.name
    return membership, duplicates
