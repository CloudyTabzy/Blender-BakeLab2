import bpy

def SelectObject(obj):
    bpy.ops.object.select_all(action = 'DESELECT')
    if obj:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
def SelectObjects(active_obj, selected_objs):
    SelectObject(active_obj)
    for obj in selected_objs:
        if obj:
            obj.select_set(True)
            
def IsValidMesh(self, obj):
    if obj.type != 'MESH':
        self.report(type = {'WARNING'}, message = 'Object ' + obj.name + ' is not mesh type')
        return False
    if len(obj.data.polygons) == 0:
        self.report(type = {'WARNING'}, message = 'Object ' + obj.name + ' has no faces')
        return False
    return True

# Socket names (casefolded) that hold a material's opacity
ALPHA_SOCKET_NAMES = {'alpha', 'opacity', 'transparency', 'transparent'}

def material_has_wired_alpha(mat):
    """True when the material's opacity depends on nodes: an alpha-named
    value socket with a live link, or a Transparent BSDF that feeds
    something. Leaf-level scan - the baker itself handles node groups."""
    if mat is None or not getattr(mat, 'use_nodes', False) \
            or mat.node_tree is None:
        return False
    for node in mat.node_tree.nodes:
        if node.bl_idname == 'ShaderNodeBsdfTransparent' \
                and node.outputs and node.outputs[0].is_linked:
            return True
        for socket in node.inputs:
            if socket.type == 'VALUE' and socket.is_linked \
                    and (socket.name.casefold() in ALPHA_SOCKET_NAMES
                         or socket.identifier.casefold() in ALPHA_SOCKET_NAMES):
                return True
    return False