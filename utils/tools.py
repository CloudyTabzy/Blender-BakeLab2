import bpy
import re

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

# foo_low / foo_low_01 / foo_low.001  <->  foo_high / foo_high_a / foo_high.001
# The side tag needs a separator before it; a variant follows through a
# separator or as trailing digits (so "sword_lowpoly" stays a plain name).
_NAME_PAIR_RE = re.compile(r'^(.*?)[_\-.](low|high)((?:[_\-.][\w.-]*|\d+))?$', re.IGNORECASE)
_DEDUP_RE = re.compile(r'\.\d+$')

def split_pair_name(name):
    """'prop_low_01' -> ('prop', 'low', '01'); None when the name carries
    no _low/_high tag. Blender's .001 dedup suffix is stripped first."""
    match = _NAME_PAIR_RE.match(_DEDUP_RE.sub('', name))
    if match is None or match.group(1) == '':
        return None
    variant = (match.group(3) or '').lstrip('_-.').casefold()
    return match.group(1).casefold(), match.group(2).casefold(), variant

def pair_high_low(objects):
    """Match *_low targets to their *_high* sources by name. Variants must
    agree when both sides carry one ('chest_low_1' <- 'chest_high_1'), while
    a side with no variant pairs with every variant of the other. Returns
    [(low, [highs])] sorted by low name - lows with no sources included."""
    lows = []
    highs = []
    for obj in objects:
        parts = split_pair_name(obj.name)
        if parts is None:
            continue
        base, side, variant = parts
        (lows if side == 'low' else highs).append((obj, base, variant))
    return [(low, [obj for obj, hbase, hvar in highs
                   if hbase == base and (variant == hvar or not variant or not hvar)])
            for low, base, variant in sorted(lows, key=lambda e: e[0].name)]


# Texture-import filename suffix token -> channel; aliases cover common
# pipelines (Substance 'basecolor', Marmoset-style 'albedo', Unity
# 'metallic'...). 'color' channels carry a view transform; everything
# else is raw data. The texture importer consumes this table and the
# addon preferences enumerate it for user aliases.
CHANNEL_SPECS = (
    ('aorm',         ('aorm', 'orm'),                                   True),
    ('basecolor',    ('basecolor', 'base_color', 'albedo', 'diffuse',
                      'diff', 'col', 'color', 'base'),                  False),
    ('normal',       ('normal', 'nrm', 'nor'),                          True),
    ('roughness',    ('roughness', 'rough'),                            True),
    ('metallic',     ('metallic', 'metal', 'metalness'),                True),
    ('specular',     ('specular', 'spec'),                              True),
    ('emission',     ('emission', 'emissive', 'emit', 'glow'),          False),
    ('alpha',        ('alpha', 'opacity'),                              True),
    ('ao',           ('ao', 'occlusion', 'ambientocclusion'),           True),
    ('displacement', ('height', 'displacement', 'disp', 'bump'),        True),
)
CHANNEL_ALIASES = {alias: channel
                   for channel, aliases, _ in CHANNEL_SPECS
                   for alias in aliases}
DATA_CHANNELS = {channel for channel, _, is_data in CHANNEL_SPECS if is_data}