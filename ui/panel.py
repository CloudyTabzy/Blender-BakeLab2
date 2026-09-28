from bpy.types import (
            Panel
        )
from ..utils.tools import material_has_wired_alpha


def bake_readiness(context):
    """Preflight checklist for the Bake button. Mirrors what the baker
    validates and auto-fixes, so the panel can say what will happen
    before the button is clicked. Returns (status, label) pairs;
    status is 'ok', 'info' or 'warn'."""
    props = context.scene.BakeLabProps
    checks = []
    if props.batch_source != 'SELECTION':
        checks.append(('info', 'Bakes a %s batch, not just the selection'
                               % props.batch_source.title()))
    else:
        meshes = [o for o in context.selected_objects
                  if o.type == 'MESH' and len(o.data.polygons) > 0]
        if props.bake_mode == 'TO_ACTIVE':
            active_ok = context.active_object in meshes
            checks.append(('ok' if active_ok and len(meshes) > 1 else 'warn',
                           'Needs an active mesh plus source objects'))
            targets = (context.active_object,) if active_ok else ()
        else:
            checks.append(('ok' if meshes else 'warn',
                           '%d mesh object%s selected'
                           % (len(meshes), 's' if len(meshes) != 1 else '')))
            targets = meshes
        missing = [o.name for o in targets if len(o.data.uv_layers) == 0]
        if missing:
            checks.append(('warn', 'Missing UV map: ' + ', '.join(missing[:3])
                                   + (' ...' if len(missing) > 3 else '')))
        elif targets:
            checks.append(('ok', 'UV maps present'))
    if props.bake_mode == 'TO_ACTIVE' and props.batch_source != 'SELECTION':
        checks.append(('warn', 'Selected to Active needs the Selection batch'))
    if (props.batch_source == 'MATERIAL' and props.bake_mode == 'ALL_TO_ONE'
            and props.pre_join_mesh):
        checks.append(('warn', 'By Material cannot use Pre-Join Meshes'))
    maps = context.scene.BakeLabMaps
    enabled = sum(1 for m in maps if m.enabled)
    if len(maps) == 0:
        checks.append(('info', 'No maps yet - a default Albedo map is added'))
    elif enabled == 0:
        checks.append(('warn', 'All bake maps are disabled'))
    else:
        checks.append(('ok', '%d bake map%s enabled'
                       % (enabled, 's' if enabled != 1 else '')))
    if props.batch_source == 'SELECTION' and not any(m.type == 'Alpha' for m in maps):
        if any(material_has_wired_alpha(slot.material)
               for o in context.selected_objects if o.type == 'MESH'
               for slot in o.material_slots):
            checks.append(('info', 'Wired Alpha input - an Alpha map will be added'))
    return checks


class BakeLabUI(Panel):
    bl_label = "BakeLab"
    bl_space_type = 'VIEW_3D'
    bl_idname = "BAKELAB_PT_ui"
    bl_region_type = 'UI'
    bl_context = "objectmode"
    bl_category = "BakeLab"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.use_property_decorate = False
        props = scene.BakeLabProps

        if props.bake_state == 'NONE':
            checks = bake_readiness(context)
            has_blocker = any(status == 'warn' for status, _ in checks)

            col = layout.column()
            col.scale_y = 1.5
            # Every 'warn' item is a real blocker, so the checklist doubles
            # as the button's enabled state
            col.enabled = not has_blocker
            col.operator("bakelab.bake", text = 'Bake', icon='RENDER_STILL')

            box = layout.box()
            col = box.column(align = True)
            icons = {'ok': 'CHECKMARK', 'info': 'INFO', 'warn': 'CANCEL'}
            for status, label in checks:
                col.label(text = label, icon = icons[status])
            
            row = layout.row(align = True)
            row.operator("bakelab.unwrap", icon='UV')
            row.operator("bakelab.clear_uv", icon='UV')

            layout.separator()
            
            col = layout.column(align=True)
            col.label(text="Bake mode:")
            row = col.row(align = True)
            row.prop(props, "bake_mode", text='')
            row.prop(props, "show_bake_settings", icon = 'PREFERENCES')
            if props.show_bake_settings:
                box = col.box()
                col = box.column()
                col.use_property_split = True
                col.use_property_decorate = False
                col.prop(props, "bake_margin")
                if props.bake_mode == "TO_ACTIVE":
                    col.prop(props, "cage_extrusion")
                    col.prop(props, "max_ray_distance")
                if props.bake_mode == "ALL_TO_ONE":
                    col.prop(props, "global_image_name")
                    col.prop(props, "pre_join_mesh")
                    if props.pre_join_mesh:
                        col.prop(props, "cage_extrusion")
                        col.prop(props, "max_ray_distance")
            
            layout.separator()
            
            col = layout.column(align=True)
            col.label(text="Batch:")
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(props, "batch_source", text='Source')
            if props.batch_source == 'COLLECTION':
                col.prop(props, "batch_collection")
                col.prop(props, "batch_include_children")
            if props.bake_mode == 'TO_ACTIVE' and props.batch_source != 'SELECTION':
                col.label(text="Selected to Active needs Selection", icon='ERROR')
            if (props.batch_source == 'MATERIAL' and props.bake_mode == 'ALL_TO_ONE'
                    and props.pre_join_mesh):
                col.label(text="By Material cannot use Pre-Join", icon='ERROR')
            
            layout.separator()
            
            layout.prop(props, "compute_device")
            col = layout.column(align=True)
            col.use_property_split = True
            col.use_property_decorate = False
            row = col.row(align=True)
            row.prop(props, "image_size")
            if props.image_size == 'ADAPTIVE':
                row.prop(props, "adaptive_image_Settings", icon='PREFERENCES')
                if props.adaptive_image_Settings:
                    box = col.box()
                    col = box.column()
                    col.prop(props, "texel_per_unit")
                    row = col.row(align = True)
                    row.use_property_split = False
                    row.prop(props, "image_min_size")
                    row.prop(props, "image_max_size")
                    col.prop(props, "round_adaptive_image")
                
            layout.use_property_split = True
            layout.prop(props, "anti_alias")
            if any(m.enabled and m.use_udim for m in scene.BakeLabMaps):
                layout.label(text="UDIM maps ignore anti-aliasing", icon = 'INFO')
            layout.prop(props, "save_or_pack", expand=True)
            layout.use_property_split = False
            if props.save_or_pack == "SAVE":
                layout.prop(props, "save_path")
                layout.prop(props, "create_folder")
                # Matches PrepareImage's folder choice: Folder name is only
                # used for a single Selection job; batches get per-job folders
                if props.bake_mode == "ALL_TO_ONE" and props.batch_source == 'SELECTION':
                    layout.prop(props, "folder_name")
            else:
                layout.label(text = "")
            col = layout.column()
            col.label(text = "Maps:")
            box = col.box()
            col = box.column(align = True)
            row = col.split(align = True)
            row.operator("bakelab.newmapitem", icon='ADD', text="")
            row.operator("bakelab.removemapitem", icon='REMOVE', text="")
            
            col.template_list("BAKELAB_MAP_UL_list", "", scene,
                            "BakeLabMaps", scene, "BakeLabMapIndex", rows=2, maxrows=5)
            
            ##################################################
            if scene.BakeLabMapIndex >= 0 and scene.BakeLabMaps:
                item = scene.BakeLabMaps[scene.BakeLabMapIndex]
                col = col.column()
                col.use_property_split = True
                col.use_property_decorate = False
                col.enabled = item.enabled
                col.separator()
                subcol = col.column(align = True)
                row = subcol.row(align = True)
                row.prop(item, "type")
                row.prop(props, "show_map_settings", icon = 'PREFERENCES')
                
                if props.show_map_settings:
                    box = subcol.box()
                    scol = box.column()
                    row = scol.row()
                    row.enabled = not item.use_udim
                    row.prop(item, 'aa_override')
                    if item.type != 'CustomPass':
                        scol.prop(item, 'color_space')
                    if item.type in {
                        'Combined',
                        'Diffuse',
                        'Glossy',
                        'Transmission',
                        'Normal'
                    }:
                        row = box.row()
                        row.use_property_split = False
                        if item.type == 'Combined':
                            row = box.row(align = True)
                            row.use_property_split = False
                            row.prop(item, "combined_direct", toggle = True)
                            row.prop(item, "combined_indirect", toggle = True)
                            
                            sub_box_col = box.column(align = True)
                            sub_box_col.use_property_split = False
                            row = sub_box_col.row(align = True)
                            row.prop(item, "combined_diffuse", toggle = True)
                            #row.prop(item, "combined_subsurface", toggle = True)
                            
                            row = sub_box_col.row(align = True)
                            row.prop(item, "combined_glossy", toggle = True)
                            #row.prop(item, "combined_ambient_occlusion", toggle = True)
                            
                            row = sub_box_col.row(align = True)
                            row.prop(item, "combined_transmission", toggle = True)
                            row.prop(item, "combined_emit", toggle = True)
                            
                        if item.type in {
                            'Diffuse',
                            'Glossy',
                            'Transmission'
                        }:
                            row = box.row(align = True)
                            row.use_property_split = False
                            row.prop(item, "bake_direct", toggle = True)
                            row.prop(item, "bake_indirect", toggle = True)
                            row.prop(item, "bake_color", toggle = True)
                            
                        if item.type == 'Normal':
                            box.prop(item, "normal_space")
                            
                        subcol.separator()
                        
                if item.type == 'CustomPass':
                    col.label(text='Property Name')
                    row = col.row(align = True)
                    row.use_property_split = False
                    row.prop(item, "pass_name", text='')
                    row.operator_menu_enum(
                        'bakelab.show_pass_presets',
                        'pass_presets',
                        icon = 'PRESET',
                        text = ''
                    )
                    col.prop(item, 'color_space')
                    col.prop(item, "deep_search")
                
                if item.type == 'Displacement':
                    if not item.float_depth:
                        col.label(text="Use 32 bit float type", icon = 'INFO')
                    if props.save_or_pack == 'SAVE':
                        if item.file_format != 'OPEN_EXR':
                            col.label(text="Use EXR format", icon = 'INFO')
                
                col.separator()
                    
                col.prop(item, "samples")
                
                col.separator()
                col.prop(item, "img_name")
                col.prop(item, "clear_img")
                col.prop(item, "use_udim")
                if item.use_udim:
                    col.label(text="Bakes at final size, AA disabled", icon = 'INFO')

                subcol = col.column(align = True)
                if props.image_size == 'FIXED':
                    subcol.prop(item, "width")
                    subcol.prop(item, "height")
                elif props.image_size == 'ADAPTIVE':
                    subcol.prop(item, "image_scale")
                
                col.separator()
                col.prop(item, "float_depth")
                if props.save_or_pack == 'SAVE':
                    row = col.row()
                    row.prop(item, "file_format")
                    row.prop(props, "show_file_settings", icon = 'PREFERENCES')
                    if item.clear_img:
                        if item.file_format == 'JPEG':
                            col.label(text="JPEG can't store transparency", icon = 'ERROR')
                        else:
                            col.label(text="Saved as RGBA for transparency", icon = 'INFO')
                    if props.show_file_settings:
                        subcol = col.column()
                        if item.file_format == "PNG":
                            row = subcol.row()
                            row.prop(item, "png_channels", expand = True)
                            row = subcol.row()
                            row.prop(item, "png_depth", expand = True)
                            subcol.prop(item, "png_compression")
                        if item.file_format == "JPEG":
                            row = subcol.row()
                            row.prop(item, "jpg_channels", expand = True)
                            subcol.prop(item, "jpg_quality")
                        if item.file_format == "OPEN_EXR":
                            row = subcol.row()
                            row.prop(item, "exr_channels", expand = True)
                            row = subcol.row()
                            row.prop(item, "exr_depth", expand = True)
                            if item.exr_depth == '32':
                                subcol.prop(item, "exr_codec_32")
                            if item.exr_depth == '16':
                                subcol.prop(item, "exr_codec_16")
        
        else:
            if props.bake_state == 'BAKING':
                layout.label(text = 'Baking', icon = 'RENDER_STILL')
                if props.baking_job_count > 1:
                    row = layout.row()
                    row.label(text = 'Job:')
                    row.label(
                        text =
                            str(props.baking_job_index) + ' of ' +
                            str(props.baking_job_count) + '  (' + props.baking_job_name + ')'
                    )
                if props.bake_mode == 'INDIVIDUAL':
                    row = layout.row()
                    row.label(text = 'Objects:')
                    row.label(
                        text = 
                            str(props.baking_obj_index) + ' of ' + 
                            str(props.baking_obj_count)
                    )
                row = layout.row()
                row.label(text = 'Maps:')
                row.label(
                    text = 
                        str(props.baking_map_index) + ' of ' + 
                        str(props.baking_map_count)
                )
                
                layout.separator()
                
                if props.bake_mode == 'INDIVIDUAL':
                    row = layout.row()
                    row.label(text = 'Current Object:')
                    row.label(text = props.baking_obj_name)
                
                row = layout.row()
                row.label(text = 'Current Image:')
                row.label(text = props.baking_map_name)
                row = layout.row()
                row.label(text = '')
                row.label(text = props.baking_map_size)
                
                row = layout.row()
                row.label( text = 'Type:')
                row.label( text = props.baking_map_type)
                layout.template_running_jobs()
            elif props.bake_state == 'BAKED':
                layout.label(text = 'Baked', icon = 'CHECKMARK')
                
                if props.baking_job_count > 1:
                    row = layout.row()
                    row.label(text = 'Jobs:')
                    row.label(text = str(props.baking_job_count))
                
                if props.bake_mode == 'INDIVIDUAL':
                    row = layout.row()
                    row.label(text = 'Objects:')
                    row.label(text = str(props.baking_obj_count))
                
                row = layout.row()
                row.label(text = 'Total images: ')
                # Counted from the actual baked records: exact for every mode
                # and across batch jobs (the old map_count x obj_count formula
                # only described the last job)
                row.label(text = str(sum(len(entry.map_list) for entry in scene.BakeLab_Data)))
                
                layout.separator()
                
                layout.prop(props, "apply_only_selected")
                layout.prop(props, "make_single_user")
                layout.operator("bakelab.generate_mats", icon='MATERIAL')
                layout.operator("bakelab.apply_ao", icon='SHADING_RENDERED')
                layout.operator("bakelab.apply_displace", icon='RNDCURVE')
                layout.separator()
                layout.operator("bakelab.finish")
