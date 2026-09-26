import os
import traceback
import bpy

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

from array import array
from math import log2, floor
from os.path import abspath, join

from .bakelab_tools import (
    SelectObject,
    SelectObjects,
    IsValidMesh
)
from . import bakelab_compat as compat
    
def iter_child_collections(collection):
    for child in collection.children:
        yield child
        yield from iter_child_collections(child)


class BakeJob:
    """One unit of the bake queue.

    materials=None bakes every material slot (legacy SELECTION behavior);
    a set of original Materials restricts the bake target to the slots
    holding them (MATERIAL batch source)."""
    __slots__ = ('name', 'objects', 'active_object', 'image_name', 'materials')

    def __init__(self, name, objects, active_object=None, image_name=None, materials=None):
        self.name = name
        self.objects = list(objects)
        self.active_object = active_object
        self.image_name = image_name
        self.materials = materials


class Baker(Operator):
    """Bake"""
    bl_label = "BakeLab Bake"
    bl_info = "BakeLab"
    bl_idname = "bakelab.bake"
    bl_options = {'REGISTER', 'UNDO'}
    
    _timer = None
    cycles = None
    headless = False
    _udim_aa_warned = False
    TMP_EMPTY_MAT_NAME = "BAKELAB_TMP_EMPTY_MAT"
    TMP_INERT_MAT_NAME = "BAKELAB_TMP_INERT_MAT"
    TMP_IMAGE_NODE_NAME = "BAKELAB_TMP_IMAGE_NODE"

    # BakeLab map type -> Cycles bake type
    BAKE_TYPES = {
        'Albedo':       'EMIT',
        'Combined':     'COMBINED',
        'AO':           'AO',
        'Displacement': 'EMIT',
        'Shadow':       'SHADOW',
        'Normal':       'NORMAL',
        'UV':           'UV',
        'Roughness':    'ROUGHNESS',
        'Emission':     'EMIT',
        'Environment':  'ENVIRONMENT',
        'Diffuse':      'DIFFUSE',
        'Glossy':       'GLOSSY',
        'Transmission': 'TRANSMISSION',
        'Subsurface':   'EMIT', # Subsurface Weight, SSS lighting is part of the Diffuse pass since 2.83
        'CustomPass':   'EMIT',
    }

    def save_defaults(self, context):
        scene = context.scene
        render = scene.render
        
        # Image settings{
        img_settings = render.image_settings
        # 5.0+ filters file_format by media_type; absent on 4.2 - 4.5
        self.default_image_media_type = getattr(img_settings, 'media_type', None)
        self.default_image_format = img_settings.file_format
        self.default_color_mode   = img_settings.color_mode
        self.default_color_depth  = img_settings.color_depth
        
        self.default_compression  = img_settings.compression
        self.default_quality      = img_settings.quality
        self.default_exr_codec    = img_settings.exr_codec

        self.default_color_management = img_settings.color_management
        view_settings = img_settings.view_settings
        self.default_view_transform = view_settings.view_transform
        self.default_look           = view_settings.look
        self.default_exposure       = view_settings.exposure
        self.default_gamma          = view_settings.gamma
        # }
        
        # Scene settings{
        self.default_active_object = context.active_object
        self.default_selected_objects = context.selected_objects
        self.default_engine = render.engine
        # scene.cycles only exists while the Cycles add-on is registered
        self.cycles = compat.cycles_settings(scene)
        if self.cycles is not None:
            self.default_cycles_device = self.cycles.device
            self.default_cycles_pause = self.cycles.preview_pause
        else:
            self.default_cycles_device = None
            self.default_cycles_pause  = None
        # }
        
        # Bake settings{
        bake_settings = context.scene.render.bake
        self.default_use_s2a = bake_settings.use_selected_to_active
        self.default_use_cage = bake_settings.use_cage
        self.default_cage_extrusion = bake_settings.cage_extrusion
        self.default_max_ray_distance = bake_settings.max_ray_distance
        self.default_bake_margin    = bake_settings.margin
        self.default_samples        = self.cycles.samples if self.cycles is not None else None
        self.default_normal_space = bake_settings.normal_space
        
        self.default_use_pass_direct   = bake_settings.use_pass_direct
        self.default_use_pass_indirect = bake_settings.use_pass_indirect
        self.default_use_pass_color    = bake_settings.use_pass_color
        
        self.default_use_pass_diffuse  = bake_settings.use_pass_diffuse
        self.default_use_pass_glossy   = bake_settings.use_pass_glossy
        self.default_use_pass_trans    = bake_settings.use_pass_transmission
        #self.default_use_pass_sss      = bake_settings.use_pass_subsurface # No Longer in 2.83
        #self.default_use_pass_ao       = bake_settings.use_pass_ambient_occlusion # No Longer in 3.0
        self.default_use_pass_emit     = bake_settings.use_pass_emit
    
        self.default_cage_object       = bake_settings.cage_object
        # }
        
    def restore_defaults(self, context):
        scene = context.scene
        render = scene.render
        
        # Image settings{
        img_settings = render.image_settings
        compat.set_image_file_format(img_settings, self.default_image_format,
                                     self.default_image_media_type)
        compat.set_enum(img_settings, 'color_mode', self.default_color_mode)
        compat.set_enum(img_settings, 'color_depth', self.default_color_depth)
        
        img_settings.compression         = self.default_compression
        img_settings.quality             = self.default_quality
        compat.set_enum(img_settings, 'exr_codec', self.default_exr_codec)

        # color_management must be set before the view_settings writes below,
        # whose available items depend on it
        img_settings.color_management    = self.default_color_management
        view_settings = img_settings.view_settings
        if not compat.set_enum(view_settings, 'view_transform', self.default_view_transform):
            self.report(type = {'WARNING'},
                        message = "Could not restore view transform '%s'" % self.default_view_transform)
        compat.set_enum(view_settings, 'look', self.default_look)
        view_settings.exposure           = self.default_exposure
        view_settings.gamma              = self.default_gamma
        # }
        
        # Scene settings{
        SelectObjects(self.default_active_object, self.default_selected_objects)
        render.engine = self.default_engine
        if self.cycles is not None:
            self.cycles.device = self.default_cycles_device
            if not self.headless:
                # Never written in a headless run; writing it back would trip
                # Cycles' area tag_redraw callback with no area present
                self.cycles.preview_pause = self.default_cycles_pause
        # }
        
        # Bake settings{
        bake_settings = context.scene.render.bake
        bake_settings.use_selected_to_active = self.default_use_s2a
        bake_settings.use_cage = self.default_use_cage
        bake_settings.cage_extrusion = self.default_cage_extrusion
        bake_settings.max_ray_distance = self.default_max_ray_distance
        bake_settings.margin  = self.default_bake_margin
        if self.cycles is not None:
            self.cycles.samples = self.default_samples
        compat.set_enum(bake_settings, 'normal_space', self.default_normal_space)
        
        bake_settings.use_pass_direct          = self.default_use_pass_direct
        bake_settings.use_pass_indirect        = self.default_use_pass_indirect
        bake_settings.use_pass_color           = self.default_use_pass_color
    
        bake_settings.use_pass_diffuse           = self.default_use_pass_diffuse
        bake_settings.use_pass_glossy            = self.default_use_pass_glossy
        bake_settings.use_pass_transmission      = self.default_use_pass_trans
        #bake_settings.use_pass_subsurface        = self.default_use_pass_sss # No Longer in 2.83
        #bake_settings.use_pass_ambient_occlusion = self.default_use_pass_ao # No Longer in 3.0
        bake_settings.use_pass_emit              = self.default_use_pass_emit
    
        bake_settings.cage_object              = self.default_cage_object
        # }
    
    def passes_to_rgb(self, node, src_socket, nodes, links, passes):
        has_bsdf_inputs = False
        for input in node.inputs:
            if input.type == 'SHADER':
                has_bsdf_inputs = True
                if len(input.links):
                    self.passes_to_rgb(input.links[0].from_node, input,
                                    nodes, links, passes)
        
        if not has_bsdf_inputs:
            emit = nodes.new(type = 'ShaderNodeEmission')
            emit_color = compat.input_socket(emit, 'Color', 0)
            emit_color.default_value = 0, 0, 0, 0
            links.new(compat.output_socket(emit, 'Emission', 0), src_socket)
            ####### Find Pass Input Socket{
            # Names are in priority order, so the first one the node has wins;
            # sockets also answer to their identifier (display name may differ)
            pass_input = next((s for p in passes for s in node.inputs
                               if s.name.casefold() == p or s.identifier.casefold() == p), None)
            ####### }
            if pass_input:
                if len(pass_input.links):
                    links.new(pass_input.links[0].from_socket, emit_color)
                else:
                    if   pass_input.type == 'RGBA':
                        emit_color.default_value[0] = pass_input.default_value[0]
                        emit_color.default_value[1] = pass_input.default_value[1]
                        emit_color.default_value[2] = pass_input.default_value[2]
                        emit_color.default_value[3] = pass_input.default_value[3]
                    elif pass_input.type == 'VECTOR':
                        emit_color.default_value[0] = pass_input.default_value[0]
                        emit_color.default_value[1] = pass_input.default_value[1]
                        emit_color.default_value[2] = pass_input.default_value[2]
                        emit_color.default_value[3] = 1
                    elif pass_input.type == 'VALUE':
                        emit_color.default_value[0] = pass_input.default_value
                        emit_color.default_value[1] = pass_input.default_value
                        emit_color.default_value[2] = pass_input.default_value
                        emit_color.default_value[3] = 1
    
    def passes_to_emit_node(self, mat, passes):
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        out = self.find_node(nodes, 'OUTPUT_MATERIAL')
            
        if out:
        #### Modify Nodes
            split_passes = passes.split(',')
            for i in range(len(split_passes)):
                split_passes[i] = split_passes[i].strip().casefold()
            self.passes_to_rgb(out, None, nodes, links, split_passes)
        else:
        #### Create Default Texture Nodes
            out = nodes.new(type = 'ShaderNodeOutputMaterial')
            emit = nodes.new(type = 'ShaderNodeEmission')
            compat.input_socket(emit, 'Color', 0).default_value = 0, 0, 0, 0
            links.new(compat.output_socket(emit, 'Emission', 0),
                      compat.input_socket(out, 'Surface', 0))
            
    def copy_node(self, dst_nodes, node):
        try:
            new_node = dst_nodes.new(type = node.bl_idname)
        except RuntimeError:
            return None
        for member in dir(node):
            try:
                value = getattr(node, member)
                if value is None:
                    continue
                setattr(new_node, member, value)
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass # Read-only or incompatible attribute
        # Outputs too, RGB and Value nodes store their value there
        for src_sockets, dst_sockets in ((node.inputs, new_node.inputs), (node.outputs, new_node.outputs)):
            for src_socket in src_sockets:
                dst_socket = self.get_socket(dst_sockets, src_socket.identifier)
                if dst_socket is not None:
                    if hasattr(src_socket, 'default_value') and \
                            hasattr(dst_socket, 'default_value'):
                        dst_socket.default_value = src_socket.default_value
        return new_node
    
    def find_node(self, nodes, type):
        for node in nodes:
            if node.type == type:
                if type in {"OUTPUT_MATERIAL", "GROUP_OUTPUT"}:
                    if node.is_active_output:
                        return node
                else:
                    return node
        return None
    
    def get_socket(self, sockets, identifier):
        for socket in sockets:
            if socket.identifier == identifier:
                return socket
        return None

    def forward_group_socket(self, src_input, dst_input, nodes, links):
        """Forward an interface input, retaining Blender's socket conversions."""
        if src_input.is_linked:
            links.new(src_input.links[0].from_socket, dst_input)
        elif src_input.type == 'RGBA':
            value = nodes.new('ShaderNodeRGB')
            value.outputs[0].default_value = src_input.default_value
            links.new(value.outputs[0], dst_input)
        elif src_input.type == 'VECTOR':
            value = nodes.new('ShaderNodeCombineXYZ')
            for socket, component in zip(value.inputs, src_input.default_value):
                socket.default_value = component
            links.new(value.outputs[0], dst_input)
        elif src_input.type in {'VALUE', 'INT', 'BOOLEAN'}:
            value = nodes.new('ShaderNodeValue')
            value.outputs[0].default_value = src_input.default_value
            links.new(value.outputs[0], dst_input)
        # Unlinked shader inputs have no default_value and remain unlinked.
    
    def extract_nodes_rc(
                self, gr_node, gr_in, gr_out,
                nodes, links, n_group, node_dict):
        if gr_node.name in node_dict:
            return node_dict[gr_node.name]
        
        node = self.copy_node(nodes, gr_node)
        node_dict[gr_node.name] = node
        
        if node is None:
            return None
        
        ### Inputs {
        for src_input in gr_node.inputs:
            dst_input = self.get_socket(node.inputs, src_input.identifier)
            if dst_input is None:
                continue
            for link in src_input.links:
                from_node = link.from_node
                
                if from_node.type == 'GROUP_INPUT':
                    ng_input = self.get_socket(n_group.inputs, link.from_socket.identifier)
                    if ng_input is None:
                        continue
                    self.forward_group_socket(ng_input, dst_input, nodes, links)
                else:
                    link_node = self.extract_nodes_rc(
                        from_node, gr_in, gr_out,
                        nodes, links, n_group, node_dict)
                    if link_node is not None:
                        link_output = self.get_socket(link_node.outputs, link.from_socket.identifier)
                        if link_output is not None:
                            links.new(link_output, dst_input)
        ### }
        ### Outputs {
        for src_output in gr_node.outputs:
            dst_output = self.get_socket(node.outputs, src_output.identifier)
            if dst_output is None:
                continue
            for link in src_output.links:
                to_node = link.to_node
                
                if to_node.type == 'GROUP_OUTPUT':
                    if to_node != gr_out:
                        continue
                    ng_output = self.get_socket(n_group.outputs, link.to_socket.identifier)
                    if ng_output is None:
                        continue
                    for ng_link in ng_output.links:
                        links.new(dst_output, ng_link.to_socket)
                else:
                    link_node = self.extract_nodes_rc(
                        to_node, gr_in, gr_out,
                        nodes, links, n_group, node_dict)
                    if link_node is not None:
                        link_input = self.get_socket(link_node.inputs, link.to_socket.identifier)
                        if link_input is not None:
                            links.new(dst_output, link_input)
        ### }
        return node
    
    def ungroup_nodes(self, node_tree):
        nodes = node_tree.nodes
        links = node_tree.links
        skipped = set() # Groups that can't be expanded, left in place
        while True:
            group_exists = False
            ungroup_nodes = [n for n in nodes]
            for node in ungroup_nodes:
                if node.type != 'GROUP' or node.name in skipped:
                    continue
                if node.node_tree is None:
                    skipped.add(node.name)
                    continue

                node_dict = {}
                gr_nodes = node.node_tree.nodes
                gr_in  = self.find_node(gr_nodes, 'GROUP_INPUT') # May be None, the group then has no inputs
                gr_out = self.find_node(gr_nodes, 'GROUP_OUTPUT')
                if gr_out is None:
                    skipped.add(node.name)
                    continue
                group_exists = True

                for gr_node in gr_nodes:
                    if gr_node.type in {'GROUP_INPUT', 'GROUP_OUTPUT'}:
                        continue
                    self.extract_nodes_rc(
                        gr_node, gr_in, gr_out,
                        nodes, links, node, node_dict)
                # Direct input-to-output links and unconnected output defaults
                # have no internal node for extract_nodes_rc to visit.
                for output_input in gr_out.inputs:
                    group_output = self.get_socket(node.outputs, output_input.identifier)
                    if group_output is None:
                        continue
                    source = output_input
                    if output_input.is_linked:
                        source_link = output_input.links[0]
                        if source_link.from_node.type != 'GROUP_INPUT':
                            continue
                        source = self.get_socket(node.inputs, source_link.from_socket.identifier)
                    if source is not None:
                        for link in list(group_output.links):
                            self.forward_group_socket(source, link.to_socket, nodes, links)
                node_dict.clear()
                nodes.remove(node)
            if not group_exists:
                break
            
    def displacement_to_color(self, mat):
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        out = self.find_node(nodes, 'OUTPUT_MATERIAL')
        if out == None:
            return

        displacement = compat.input_socket(out, 'Displacement', 2)
        surface      = compat.input_socket(out, 'Surface', 0)
        if displacement is None or len(displacement.links) == 0:
            emit = nodes.new(type = 'ShaderNodeEmission')
            compat.input_socket(emit, 'Color', 0).default_value = 0, 0, 0, 0
            links.new(compat.output_socket(emit, 'Emission', 0), surface)
        else:
            from_socket = displacement.links[0].from_socket
            v_transform = nodes.new(type = 'ShaderNodeVectorTransform')
            links.remove(displacement.links[0])

            links.new(from_socket, compat.input_socket(v_transform, 'Vector', 0))
            links.new(compat.output_socket(v_transform, 'Vector', 0), surface)
    
    def init_bake_settings(self, context, map):
        self.cycles.samples = map.samples
        bake_settings = context.scene.render.bake
        bake_settings.normal_space = map.normal_space
        
        if map.type == 'Combined':
            bake_settings.use_pass_direct            = map.combined_direct
            bake_settings.use_pass_indirect          = map.combined_indirect
    
            bake_settings.use_pass_diffuse           = map.combined_diffuse
            bake_settings.use_pass_glossy            = map.combined_glossy
            bake_settings.use_pass_transmission      = map.combined_transmission
            #bake_settings.use_pass_subsurface        = map.combined_subsurface
            #bake_settings.use_pass_ambient_occlusion = map.combined_ambient_occlusion
            bake_settings.use_pass_emit              = map.combined_emit
        else:
            bake_settings.use_pass_direct          = map.bake_direct
            bake_settings.use_pass_indirect        = map.bake_indirect
            bake_settings.use_pass_color           = map.bake_color
        
        return self.BAKE_TYPES[map.type]
    
    def calc_surf_area(self, obj):
        import bmesh
        bm = bmesh.new(use_operators=False)
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        area = sum(face.calc_area() for face in bm.faces)
        bm.free()
        return area
    
    def round_to_power_of_2(self, num):
        return pow(2,round(log2(num)))
    
    def apply_transparent_background(self, bake_image):
        # run_bake preserves coverage alpha with a masked write. RGB cannot
        # distinguish empty space from black albedo or zero-valued data maps.
        # Tiled images must not be touched here: assigning alpha_mode after a
        # bake clears their dirty state and voids the pack/save that follows.
        # Their alpha_mode is set at creation instead (create_image).
        if bake_image.source == 'TILED':
            return
        bake_image.alpha_mode = 'STRAIGHT'

    def collect_udim_tiles(self, objects):
        """Set of UDIM tile numbers covered by the bake UVs of objects. Uses
        each object's editing-active UV layer — the same layer run_bake passes
        to object.bake. Coordinates outside the valid tile grid (negative,
        u >= 10 — the grid is ten columns wide — or tile > 2000) are counted
        and reported once; tile = 1001 + floor(u) + floor(v) * 10."""
        tiles = set()
        skipped = 0
        for obj in objects:
            uv_layer = obj.data.uv_layers.active
            if uv_layer is None:
                continue
            coords = array('f', [0.0]) * (len(uv_layer.data) * 2)
            uv_layer.data.foreach_get('uv', coords)
            for i in range(0, len(coords), 2):
                tu = int(floor(coords[i]))
                tv = int(floor(coords[i + 1]))
                number = 1001 + tu + tv * 10
                # tu > 9 would collide with the next row's tiles (u=15,v=0 and
                # u=5,v=1 both compute 1016) and the engine bakes nothing there
                if tu < 0 or tv < 0 or tu > 9 or number > 2000:
                    skipped += 1
                    continue
                tiles.add(number)
        if skipped:
            self.report(type = {'WARNING'},
                        message = '%d UV coordinates outside the UDIM range 1001-2000 were skipped' % skipped)
        return tiles

    def create_image(self, context, map, image_name, tiles=()):
        if map.use_udim:
            if not compat.SUPPORTS_IMAGE_TILES:
                raise RuntimeError('This Blender build has no UDIM image support')
            bake_image = compat.new_tiled_image(image_name,
                                                map.target_width, map.target_height,
                                                map.clear_img)
            # Must happen before the bake: touching alpha_mode afterwards clears
            # the dirty state and voids pack/save on tiled images.
            bake_image.alpha_mode = 'STRAIGHT'
            bake_image.use_generated_float = map.float_depth
            fill_color = (0, 0, 0, 0) if map.clear_img else (0, 0, 0, 1)
            if map.clear_img:
                bake_image.generated_color = fill_color
            numbers = set(tiles) or {1001}
            failed = compat.ensure_tiles(context, bake_image, numbers,
                                         map.target_width, map.target_height,
                                         map.float_depth, fill_color)
            if failed:
                raise RuntimeError('Could not initialize UDIM tiles %s' % failed)
            # new_tiled_image always brings tile 1001; drop unneeded tiles so
            # saving does not write blank extra files (fresh images only)
            if not compat.prune_tiles(context, bake_image, numbers):
                self.report(type = {'WARNING'},
                            message = 'Could not remove unneeded UDIM tiles; '
                                      'extra blank tile files may be written')
        else:
            bake_image = bpy.data.images.new(
                name = image_name,
                width  = map.target_width  * map.final_aa,
                height = map.target_height * map.final_aa,
                # Without an alpha channel, packing and Save As drop the transparent background
                alpha = map.clear_img
            )
            bake_image.use_generated_float = map.float_depth
            if map.clear_img:
                bake_image.generated_color = (0, 0, 0, 0)
        # map.color_space is the addon's own key; the OCIO config of the
        # active build decides the actual color space name
        if compat.set_image_colorspace(bake_image.colorspace_settings, map.color_space) is None:
            self.report(type = {'WARNING'},
                        message = "Could not set color space %s (tried %s)"
                                  % (map.color_space,
                                     ', '.join(compat.color_space_candidates(map.color_space))))
        return bake_image
    
    def PrepareImage(self, context, map, objects, name):
        props = context.scene.BakeLabProps
        self.SetSaveImageSettings(context, map)
        
        if props.image_size == 'FIXED':
            map.target_width  = map.width
            map.target_height = map.height
        elif props.image_size == 'ADAPTIVE':
            area = 0
            for obj in objects:
                area += self.calc_surf_area(obj)
            size = max(pow(area, 0.5) * props.texel_per_unit * map.image_scale, 1)
            if props.round_adaptive_image:
                size = self.round_to_power_of_2(size)
            size = int(min(max(size, props.image_min_size), props.image_max_size))
            map.target_width  = size
            map.target_height = size
            
        map.final_aa = props.anti_alias
        if map.aa_override > 0:
            map.final_aa = map.aa_override

        udim_tiles = set()
        if map.use_udim:
            # No per-tile downscale exists in the Python API: image.scale()
            # only touches the base tile, so UDIM maps bake at final size.
            if map.final_aa != 1 and not self._udim_aa_warned:
                self.report(type = {'WARNING'},
                            message = 'Anti-aliasing is disabled for UDIM maps (tiles bake at final size)')
                self._udim_aa_warned = True
            map.final_aa = 1
            udim_tiles = self.collect_udim_tiles(objects)
            if not udim_tiles:
                raise RuntimeError('No UVs inside the UDIM tile range (1001-2000)')

        image_name = map.img_name.replace('*', name)

        bake_image = bpy.data.images.get(image_name)
        if bake_image is not None and (bake_image.source == 'TILED') != bool(map.use_udim):
            # No API converts between tiled and non-tiled images
            self.report(type = {'WARNING'},
                        message = "Replacing %s image '%s' (UDIM setting changed)"
                                  % ('non-UDIM' if map.use_udim else 'UDIM', image_name))
            bpy.data.images.remove(bake_image)
            bake_image = None
        if map.clear_img and bake_image is not None:
            bpy.data.images.remove(bake_image)
            bake_image = None
        if bake_image is None:
            self.report(type = {'INFO'}, message = "Creating new image " + image_name)
            bake_image = self.create_image(context, map, image_name, udim_tiles)
        elif map.use_udim:
            # Reuse: initialize every needed tile (ensure_tiles skips ones that
            # already hold pixels and repairs 0x0 leftovers); never prune (that
            # would destroy baked pixels) and never rescale (scale() only
            # touches the base tile).
            sizes = {tuple(tile.size) for tile in bake_image.tiles}
            if sizes and sizes != {(map.target_width, map.target_height)}:
                self.report(type = {'WARNING'},
                            message = 'Reused UDIM image keeps its tile sizes; new tiles added at %dx%d'
                                      % (map.target_width, map.target_height))
            failed = compat.ensure_tiles(context, bake_image, udim_tiles,
                                         map.target_width, map.target_height,
                                         map.float_depth, tuple(bake_image.generated_color))
            if failed:
                raise RuntimeError('Could not initialize UDIM tiles %s' % failed)
        
        context.scene.render.bake.margin = props.bake_margin * map.final_aa
        if props.save_or_pack == 'PACK':
            bake_image.pack()
        else:
            extension = "."
            if map.file_format == 'PNG':
                extension = '.png'
            if map.file_format == 'JPEG':
                extension = '.jpg'
            if map.file_format == 'OPEN_EXR':
                extension = '.exr'
            
            file_stem = bake_image.name
            if bake_image.source == 'TILED':
                # Tiled images only save through a path with the <UDIM> marker;
                # it writes one file per tile (name_1001.png, ...)
                file_stem += '_<UDIM>'
            
            abs_save_path = bpy.path.abspath(props.save_path)
            if not os.path.isdir(abs_save_path):
                os.makedirs(abs_save_path, 0o777)
            
            if props.create_folder:
                if props.bake_mode == "ALL_TO_ONE" and props.batch_source == 'SELECTION':
                    folder = props.folder_name
                else:
                    # Per-object folder, or per-job folder when batching
                    folder = name
                bake_image.filepath = abspath(join(abs_save_path, folder, file_stem + extension))
            else:
                bake_image.filepath = abspath(join(abs_save_path, file_stem + extension))
            
            bake_image.save_render(bake_image.filepath)

        # A reused image keeps the size of its last bake, which was downscaled after anti-aliasing.
        # Resized last, since changing the filepath above can reload the image from disk.
        # Tiled images are skipped: scale() would only resize the base tile.
        if bake_image.source != 'TILED':
            bake_size = (map.target_width * map.final_aa, map.target_height * map.final_aa)
            if tuple(bake_image.size) != bake_size:
                bake_image.scale(*bake_size)

        return bake_image
    
    def SetSaveImageSettings(self, context, map):
        img_settings = context.scene.render.image_settings
        accepted_format = compat.set_image_file_format(img_settings, map.file_format)
        if accepted_format != map.file_format:
            # The extension is derived from map.file_format below, so a rejected
            # format would write one payload into a differently-named file.
            self.report(type = {'ERROR'},
                        message = "File format '%s' was not accepted (got '%s')"
                                  % (map.file_format, accepted_format))
        # save_render applies the scene view transform (AgX by default) to color images,
        # so write them with Standard to keep the baked values unchanged
        img_settings.color_management = 'OVERRIDE'
        view_settings = img_settings.view_settings
        if not compat.set_enum(view_settings, 'view_transform', 'Standard'):
            self.report(type = {'WARNING'},
                        message = "Could not set 'Standard' view transform, saved colors may be tone-mapped")
        if compat.set_none_look(view_settings) is None:
            self.report(type = {'WARNING'}, message = "Could not clear the view transform's look")
        view_settings.exposure = 0
        view_settings.gamma    = 1

        if map.file_format == 'PNG':
            img_settings.color_mode  = map.png_channels
            img_settings.color_depth = map.png_depth
            img_settings.compression = map.png_compression
        if map.file_format == 'JPEG':
            img_settings.color_mode = map.jpg_channels
            img_settings.quality    = map.jpg_quality
        if map.file_format == 'OPEN_EXR':
            img_settings.color_mode = map.exr_channels
            img_settings.color_depth = map.exr_depth
            if map.exr_depth == '32':
                img_settings.exr_codec    = map.exr_codec_32
            if map.exr_depth == '16':
                img_settings.exr_codec    = map.exr_codec_16

        # Clear image makes the background transparent, which needs an alpha channel in the file
        if map.clear_img:
            if map.file_format in {'PNG', 'OPEN_EXR'}:
                img_settings.color_mode = 'RGBA'
            elif context.scene.BakeLabProps.save_or_pack == 'SAVE':
                self.report(type = {'WARNING'}, message = "JPEG has no alpha channel, the transparent background won't be saved")

    def ReserveMaterials(self, obj):
        selected_objects = bpy.context.selected_objects
        active_object    = bpy.context.active_object
        
        SelectObject(obj)
        if len(obj.material_slots) == 0:
            bpy.ops.object.material_slot_add()
        for slot in obj.material_slots:
            # Objects sharing a mesh share its slots, which were already reserved
            if slot.material is not None and slot.material in self.material_copies:
                continue
            self.object_slots.append(slot)
            self.original_materials.append(slot.material)
            if slot.material is not None:
                original = slot.material
                slot.material = original.copy()
                self.material_originals[slot.material] = original
                self.material_copies.add(slot.material)

        SelectObjects(active_object,selected_objects)

        return (self.object_slots, self.original_materials)

    def RestoreMaterials(self):
        for i in range(0, min(len(self.object_slots), len(self.original_materials))):
            if self.object_slots[i] is not None:
                if self.object_slots[i].material is not None:
                    bpy.data.materials.remove(self.object_slots[i].material)
                self.object_slots[i].material = self.original_materials[i]
        self.object_slots.clear()
        self.original_materials.clear()
        self.material_copies.clear()
        self.material_originals.clear()
    
    def PrepareMaterials(self, context, dst_obj, src_obj_list, map, bake_image, job_materials=None):
        active_obj = context.active_object
        selected_objects = context.selected_objects
        
        converted = set() # Objects sharing a mesh share materials, convert each only once
        for obj in src_obj_list:
            SelectObject(obj)
            if len(obj.material_slots) == 0:
                bpy.ops.object.material_slot_add()
            for slot in obj.material_slots:
                if slot.material is None:
                    if job_materials is not None:
                        continue # the dst phase swaps empty slots to inert
                    slot.material = self.GetEmptyMaterial()
                mat = slot.material
                if mat in converted:
                    continue
                converted.add(mat)
                if job_materials is not None and self.material_originals.get(mat, mat) not in job_materials:
                    continue # other materials keep their nodes; the dst phase swaps their slots
                
                if map.type == 'CustomPass':
                    if map.deep_search:
                        self.ungroup_nodes(mat.node_tree)
                    self.passes_to_emit_node(mat, map.pass_name)
                if map.type == 'Albedo':
                    self.ungroup_nodes(mat.node_tree)
                    self.passes_to_emit_node(mat, 'Albedo,Color,Base Color,Col,Paint Color')
                if map.type == 'Subsurface':
                    self.ungroup_nodes(mat.node_tree)
                    self.passes_to_emit_node(mat, 'Subsurface Weight,Subsurface')
                if map.type == 'Displacement':
                    self.displacement_to_color(mat)
                    
        ###################
        
        SelectObject(dst_obj)
        if len(dst_obj.material_slots) == 0:
            bpy.ops.object.material_slot_add()
        for slot in dst_obj.material_slots:
            mat = slot.material
            orig = None if mat is None else self.material_originals.get(mat, mat)
            if job_materials is not None and orig not in job_materials:
                # Cycles bakes each face into its own material's image node, so
                # other materials' faces are excluded by giving their slot a
                # material without any image node.
                if mat is not None:
                    self.material_copies.discard(mat)
                    bpy.data.materials.remove(mat)
                slot.material = self.GetInertMaterial()
                continue
            if mat is None:
                slot.material = self.GetEmptyMaterial()
                mat = slot.material
            if self.TMP_IMAGE_NODE_NAME in mat.node_tree.nodes:
                img_node = mat.node_tree.nodes[self.TMP_IMAGE_NODE_NAME]
            else:
                img_node = mat.node_tree.nodes.new(type = 'ShaderNodeTexImage')
                img_node.name = self.TMP_IMAGE_NODE_NAME
            mat.node_tree.nodes.active = img_node
            img_node.image = bake_image
            
        SelectObjects(active_obj, selected_objects)
            
    def GetEmptyMaterial(self):
        mat = bpy.data.materials.new(self.TMP_EMPTY_MAT_NAME)
        compat.enable_nodes(mat)
        img_node = mat.node_tree.nodes.new(type = 'ShaderNodeTexImage')
        img_node.name = self.TMP_IMAGE_NODE_NAME
        return mat

    def GetInertMaterial(self):
        """A material without an image node: Cycles skips its faces while
        baking, which is how material batch jobs exclude other materials."""
        mat = bpy.data.materials.new(self.TMP_INERT_MAT_NAME)
        compat.enable_nodes(mat)
        return mat
    
    def create_merged_object(self, context, object_list):
        ##### Create New Object{
        merged_mesh = bpy.data.meshes.new('BAKELAB_MERGED_MESH_TMP')
        merged_obj  = bpy.data.objects.new('BAKELAB_MERGED_OBJ_TMP', merged_mesh)
        # Track ownership before any modifier or join can fail.
        self.merged_object = merged_obj
        merged_obj.location = 0, 0, 0
        context.scene.collection.objects.link(merged_obj)
        merged_mesh.update()
        ##### }
        
        uv_name = 'BAKELAB_BAKE_UV_TMP'
        existing_names = {uv.name for obj in object_list for uv in obj.data.uv_layers}
        while uv_name in existing_names:
            uv_name += '_'
        for obj in object_list:
            SelectObject(obj)
            result = bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
            obj_clone = context.active_object
            # A failed duplicate leaves the original active; raising before the
            # try keeps the finally-cleanup from removing the user's own object.
            if 'FINISHED' not in result or obj_clone == obj:
                raise RuntimeError('Could not duplicate %r for merged bake' % obj.name)

            clone_data = obj_clone.data
            try:
                for modifier in list(obj_clone.modifiers):
                    if modifier.show_render:
                        if modifier.type == 'SUBSURF':
                            modifier.levels = modifier.render_levels
                        bpy.ops.object.modifier_apply(modifier=modifier.name)

                # Joining matches layers by name. Each object's selected bake UV
                # must reach the same destination layer even if its name differs.
                source_uv = obj_clone.data.uv_layers.active
                if source_uv is None:
                    raise RuntimeError('Merged bake source has no active UV map')
                coordinates = [tuple(loop.uv) for loop in source_uv.data]
                bake_uv = obj_clone.data.uv_layers.new(name=uv_name)
                for loop, coordinate in zip(bake_uv.data, coordinates):
                    loop.uv = coordinate
                compat.set_active_uv_layer(obj_clone.data.uv_layers, bake_uv)

                SelectObject(merged_obj)
                obj_clone.select_set(True)
                bpy.ops.object.join()
                obj_clone = None # join removed the clone
            finally:
                if obj_clone is not None:
                    bpy.data.objects.remove(obj_clone, do_unlink=True)
                if clone_data.users == 0:
                    bpy.data.meshes.remove(clone_data)
        
        while len(merged_obj.material_slots)>0:
            bpy.ops.object.material_slot_remove()

        uv_layers = merged_mesh.uv_layers
        bake_uv = uv_layers[uv_name]
        compat.set_active_uv_layer(uv_layers, bake_uv)
        bake_uv.active_render = True
        merged_mesh.update()
        return merged_obj
    
    def down_scale(self, img, props, map):
        if map.use_udim or map.final_aa == 1:
            # image.scale() only touches the base tile of a UDIM image, so
            # UDIM maps bake at final size and are never downscaled
            return
        img.scale(map.target_width, map.target_height)
    
    def UpdateDisplayStatus(self, props, obj, map, image):
        props.baking_obj_name = obj.name
        if map.type == 'CustomPass':
            props.baking_map_type = map.pass_name + '(Custom Pass)'
        else:
            props.baking_map_type = map.type
        props.baking_map_name = image.name
        props.baking_map_size = str(map.target_width) + 'x' + str(map.target_height)
        if map.final_aa != 1:
            props.baking_map_size += str(' (' + str(map.final_aa)+'X)')

    def run_bake(self, bake_type, bake_image):
        """Start a bake job and wait for it to end. Returns True if it baked into the image."""
        while bpy.app.is_job_running('OBJECT_BAKE'):
            yield 1
        was_dirty = bake_image.is_dirty
        uv_layer = compat.active_uv_name(bpy.context.active_object)
        # PrepareImage already replaces images when clearing is requested. Using
        # Blender's masked write preserves their transparent background; use_clear
        # replaces the whole buffer, including opaque pixels outside UV coverage.
        if self.headless:
            # Without a window there is no event loop to poll: EXEC_DEFAULT
            # runs the bake to completion before returning.
            completed = 'FINISHED' in bpy.ops.object.bake(
                'EXEC_DEFAULT', type=bake_type, uv_layer=uv_layer, use_clear=False)
        else:
            self.bake_result = None
            if bpy.ops.object.bake('INVOKE_DEFAULT', type=bake_type, uv_layer=uv_layer,
                                   use_clear=False) != {'RUNNING_MODAL'}:
                self.report(type = {'ERROR'}, message = 'Bake could not start, see the Info editor for the reason')
                return False
            while self.bake_result is None:
                yield 1
            # Errors inside the bake job are still reported as complete, but leave the image untouched
            completed = self.bake_result == 'COMPLETE'
        if not completed or not (was_dirty or bake_image.is_dirty):
            self.report(type = {'ERROR'}, message = 'Bake was cancelled or failed, see the Info editor for the reason')
            return False
        return True

    def on_bake_complete(self, *args):
        self.bake_result = 'COMPLETE'

    def on_bake_cancel(self, *args):
        self.bake_result = 'CANCEL'

    def store_image(self, bake_image, props):
        if props.save_or_pack == 'PACK':
            bake_image.pack()
            return
        bake_image.save_render(bake_image.filepath)
        # Generated images are regenerated blank when the .blend is reopened,
        # so switch it to the file that was just saved. TILED images keep their
        # source: the flip does not apply and reload() would drop tile buffers.
        if bake_image.source == 'GENERATED':
            color_space = bake_image.colorspace_settings.name
            bake_image.source = 'FILE'
            bake_image.reload()
            bake_image.colorspace_settings.name = color_space

    def remove_merged_object(self):
        if self.merged_object is None:
            return
        # Its placeholder materials aren't reserved, so they're never restored and removed
        for slot in self.merged_object.material_slots:
            if slot.material is not None and slot.material.name.startswith(self.TMP_EMPTY_MAT_NAME):
                bpy.data.materials.remove(slot.material)
        merged_data = self.merged_object.data
        bpy.data.objects.remove(self.merged_object)
        bpy.data.meshes.remove(merged_data)
        self.merged_object = None

    def Bake(self, context):
        yield 1
        scene = context.scene
        props = scene.BakeLabProps

        props.bake_state = 'BAKING'
        scene.render.engine = 'CYCLES'
        self.cycles.device = props.compute_device
        if not self.headless:
            # Pausing the viewport preview only matters with a UI, and Cycles'
            # update callback tag_redraws a nonexistent area in background mode
            self.cycles.preview_pause = True
        scene.render.bake.use_cage = True
        scene.render.bake.cage_extrusion = props.cage_extrusion
        scene.render.bake.max_ray_distance = props.max_ray_distance
        scene.render.bake.cage_object = None

        try:
            jobs = self.build_jobs(context)
        except RuntimeError as exc:
            self.report(type = {'ERROR'}, message = str(exc))
            yield -1
            return

        if len(scene.BakeLabMaps) == 0:
            self.report(type = {'ERROR'}, message = 'Add bake maps')
            yield -1
            return

        props.baking_map_index = 0
        props.baking_map_count = 0
        for map in scene.BakeLabMaps:
            if map.enabled:
                props.baking_map_count += 1
        props.baking_job_index = 0
        props.baking_job_count = len(jobs)
        failed_jobs = []

        for job in jobs:
            props.baking_job_index += 1
            props.baking_job_name = job.name
            props.baking_obj_index = 0
            props.baking_obj_count = len(job.objects)
            job_data_start = len(scene.BakeLab_Data)
            try:
                ok = yield from self.bake_job(context, job)
            except Exception as exc:
                traceback.print_exc()
                self.report(type = {'ERROR'}, message = 'Job "%s" failed: %s' % (job.name, exc))
                ok = False
            if not ok:
                data = scene.BakeLab_Data
                while len(data) > job_data_start:
                    data.remove(len(data) - 1)
                failed_jobs.append(job.name)
                if self.cancel_requested:
                    self.report(type = {'WARNING'}, message = 'Bake cancelled')
                    yield -1
                    return
                if len(jobs) == 1:
                    yield -1
                    return

        if failed_jobs:
            if len(failed_jobs) == len(jobs):
                self.report(type = {'ERROR'}, message = 'All %d bake jobs failed' % len(failed_jobs))
                yield -1
                return
            self.report(type = {'WARNING'},
                        message = 'Baked with %d failed job(s): %s'
                                  % (len(failed_jobs), ', '.join(failed_jobs)))
        props.bake_state = 'BAKED'
        yield 0 #Done

    def used_materials(self, obj):
        """Materials the object's polygons actually reference, in slot order.
        A slot material with zero faces would produce a batch job that bakes
        nothing, so the MATERIAL source ignores it."""
        me = obj.data
        slots = obj.material_slots
        if len(me.polygons) == 0 or len(slots) == 0:
            return []
        indices = array('i', [0]) * len(me.polygons)
        me.polygons.foreach_get('material_index', indices)
        used = {}  # dict as ordered set
        for index in indices:
            if 0 <= index < len(slots):
                mat = slots[index].material
                if mat is not None:
                    used[mat] = None
        return list(used)

    def build_jobs(self, context):
        """The bake queue. Pre-bake validation errors raise RuntimeError with
        the message to report; per-job validation stays in the job bodies."""
        props = context.scene.BakeLabProps
        source = props.batch_source
        if props.bake_mode == 'TO_ACTIVE' and source != 'SELECTION':
            raise RuntimeError('Selected to Active baking needs the Selection batch source')
        if source == 'MATERIAL' and props.bake_mode == 'ALL_TO_ONE' and props.pre_join_mesh:
            # Joining drops material slots, so faces can no longer be attributed
            # to a material job.
            raise RuntimeError('By Material batching cannot be combined with Pre-Join Meshes')

        if source == 'SELECTION':
            if len(self.default_selected_objects) == 0:
                raise RuntimeError('Select some objects')
            objects = [obj for obj in self.default_selected_objects if IsValidMesh(self, obj)]
            if len(objects) == 0:
                raise RuntimeError('No valid objects selected, see console for more info')
            return [BakeJob('Selection', objects, self.default_active_object)]

        if source == 'MATERIAL':
            if len(self.default_selected_objects) == 0:
                raise RuntimeError('Select some objects')
            objects = [obj for obj in self.default_selected_objects if IsValidMesh(self, obj)]
            if len(objects) == 0:
                raise RuntimeError('No valid objects selected, see console for more info')
            jobs_by_material = {}
            for obj in objects:
                materials = self.used_materials(obj)
                if not materials:
                    self.report(type = {'INFO'},
                                message = 'Object "%s" has no materials on its faces and was skipped' % obj.name)
                    continue
                for mat in materials:
                    jobs_by_material.setdefault(mat, []).append(obj)
            if len(jobs_by_material) == 0:
                raise RuntimeError('No materials found on the selected objects')
            if props.bake_mode == 'INDIVIDUAL' and len(jobs_by_material) > 1:
                self.report(type = {'INFO'},
                            message = 'Individual Objects names images per object, so material jobs '
                                      'overwrite earlier results unless Clear image is off')
            return [BakeJob(mat.name, objs, self.default_active_object,
                            image_name = mat.name, materials = {mat})
                    for mat, objs in jobs_by_material.items()]

        if source == 'COLLECTION':
            if props.batch_collection is not None:
                collections = [props.batch_collection]
                if props.batch_include_children:
                    collections.extend(iter_child_collections(props.batch_collection))
            else:
                collections = list(context.scene.collection.children)
            jobs = []
            for col in collections:
                objects = [obj for obj in col.objects if IsValidMesh(self, obj)]
                if len(objects) == 0:
                    self.report(type = {'INFO'},
                                message = 'Collection "%s" has no valid mesh objects and was skipped' % col.name)
                    continue
                jobs.append(BakeJob(col.name, objects, self.default_active_object,
                                    image_name = col.name))
            if len(jobs) == 0:
                raise RuntimeError('No collections with valid mesh objects to bake')
            return jobs

        # SCENE
        objects = [obj for obj in context.scene.collection.all_objects if IsValidMesh(self, obj)]
        if len(objects) == 0:
            raise RuntimeError('No valid mesh objects in the scene')
        return [BakeJob(context.scene.name, objects, self.default_active_object,
                        image_name = context.scene.name)]

    def bake_job(self, context, job):
        props = context.scene.BakeLabProps
        try:
            if props.bake_mode == "INDIVIDUAL":
                return (yield from self.bake_job_individual(context, job))
            if props.bake_mode == "ALL_TO_ONE":
                return (yield from self.bake_job_all_to_one(context, job))
            return (yield from self.bake_job_to_active(context, job))
        finally:
            # A failed job must not strand reserved materials or the merged
            # object; both are no-ops when there is nothing to clean.
            self.RestoreMaterials()
            self.remove_merged_object()

    def bake_job_individual(self, context, job):
        scene = context.scene
        render = scene.render
        props = scene.BakeLabProps
        for obj in job.objects:
            if len(obj.data.uv_layers) == 0:
                self.report(type = {'ERROR'}, message = 'Not all objects have UV maps')
                return False
        render.bake.use_selected_to_active = False

        for obj in job.objects:
            # Save baking data {
            baked_data = scene.BakeLab_Data.add()
            baked_data.AddObj(obj)
            # }
            props.baking_obj_index += 1
            SelectObject(obj)
            props.baking_map_index = 0
            for map in scene.BakeLabMaps:
                if not map.enabled:
                    continue
                props.baking_map_index += 1

                self.ReserveMaterials(obj)
                bake_image = self.PrepareImage(context, map, {obj}, obj.name)
                self.PrepareMaterials(context, obj, {obj}, map, bake_image, job.materials)
                bake_type = self.init_bake_settings(context, map)

                self.UpdateDisplayStatus(props,obj,map,bake_image)

                if not (yield from self.run_bake(bake_type, bake_image)):
                    return False
                if map.clear_img:
                    self.apply_transparent_background(bake_image)

                self.down_scale(bake_image, props, map)
                self.store_image(bake_image, props)

                baked_data.AddMap(map, bake_image) # Save baking data
                self.RestoreMaterials()
        return True

    ##########################################################################################
    def bake_job_all_to_one(self, context, job):
        scene = context.scene
        render = scene.render
        props = scene.BakeLabProps
         # Check UVs {
        for obj in job.objects:
            if len(obj.data.uv_layers) == 0:
                self.report(type = {'ERROR'}, message = 'Not all objects have UV maps')
                return False
        # }

         # Save baking data {
        baked_data = scene.BakeLab_Data.add()
        for obj in job.objects:
            baked_data.AddObj(obj)
        # }

        if props.pre_join_mesh:
            render.bake.use_selected_to_active = True
            render.bake.use_cage = True
            render.bake.cage_extrusion = props.cage_extrusion
            render.bake.max_ray_distance = props.max_ray_distance

            self.merged_object = self.create_merged_object(context, job.objects)
            merged_object = self.merged_object
            SelectObjects(merged_object, job.objects)
        else:
            render.bake.use_selected_to_active = False

        props.baking_map_index = 0

        for map in scene.BakeLabMaps:
            if not map.enabled:
                continue
            props.baking_map_index += 1

            if props.pre_join_mesh:
                for obj in job.objects:
                    self.ReserveMaterials(obj)

                bake_image = self.PrepareImage(context, map, {merged_object}, (job.image_name or props.global_image_name))
                self.PrepareMaterials(context, merged_object, job.objects, map, bake_image, job.materials)
                bake_type = self.init_bake_settings(context, map)

                self.UpdateDisplayStatus(props, merged_object, map, bake_image)

                if not (yield from self.run_bake(bake_type, bake_image)):
                    return False
                if map.clear_img:
                    self.apply_transparent_background(bake_image)

                self.RestoreMaterials()

                self.down_scale(bake_image, props, map)
                self.store_image(bake_image, props)
            else:
                bake_image = self.PrepareImage(context, map, job.objects, (job.image_name or props.global_image_name))
                for obj in job.objects:
                    SelectObject(obj)
                    self.ReserveMaterials(obj)

                    self.PrepareMaterials(context, obj, {obj}, map, bake_image, job.materials)
                    bake_type = self.init_bake_settings(context, map)

                    self.UpdateDisplayStatus(props, obj, map, bake_image)

                    if not (yield from self.run_bake(bake_type, bake_image)):
                        return False
                    self.RestoreMaterials()

                if map.clear_img:
                    self.apply_transparent_background(bake_image)

                self.down_scale(bake_image, props, map)
                self.store_image(bake_image, props)

            baked_data.AddMap(map, bake_image) # Save baking data

        self.remove_merged_object()
        return True

    ##########################################################################################
    def bake_job_to_active(self, context, job):
        scene = context.scene
        render = scene.render
        props = scene.BakeLabProps
        if len(job.objects) < 2:
            self.report(type = {'ERROR'}, message = 'Select atleast two mesh objects')
            return False
        # The active object's materials are only preserved if it's one of the selected objects
        if job.active_object not in job.objects:
            self.report(type = {'ERROR'}, message = 'Active object must be a selected mesh with faces')
            return False
        if len(job.active_object.data.uv_layers) == 0:
            self.report(type = {'ERROR'}, message = 'Active object does not have UV maps')
            return False
        render.bake.use_selected_to_active = True
        render.bake.use_cage = True
        render.bake.cage_extrusion = props.cage_extrusion
        render.bake.max_ray_distance = props.max_ray_distance

         # Save baking data {
        baked_data = scene.BakeLab_Data.add()
        baked_data.AddObj(job.active_object)
        # }

        SelectObjects(job.active_object, job.objects)

        props.baking_map_index = 0

        for map in scene.BakeLabMaps:
            if not map.enabled:
                continue
            props.baking_map_index += 1

            for obj in job.objects:
                self.ReserveMaterials(obj)

            bake_image = self.PrepareImage(context, map, {job.active_object}, job.active_object.name)
            self.PrepareMaterials(
                context, 
                job.active_object, 
                [obj for obj in job.objects 
                    if obj is not job.active_object], 
                map, 
                bake_image,
                job.materials
            )
            bake_type = self.init_bake_settings(context, map)

            self.UpdateDisplayStatus(props, job.active_object, map, bake_image)

            if not (yield from self.run_bake(bake_type, bake_image)):
                return False
            if map.clear_img:
                self.apply_transparent_background(bake_image)

            self.down_scale(bake_image, props, map)
            self.store_image(bake_image, props)

            baked_data.AddMap(map, bake_image) # Save baking data
            self.RestoreMaterials()
        return True

    ##########################################################################################
    def modal(self, context, event):
        # Esc during a bake is handled by the bake job itself, which then reports a cancel
        if event.type == 'ESC' and event.value == 'PRESS':
            self.cancel_requested = True

        if event.type == 'TIMER':
            if self.cancel_requested and not bpy.app.is_job_running('OBJECT_BAKE'):
                self.report(type = {'WARNING'}, message = 'Bake cancelled')
                self.cancel(context)
                return {'CANCELLED'}
            if context.scene.BakeLabProps.bake_state == 'BAKING' and context.area:
                context.area.tag_redraw() # Update UI
            try:
                result = next(self.BakeCrt)
            except Exception as exc:
                traceback.print_exc()
                self.report(type={'ERROR'}, message=f'Bake failed: {exc}')
                self.cancel(context)
                return {'CANCELLED'}
            if result == -1:
                self.cancel(context)
                return {'CANCELLED'}
            if result == 0:
                self.finish(context)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        try:
            context.scene.BakeLabProps.bake_state = 'NONE'
            # Partial records must not be applied to a later successful bake.
            data = context.scene.BakeLab_Data
            while len(data) > self._baked_data_start:
                data.remove(len(data) - 1)
        finally:
            self.finish(context)

    def finish(self, context):
        if self._finished:
            return
        self._finished = True
        # One failed restoration must not strand handlers, timers, or other data.
        actions = [self.RestoreMaterials, self.remove_merged_object]
        if self._defaults_saved:
            actions.append(lambda: self.restore_defaults(context))
        if self.BakeCrt is not None:
            actions.append(self.BakeCrt.close)
        for handlers, handler in self._bake_handlers:
            actions.append(lambda handlers=handlers, handler=handler:
                           handlers.remove(handler) if handler in handlers else None)
        if self._timer is not None:
            timer = self._timer
            self._timer = None
            actions.append(lambda: context.window_manager.event_timer_remove(timer))
        for action in actions:
            try:
                action()
            except Exception as exc:
                traceback.print_exc()
                self.report(type={'WARNING'}, message=f'Bake cleanup failed: {exc}')

    def detect_headless(self, context):
        """Background mode has no event loop to drive a modal operator.
        context.window still reports a dummy Window under `blender -b`, so
        bpy.app.background is the reliable signal."""
        return bool(bpy.app.background) or getattr(context, 'window', None) is None

    def execute(self, context):
        # Cycles backs every bake type here, but on 4.2 its add-on can be
        # disabled, and then scene.cycles is absent. Enable it up front so the
        # save/bake path has a settings struct to read, or bail cleanly.
        if compat.ensure_cycles(context.scene) is None:
            self.report(type = {'ERROR'},
                        message = 'Cycles is required for baking and could not be enabled')
            return {'CANCELLED'}
        self.original_materials = []
        self.object_slots = []
        self.material_copies = set()
        self.material_originals = {}
        self.merged_object = None
        self.cancel_requested = False
        self.bake_result = None
        self._finished = False
        self._defaults_saved = False
        self._timer = None
        self._bake_handlers = ()
        self.BakeCrt = None
        self.headless = False
        self._udim_aa_warned = False
        self._baked_data_start = len(context.scene.BakeLab_Data)
        try:
            self.save_defaults(context)
            self._defaults_saved = True
            self._bake_handlers = (
                (bpy.app.handlers.object_bake_complete, self.on_bake_complete),
                (bpy.app.handlers.object_bake_cancel, self.on_bake_cancel),
            )
            for handlers, handler in self._bake_handlers:
                handlers.append(handler)

            self.BakeCrt = self.Bake(context)
            # No event loop in background mode: drive the generator
            # synchronously instead of registering a timer and a modal handler.
            self.headless = self.detect_headless(context)
            if self.headless:
                return self.run_headless(context)
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.5, window=context.window)
            wm.modal_handler_add(self)
        except Exception as exc:
            traceback.print_exc()
            self.report(type={'ERROR'}, message=f'Bake could not start: {exc}')
            self.cancel(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def run_headless(self, context):
        """Run the bake generator to completion without a window or timer, so
        scripted `blender -b` bakes work. There is no Esc cancellation here;
        the run is synchronous to the end."""
        while True:
            try:
                result = next(self.BakeCrt)
            except StopIteration:
                result = 0
            except Exception as exc:
                traceback.print_exc()
                self.report(type={'ERROR'}, message=f'Bake failed: {exc}')
                self.cancel(context)
                return {'CANCELLED'}
            if result == -1:
                self.cancel(context)
                return {'CANCELLED'}
            if result == 0:
                self.finish(context)
                return {'FINISHED'}
