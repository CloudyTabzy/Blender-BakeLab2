"""Run with blender --background --factory-startup --python-exit-code 1 --python tests/blender_regressions.py."""

import importlib.util
import inspect
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import bpy


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'bakelab_regression_addon', ROOT / '__init__.py',
    submodule_search_locations=[str(ROOT)],
)
ADDON = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ADDON
SPEC.loader.exec_module(ADDON)
BAKE = ADDON.bakelab_bake
POST = ADDON.bakelab_post
COMPAT = ADDON.bakelab_compat  # fails loudly if __init__.py stops importing it

# Blender operators cannot be instantiated as ordinary Python objects. Bind the
# production methods to a plain object; all scene/node/image operations stay real.
BakerMethods = type('BakerMethods', (), {
    name: value for name, value in vars(BAKE.Baker).items()
    if inspect.isfunction(value) or name.isupper()
})


class BackgroundBaker(BakerMethods):
    def __init__(self):
        self.report = Mock()

    def detect_headless(self, context):
        # These tests run under `blender -b` but exercise the modal machinery
        # with a fake window and simulated TIMER events.
        return False

    def run_bake(self, bake_type, bake_image):
        def invoke(_mode, **kwargs):
            # Use real Cycles baking, synchronously, without a UI event loop.
            settings = bpy.context.scene.render.bake
            for name in ('margin', 'use_clear', 'use_selected_to_active',
                         'use_cage', 'cage_extrusion', 'max_ray_distance'):
                kwargs.setdefault(name, getattr(settings, name))
            result = bpy.ops.object.bake('EXEC_DEFAULT', **kwargs)
            if result == {'FINISHED'}:
                self.on_bake_complete()
                return {'RUNNING_MODAL'}
            return result

        proxy = SimpleNamespace(
            app=bpy.app, context=bpy.context,
            ops=SimpleNamespace(object=SimpleNamespace(bake=invoke)),
        )
        with patch.object(BAKE, 'bpy', proxy):
            return (yield from super().run_bake(bake_type, bake_image))


class TestContext:
    def __init__(self):
        self.window_manager = SimpleNamespace(
            event_timer_add=Mock(return_value=object()),
            event_timer_remove=Mock(), modal_handler_add=Mock(),
        )
        # Baker.execute treats context.window None as headless; the modal-driven
        # tests must look windowed even under `blender -b`.
        self.window = SimpleNamespace()

    def __getattr__(self, name):
        return getattr(bpy.context, name)


class HeadlessContext(TestContext):
    def __init__(self):
        super().__init__()
        self.window = None


class HeadlessBaker(BakerMethods):
    """Drives the production headless path: no run_bake override, no timer."""

    def __init__(self):
        self.report = Mock()


class _BakeLabTestBase(unittest.TestCase):
    def setUp(self):
        self.scene = bpy.context.scene
        self.scene.BakeLab_Data.clear()
        self.scene.BakeLabMaps.clear()
        for objects in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                        bpy.data.images, bpy.data.node_groups, bpy.data.textures):
            for item in list(objects):
                objects.remove(item, do_unlink=True)
        self.cycles = COMPAT.ensure_cycles(self.scene)
        if self.cycles is None:
            self.skipTest('Cycles add-on is not available')
        self.cycles.device = 'CPU'
        self.props = self.scene.BakeLabProps
        for name in self.props.bl_rna.properties.keys():
            if name != 'rna_type':
                self.props.property_unset(name)
        self.props.compute_device = 'CPU'
        self.props.bake_margin = 0
        self.props.make_single_user = False
        self.baker = self.make_baker()
        self.addCleanup(self.cleanup_baker)

    def make_baker(self):
        return BackgroundBaker()

    def cleanup_baker(self):
        if hasattr(self.baker, '_finished') and not self.baker._finished:
            self.baker.cancel(self.context())

    def context(self):
        return TestContext()

    def plane(self, name='Plane', color=(0, 0, 0, 1), uv_name='BakeUV', offset=0):
        bpy.ops.mesh.primitive_plane_add()
        obj = bpy.context.object
        obj.name = name
        original = obj.data.uv_layers.active
        uv = obj.data.uv_layers.new(name=uv_name)
        for loop in uv.data:
            loop.uv *= 0.5
            loop.uv.x += offset
        obj.data.uv_layers.active = uv
        original.active_render = True
        mat = bpy.data.materials.new(name + '_material')
        mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color
        obj.data.materials.append(mat)
        return obj, mat

    def bake_map(self, map_type='Albedo'):
        item = self.scene.BakeLabMaps.add()
        item.type = map_type
        item.width = item.height = 16
        item.samples = 1
        item.img_name = '*_' + map_type
        return item

    def run_pipeline(self):
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        for _ in range(10):
            result = self.baker.modal(context, SimpleNamespace(type='TIMER'))
            if result != {'RUNNING_MODAL'}:
                self.assertEqual(result, {'FINISHED'}, self.baker.report.call_args_list)
                return context
        self.fail('Bake did not finish')

    def assert_coverage(self, image, expected):
        pixels = image.pixels
        alpha = [pixels[i] for i in range(3, len(pixels), 4)]
        self.assertEqual(sum(a > 0.5 for a in alpha), expected)
        self.assertTrue(all(a < 0.01 or a > 0.99 for a in alpha))

    def multi_material_grid(self, name='Grid', color_a=(1, 0, 0, 1), color_b=(0, 1, 0, 1),
                            uv_name='BakeUV', uv_scale=1.0):
        """2x2 grid, UVs spanning [0, uv_scale]; polys 0-1 (bottom UV half) get
        material A, polys 2-3 (top half) get material B — the fixture for
        per-material bake isolation. uv_scale=0.5 keeps everything inside UDIM
        tile 1001."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2)
        obj = bpy.context.object
        obj.name = name
        me = obj.data
        original = me.uv_layers.active
        uv = me.uv_layers.new(name=uv_name)
        for dst, src in zip(uv.data, original.data):
            dst.uv = src.uv * uv_scale
        me.uv_layers.active = uv
        original.active_render = True
        mat_a = bpy.data.materials.new(name + '_A')
        mat_a.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color_a
        mat_b = bpy.data.materials.new(name + '_B')
        mat_b.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color_b
        obj.data.materials.append(mat_a)
        obj.data.materials.append(mat_b)
        for poly in me.polygons:
            poly.material_index = 0 if poly.index < 2 else 1
        return obj, mat_a, mat_b

    def reported_messages(self):
        return [call.kwargs.get('message', '') for call in self.baker.report.call_args_list]

    def drive_to_end(self, context, limit=10):
        result = {'RUNNING_MODAL'}
        for _ in range(limit):
            result = self.baker.modal(context, SimpleNamespace(type='TIMER'))
            if result != {'RUNNING_MODAL'}:
                break
        return result

    def udim_plane(self, name, color, tx, ty, uv_name='BakeUV'):
        """Plane whose bake UVs land in UDIM tile 1001 + tx + ty*10."""
        obj, mat = self.plane(name, color, uv_name)
        uv = obj.data.uv_layers[uv_name]
        for loop in uv.data:
            loop.uv.x += tx
            loop.uv.y += ty
        obj.location = (tx * 3, ty * 3, 0)
        return obj, mat

    def assert_tile_file(self, directory, stem, number, coverage, color=None):
        """Verify a tile through its saved file: per-tile image.pixels access
        is unreliable in memory, but reloaded tile files are plain images."""
        path = os.path.join(directory, '%s_%d.png' % (stem, number))
        self.assertTrue(os.path.exists(path), 'missing tile file ' + path)
        tile = bpy.data.images.load(path, check_existing=False)
        self.addCleanup(bpy.data.images.remove, tile)
        self.assert_coverage(tile, coverage)
        if color is not None:
            pixels = tile.pixels
            i = (4 * tile.size[0] + 4) * 4  # inside the plane's [0,0.5] UV quadrant
            self.assertEqual(tuple(round(pixels[i + c]) for c in range(3)), color)


class BakeLabRegressions(_BakeLabTestBase):
    def test_black_bake_uses_selected_uv_and_keeps_alpha_when_packed(self):
        obj, mat = self.plane()
        self.bake_map()
        context = self.run_pipeline()
        data = self.scene.BakeLab_Data[0]
        image = data.map_list[0].image
        self.assert_coverage(image, 64)
        self.assertTrue(image.packed_file)
        self.assertEqual(obj.active_material, mat)
        self.assertTrue(obj.data.uv_layers['UVMap'].active_render)
        self.assertEqual(data.obj_list[0].uv_layer, 'BakeUV')
        context.window_manager.event_timer_remove.assert_called_once()
        # Changing the editing UV after baking must not change the baked layout.
        obj.data.uv_layers.active = obj.data.uv_layers['UVMap']
        self.assertEqual(bpy.ops.bakelab.generate_mats(), {'FINISHED'})
        self.assertTrue(obj.data.uv_layers['BakeUV'].active_render)

    def test_black_bake_keeps_alpha_in_saved_png(self):
        self.plane()
        self.bake_map()
        with tempfile.TemporaryDirectory() as directory:
            self.props.save_or_pack = 'SAVE'
            self.props.save_path = directory
            self.props.create_folder = False
            self.run_pipeline()
            image = self.scene.BakeLab_Data[0].map_list[0].image
            self.assertEqual(image.source, 'FILE')
            exported = bpy.data.images.load(image.filepath, check_existing=False)
            self.assert_coverage(exported, 64)
            bpy.data.images.remove(exported)

    def test_saved_png_keeps_un_tone_mapped_colors(self):
        # Guards the compat view_transform/none-look path: with the scene on
        # AgX, a pure red Albedo must save as pure red, not tone-mapped
        self.plane(color=(1, 0, 0, 1))
        self.bake_map()
        with tempfile.TemporaryDirectory() as directory:
            self.props.save_or_pack = 'SAVE'
            self.props.save_path = directory
            self.props.create_folder = False
            self.run_pipeline()
            image = self.scene.BakeLab_Data[0].map_list[0].image
            exported = bpy.data.images.load(image.filepath, check_existing=False)
            self.addCleanup(bpy.data.images.remove, exported)
            pixels = exported.pixels
            color = [pixels[i] for i in range(4)]
            self.assertEqual(color, [1.0, 0.0, 0.0, 1.0])

    def assert_atlas_uvs(self, pre_join):
        first, _ = self.plane('First', uv_name='FirstBake')
        second, _ = self.plane('Second', uv_name='SecondBake', offset=0.5)
        second.location.x = 3
        first.select_set(True)
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.pre_join_mesh = pre_join
        self.bake_map()
        self.run_pipeline()
        data = self.scene.BakeLab_Data[0]
        self.assert_coverage(data.map_list[0].image, 128)
        self.assertEqual({d.uv_layer for d in data.obj_list}, {'FirstBake', 'SecondBake'})
        self.assertFalse(any(o.name.startswith('BAKELAB_MERGED') for o in bpy.data.objects))

    def test_atlas_preserves_each_objects_selected_uv(self):
        self.assert_atlas_uvs(pre_join=False)

    def test_prejoined_atlas_preserves_each_objects_selected_uv(self):
        self.assert_atlas_uvs(pre_join=True)

    def test_selected_to_active_uses_destination_uv(self):
        destination, mat = self.plane('Destination')
        source, _ = self.plane('Source')
        source.location.z = 0.01
        destination.select_set(True)
        bpy.context.view_layer.objects.active = destination
        self.props.bake_mode = 'TO_ACTIVE'
        self.bake_map()
        self.run_pipeline()
        self.assert_coverage(self.scene.BakeLab_Data[0].map_list[0].image, 64)
        self.assertEqual(destination.active_material, mat)

    def test_reused_image_preserves_pixels_outside_bake_uv(self):
        obj, _ = self.plane()
        item = self.bake_map()
        item.clear_img = False
        image = bpy.data.images.new(item.img_name.replace('*', obj.name), width=16, height=16, alpha=True)
        image.pixels[:] = [0, 0, 1, 1] * 256
        self.run_pipeline()
        self.assertEqual(self.scene.BakeLab_Data[0].map_list[0].image, image)
        self.assertEqual(tuple(image.pixels[:4]), (0, 0, 0, 1))
        self.assertEqual(tuple(image.pixels[-4:]), (0, 0, 1, 1))

    def test_normal_background_and_antialiasing_preserve_coverage(self):
        self.plane()
        self.bake_map('Normal')
        self.props.anti_alias = 2
        self.run_pipeline()
        image = self.scene.BakeLab_Data[0].map_list[0].image
        self.assertEqual(tuple(image.size), (16, 16))
        self.assertGreater(image.pixels[(3 * 16 + 3) * 4 + 3], 0.99)
        self.assertEqual(image.pixels[-1], 0)

    def group_material(self, socket_type='NodeSocketColor'):
        mat = bpy.data.materials.new('Grouped')
        group = bpy.data.node_groups.new('Group', 'ShaderNodeTree')
        group.interface.new_socket(name='Input', in_out='INPUT', socket_type=socket_type)
        group.interface.new_socket(name='Output', in_out='OUTPUT', socket_type=socket_type)
        inp = group.nodes.new('NodeGroupInput')
        out = group.nodes.new('NodeGroupOutput')
        instance = mat.node_tree.nodes.new('ShaderNodeGroup')
        instance.node_tree = group
        return mat, group, inp, out, instance

    def test_shader_group_inputs_linked_and_unlinked(self):
        for linked in (False, True):
            with self.subTest(linked=linked):
                mat, group, inp, out, instance = self.group_material('NodeSocketShader')
                mix = group.nodes.new('ShaderNodeMixShader')
                group.links.new(inp.outputs[0], mix.inputs[1])
                group.links.new(mix.outputs[0], out.inputs[0])
                nt = mat.node_tree
                source = nt.nodes.get('Principled BSDF').outputs[0]
                if linked:
                    nt.links.new(source, instance.inputs[0])
                nt.links.new(instance.outputs[0], nt.nodes.get('Material Output').inputs['Surface'])
                self.baker.ungroup_nodes(nt)
                copied = next(n for n in nt.nodes if n.type == 'MIX_SHADER')
                self.assertEqual(copied.inputs[1].is_linked, linked)
                if linked:
                    self.assertEqual(copied.inputs[1].links[0].from_socket, source)

    def test_direct_group_links_and_output_defaults(self):
        for mode in ('input_default', 'input_link', 'output_default'):
            with self.subTest(mode=mode):
                mat, group, inp, out, instance = self.group_material()
                nt = mat.node_tree
                if mode != 'output_default':
                    group.links.new(inp.outputs[0], out.inputs[0])
                    instance.inputs[0].default_value = (1, 0, 0, 1)
                    if mode == 'input_link':
                        rgb = nt.nodes.new('ShaderNodeRGB')
                        rgb.outputs[0].default_value = (1, 0, 0, 1)
                        nt.links.new(rgb.outputs[0], instance.inputs[0])
                else:
                    out.inputs[0].default_value = (1, 0, 0, 1)
                target = nt.nodes.get('Principled BSDF').inputs['Base Color']
                nt.links.new(instance.outputs[0], target)
                self.baker.ungroup_nodes(nt)
                self.assertFalse(any(n.type == 'GROUP' for n in nt.nodes))
                self.assertTrue(target.is_linked)
                self.assertEqual(tuple(target.links[0].from_socket.default_value), (1, 0, 0, 1))

    def test_nested_group_without_inputs_and_active_group_output(self):
        mat, group, inp, out, instance = self.group_material()
        group.nodes.remove(inp)
        rgb = group.nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = (1, 0, 0, 1)
        group.links.new(rgb.outputs[0], out.inputs[0])
        inactive = group.nodes.new('NodeGroupOutput')
        inactive.inputs[0].default_value = (0, 0, 1, 1)
        out.is_active_output = True
        outer = bpy.data.node_groups.new('Outer', 'ShaderNodeTree')
        outer.interface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
        outer_output = outer.nodes.new('NodeGroupOutput')
        nested = outer.nodes.new('ShaderNodeGroup')
        nested.node_tree = group
        outer.links.new(nested.outputs[0], outer_output.inputs[0])
        instance.node_tree = outer
        target = mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color']
        mat.node_tree.links.new(instance.outputs[0], target)
        self.baker.ungroup_nodes(mat.node_tree)
        self.assertFalse(any(n.type in {'GROUP', 'GROUP_INPUT', 'GROUP_OUTPUT'}
                             for n in mat.node_tree.nodes))
        self.assertEqual(tuple(target.links[0].from_socket.default_value), (1, 0, 0, 1))

    def test_ao_preserves_arbitrary_surface_socket_and_explicit_uv(self):
        for kind in ('ShaderNodeMixShader', 'ShaderNodeAddShader', 'ShaderNodeEmission'):
            with self.subTest(kind=kind):
                mat = bpy.data.materials.new(kind)
                nt = mat.node_tree
                source = nt.nodes.new(kind).outputs[0]
                out = nt.nodes.get('Material Output')
                nt.links.new(source, out.inputs['Surface'])
                image = bpy.data.images.new('AO', width=1, height=1)
                POST.BakeLab_ApplyAO.add_ao(None, image, mat, 'RecordedUV')
                mix = out.inputs['Surface'].links[0].from_node
                self.assertEqual(mix.inputs[2].links[0].from_socket, source)
                uv = next(n for n in nt.nodes if n.type == 'UVMAP')
                self.assertEqual(uv.uv_map, 'RecordedUV')

    def test_post_actions_keep_recorded_uv_after_active_uv_changes(self):
        obj, _ = self.plane()
        data = self.scene.BakeLab_Data.add()
        data.AddObj(obj)
        for kind in ('AO', 'Displacement'):
            item = self.bake_map(kind)
            data.AddMap(item, bpy.data.images.new(kind, width=1, height=1))
        obj.data.uv_layers.active = obj.data.uv_layers['UVMap']
        self.assertEqual(bpy.ops.bakelab.apply_ao(), {'FINISHED'})
        self.assertTrue(obj.data.uv_layers['UVMap'].active_render)
        uv = next(n for n in obj.active_material.node_tree.nodes if n.type == 'UVMAP')
        self.assertEqual(uv.uv_map, 'BakeUV')
        self.assertEqual(bpy.ops.bakelab.apply_displace(), {'FINISHED'})
        self.assertEqual(obj.modifiers[-1].uv_layer, 'BakeUV')

    def test_presets_extract_current_principled_values(self):
        presets = ADDON.bakelab_map.BakeLabShowPassPresets.__annotations__['pass_presets'].keywords['items']
        for names, label, _ in presets:
            with self.subTest(preset=label):
                mat = bpy.data.materials.new(label)
                pbr = mat.node_tree.nodes.get('Principled BSDF')
                socket = next((s for name in names.split(',') for s in pbr.inputs
                               if s.name.casefold() == name.strip().casefold()), None)
                self.assertIsNotNone(socket)
                if socket.type == 'RGBA':
                    socket.default_value = (0.25, 0.25, 0.25, 1)
                else:
                    socket.default_value = 0.25
                self.baker.passes_to_emit_node(mat, names)
                out = mat.node_tree.nodes.get('Material Output')
                emit = out.inputs['Surface'].links[0].from_node
                self.assertAlmostEqual(emit.inputs[0].default_value[0], 0.25)

    def test_output_failure_restores_materials_settings_and_resources(self):
        obj, original = self.plane()
        self.bake_map()
        engine = self.scene.render.engine
        img = self.scene.render.image_settings
        img.file_format = 'BMP'  # so the bake's PNG change must be undone
        saved_format = img.file_format
        saved_media_type = getattr(img, 'media_type', None)
        saved_transform = img.view_settings.view_transform
        saved_look = img.view_settings.look
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        with patch.object(self.baker, 'PrepareImage', side_effect=OSError('output denied')):
            self.baker.modal(context, SimpleNamespace(type='TIMER'))
            self.assertEqual(self.baker.modal(context, SimpleNamespace(type='TIMER')), {'CANCELLED'})
        self.assertEqual(obj.active_material, original)
        self.assertEqual(self.scene.render.engine, engine)
        self.assertEqual(img.file_format, saved_format)
        if COMPAT.SUPPORTS_IMAGE_MEDIA_TYPE:
            self.assertEqual(img.media_type, saved_media_type)
        self.assertEqual(img.view_settings.view_transform, saved_transform)
        self.assertEqual(img.view_settings.look, saved_look)
        self.assertEqual(self.props.bake_state, 'NONE')
        self.assertEqual(len(self.scene.BakeLab_Data), 0)
        for handlers, handler in self.baker._bake_handlers:
            self.assertNotIn(handler, handlers)
        context.window_manager.event_timer_remove.assert_called_once()
        self.baker.finish(context)
        context.window_manager.event_timer_remove.assert_called_once()

    def test_cleanup_continues_when_a_restoration_fails(self):
        self.plane()
        context = self.context()
        self.baker.execute(context)
        with patch.object(self.baker, 'RestoreMaterials', side_effect=RuntimeError('restore failed')):
            self.baker.cancel(context)
        context.window_manager.event_timer_remove.assert_called_once()
        for handlers, handler in self.baker._bake_handlers:
            self.assertNotIn(handler, handlers)
        self.assertEqual(self.props.bake_state, 'NONE')

    def test_startup_failure_removes_handlers_and_timer(self):
        self.plane()
        context = self.context()
        context.window_manager.modal_handler_add.side_effect = RuntimeError('startup failed')
        self.assertEqual(self.baker.execute(context), {'CANCELLED'})
        context.window_manager.event_timer_remove.assert_called_once()
        for handlers, handler in self.baker._bake_handlers:
            self.assertNotIn(handler, handlers)

    def test_prejoin_failure_removes_partial_merge_and_clone(self):
        obj, mat = self.plane()
        self.bake_map()
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.pre_join_mesh = True
        modifier = obj.modifiers.new('Invalid Boolean', 'BOOLEAN')
        # A disabled viewport modifier cannot be applied by Blender.
        modifier.show_viewport = False
        context = self.context()
        self.baker.execute(context)
        self.baker.modal(context, SimpleNamespace(type='TIMER'))
        self.assertEqual(self.baker.modal(context, SimpleNamespace(type='TIMER')), {'CANCELLED'})
        self.assertEqual(list(bpy.data.objects), [obj])
        self.assertEqual(obj.active_material, mat)
        self.assertFalse(any(m.name.startswith('BAKELAB_MERGED') for m in bpy.data.meshes))
        context.window_manager.event_timer_remove.assert_called_once()


class BatchBaking(_BakeLabTestBase):
    def test_batch_material_source_isolates_faces_per_job(self):
        obj, mat_a, mat_b = self.multi_material_grid()
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.img_name = '*'
        self.run_pipeline()
        data = self.scene.BakeLab_Data
        self.assertEqual(len(data), 2)
        images = {entry.map_list[0].image.name: entry.map_list[0].image for entry in data}
        self.assertEqual(set(images), {'Grid_A', 'Grid_B'})
        # Each job's atlas contains ONLY its own material's faces: A the bottom
        # UV half (red), B the top half (green).
        for name, color, y in (('Grid_A', (1, 0, 0), 4), ('Grid_B', (0, 1, 0), 12)):
            image = images[name]
            self.assert_coverage(image, 128)
            pixels = image.pixels
            i = (y * 16 + 8) * 4
            self.assertEqual(tuple(round(pixels[i + c]) for c in range(3)), color)
        self.assertTrue(all(slot.material in (mat_a, mat_b) for slot in obj.material_slots))

    def test_material_source_skips_unused_slot_material(self):
        # A material in a slot that no polygon references must not become a
        # job: it would bake nothing and report a misleading failure.
        obj, mat_a, mat_b = self.multi_material_grid()
        unused = bpy.data.materials.new('Unused')
        obj.data.materials.append(unused)
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.img_name = '*'
        self.run_pipeline()
        names = {entry.map_list[0].image.name for entry in self.scene.BakeLab_Data}
        self.assertEqual(names, {'Grid_A', 'Grid_B'})
        self.assertEqual(self.props.baking_job_count, 2)
        self.assertTrue(all(slot.material in (mat_a, mat_b, unused)
                            for slot in obj.material_slots))

    def test_batch_collection_source(self):
        col_a = bpy.data.collections.new('ColA')
        col_b = bpy.data.collections.new('ColB')
        self.scene.collection.children.link(col_a)
        self.scene.collection.children.link(col_b)
        obj_a, _ = self.plane('PlaneA')
        obj_b, _ = self.plane('PlaneB')
        col_a.objects.link(obj_a)
        col_b.objects.link(obj_b)
        # primitive_*_add links into the active collection (the factory scene's
        # default 'Collection'); keep each plane only in its test collection so
        # the default one is empty and must be skipped.
        for obj, keep in ((obj_a, col_a), (obj_b, col_b)):
            for col in list(obj.users_collection):
                if col is not keep:
                    col.objects.unlink(obj)
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'COLLECTION'
        item = self.bake_map()
        item.img_name = '*'
        self.run_pipeline()
        data = self.scene.BakeLab_Data
        self.assertEqual({entry.map_list[0].image.name for entry in data}, {'ColA', 'ColB'})
        for entry in data:
            self.assertEqual(len(entry.obj_list), 1)
        self.assertTrue(any('skipped' in m for m in self.reported_messages()),
                        self.reported_messages())

    def test_batch_scene_source_bakes_unselected_objects(self):
        self.plane('PlaneA')
        self.plane('PlaneB')
        bpy.ops.object.select_all(action='DESELECT')
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'SCENE'
        item = self.bake_map()
        item.img_name = '*'
        self.run_pipeline()
        data = self.scene.BakeLab_Data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].map_list[0].image.name, self.scene.name)
        self.assertEqual({o.obj.name for o in data[0].obj_list}, {'PlaneA', 'PlaneB'})

    def test_batch_failing_job_is_isolated(self):
        obj, mat_a, mat_b = self.multi_material_grid()
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.img_name = '*'
        original = self.baker.PrepareImage

        def flaky(context, map, objects, name):
            if name == 'Grid_B':
                raise OSError('job denied')
            return original(context, map, objects, name)

        with patch.object(self.baker, 'PrepareImage', side_effect=flaky):
            self.run_pipeline()  # one job failed, the batch still FINISHES
        data = self.scene.BakeLab_Data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].map_list[0].image.name, 'Grid_A')
        self.assertEqual(self.props.bake_state, 'BAKED')
        self.assertTrue(any('Grid_B' in m and 'failed' in m for m in self.reported_messages()),
                        self.reported_messages())
        self.assertTrue(all(slot.material in (mat_a, mat_b) for slot in obj.material_slots))

    def test_batch_all_jobs_fail_cancels(self):
        obj, mat_a, mat_b = self.multi_material_grid()
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.img_name = '*'
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        result = {'RUNNING_MODAL'}
        with patch.object(self.baker, 'PrepareImage', side_effect=OSError('denied')):
            for _ in range(10):
                result = self.baker.modal(context, SimpleNamespace(type='TIMER'))
                if result != {'RUNNING_MODAL'}:
                    break
        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(len(self.scene.BakeLab_Data), 0)
        self.assertEqual(self.props.bake_state, 'NONE')
        self.assertTrue(all(slot.material in (mat_a, mat_b) for slot in obj.material_slots))

    def test_batch_to_active_requires_selection_source(self):
        self.plane()
        self.props.bake_mode = 'TO_ACTIVE'
        self.props.batch_source = 'SCENE'
        self.bake_map()
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        result = {'RUNNING_MODAL'}
        for _ in range(10):
            result = self.baker.modal(context, SimpleNamespace(type='TIMER'))
            if result != {'RUNNING_MODAL'}:
                break
        self.assertEqual(result, {'CANCELLED'})
        self.assertTrue(any('Selected to Active baking needs the Selection batch source' in m
                            for m in self.reported_messages()), self.reported_messages())

    def test_batch_progress_props(self):
        self.multi_material_grid()
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.img_name = '*'
        self.run_pipeline()
        self.assertEqual(self.props.baking_job_count, 2)
        self.assertEqual(self.props.baking_job_index, 2)
        self.assertEqual(self.props.baking_job_name, 'Grid_B')


class UdimBaking(_BakeLabTestBase):
    def test_udim_bake_writes_every_tile(self):
        tile_a, _ = self.udim_plane('TileA', (1, 0, 0, 1), 0, 0)
        self.udim_plane('TileB', (0, 1, 0, 1), 1, 0)
        tile_a.select_set(True)  # primitive_*_add replaces the selection
        self.props.bake_mode = 'ALL_TO_ONE'
        item = self.bake_map()
        item.use_udim = True
        item.img_name = 'Atlas'
        with tempfile.TemporaryDirectory() as directory:
            self.props.save_or_pack = 'SAVE'
            self.props.save_path = directory
            self.props.create_folder = False
            self.run_pipeline()
            image = self.scene.BakeLab_Data[0].map_list[0].image
            self.assertEqual(image.source, 'TILED')
            self.assertEqual(COMPAT.tile_numbers(image), {1001, 1002})
            self.assertIn('<UDIM>', image.filepath)
            self.assertEqual(sorted(os.listdir(directory)),
                             ['Atlas_1001.png', 'Atlas_1002.png'])
            self.assert_tile_file(directory, 'Atlas', 1001, 64, (1, 0, 0))
            self.assert_tile_file(directory, 'Atlas', 1002, 64, (0, 1, 0))

    def test_udim_forces_aa_off(self):
        self.udim_plane('P', (1, 0, 0, 1), 0, 0)
        self.props.anti_alias = 2
        item = self.bake_map()
        item.use_udim = True
        item.aa_override = 4
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(item.final_aa, 1)
        self.assertEqual(tuple(image.tiles.get(1001).size), (16, 16))
        self.assertTrue(any('Anti-aliasing is disabled' in m for m in self.reported_messages()),
                        self.reported_messages())

    def test_udim_all_to_one_modes(self):
        for pre_join in (False, True):
            with self.subTest(pre_join=pre_join):
                # subTests share one setUp: start each iteration clean
                self.scene.BakeLabMaps.clear()
                self.scene.BakeLab_Data.clear()
                tile_a, _ = self.udim_plane('TileA', (1, 0, 0, 1), 0, 0)
                self.udim_plane('TileB', (0, 1, 0, 1), 1, 0)
                tile_a.select_set(True)  # primitive_*_add replaces the selection
                self.props.bake_mode = 'ALL_TO_ONE'
                self.props.pre_join_mesh = pre_join
                item = self.bake_map()
                item.use_udim = True
                item.img_name = 'Atlas'
                with tempfile.TemporaryDirectory() as directory:
                    self.props.save_or_pack = 'SAVE'
                    self.props.save_path = directory
                    self.props.create_folder = False
                    self.run_pipeline()
                    image = self.scene.BakeLab_Data[-1].map_list[0].image
                    self.assertEqual(COMPAT.tile_numbers(image), {1001, 1002})
                    self.assert_tile_file(directory, 'Atlas', 1001, 64, (1, 0, 0))
                    self.assert_tile_file(directory, 'Atlas', 1002, 64, (0, 1, 0))
                self.assertFalse(any(o.name.startswith('BAKELAB_MERGED') for o in bpy.data.objects))

    def test_udim_reuse_adds_missing_tiles(self):
        self.udim_plane('P', (1, 0, 0, 1), 1, 0)  # tile 1002 only
        image = COMPAT.new_tiled_image('P_Albedo', 16, 16, True)
        item = self.bake_map()
        item.use_udim = True
        item.clear_img = False
        self.run_pipeline()
        result = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(result, image)
        self.assertEqual(COMPAT.tile_numbers(result), {1001, 1002})

    def test_udim_replaces_non_tiled_image(self):
        self.udim_plane('P', (1, 0, 0, 1), 0, 0)
        bpy.data.images.new('P_Albedo', 16, 16)
        item = self.bake_map()
        item.use_udim = True
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(image.source, 'TILED')
        self.assertTrue(any('UDIM setting changed' in m for m in self.reported_messages()),
                        self.reported_messages())

    def test_udim_out_of_range_uvs_fail_the_job(self):
        obj, _ = self.plane()
        for loop in obj.data.uv_layers['BakeUV'].data:
            loop.uv.x -= 2  # negative tiles do not exist
        item = self.bake_map()
        item.use_udim = True
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        self.assertEqual(self.drive_to_end(context), {'CANCELLED'})
        self.assertEqual(len(self.scene.BakeLab_Data), 0)
        self.assertTrue(any('No UVs inside the UDIM tile range' in m
                            for m in self.reported_messages()), self.reported_messages())

    def test_udim_skips_u_beyond_ten_columns(self):
        # The UDIM grid is ten columns wide: u in [10, 10.5] computes tile
        # numbers that collide with row 1, and the engine bakes nothing there.
        self.udim_plane('Far', (1, 0, 0, 1), 10, 0)
        item = self.bake_map()
        item.use_udim = True
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'RUNNING_MODAL'})
        self.assertEqual(self.drive_to_end(context), {'CANCELLED'})
        self.assertEqual(len(self.scene.BakeLab_Data), 0)
        self.assertTrue(any('No UVs inside the UDIM tile range' in m
                            for m in self.reported_messages()), self.reported_messages())
        self.assertTrue(any('skipped' in m for m in self.reported_messages()),
                        self.reported_messages())

        # Mixed: only the out-of-grid corner is skipped, the valid tile bakes
        self.scene.BakeLabMaps.clear()
        obj, _ = self.udim_plane('Near', (1, 0, 0, 1), 0, 0)
        obj.data.uv_layers['BakeUV'].data[0].uv = (10.2, 0.25)
        item = self.bake_map()
        item.use_udim = True
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(COMPAT.tile_numbers(image), {1001})

    def test_udim_mixed_range_bakes_valid_tiles(self):
        obj, _ = self.udim_plane('P', (1, 0, 0, 1), 0, 0)
        obj.data.uv_layers['BakeUV'].data[0].uv = (-5.0, 0.25)
        item = self.bake_map()
        item.use_udim = True
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(COMPAT.tile_numbers(image), {1001})
        self.assertTrue(any('skipped' in m for m in self.reported_messages()),
                        self.reported_messages())

    def test_udim_pack_mode(self):
        self.udim_plane('P', (1, 0, 0, 1), 0, 0)
        item = self.bake_map()
        item.use_udim = True
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertTrue(image.packed_file)
        self.assertEqual(image.source, 'TILED')

    def test_udim_post_actions(self):
        obj, _ = self.udim_plane('P', (1, 0, 0, 1), 0, 0)
        item = self.bake_map()
        item.use_udim = True
        disp = self.bake_map('Displacement')
        disp.use_udim = True
        self.run_pipeline()
        image = self.scene.BakeLab_Data[-1].map_list[0].image
        self.assertEqual(bpy.ops.bakelab.generate_mats(), {'FINISHED'})
        tex = next(n for n in obj.active_material.node_tree.nodes if n.type == 'TEX_IMAGE')
        self.assertEqual(tex.image, image)
        self.assertEqual(tex.image.source, 'TILED')
        reporter = Mock()
        self.assertEqual(POST.BakeLab_ApplyDisplace.execute(reporter, bpy.context), {'FINISHED'})
        self.assertTrue(any('first tile' in str(call) for call in reporter.report.call_args_list),
                        reporter.report.call_args_list)


class HeadlessBaking(_BakeLabTestBase):
    """The production headless path: execute() drives the generator to
    completion without window, timer, or test-side run_bake proxies."""

    def make_baker(self):
        return HeadlessBaker()

    def context(self):
        return HeadlessContext()

    def test_headless_bake_completes_synchronously(self):
        self.plane()
        self.bake_map()
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'FINISHED'})
        image = self.scene.BakeLab_Data[0].map_list[0].image
        self.assert_coverage(image, 64)
        self.assertEqual(self.props.bake_state, 'BAKED')
        context.window_manager.event_timer_add.assert_not_called()
        for handlers, handler in self.baker._bake_handlers:
            self.assertNotIn(handler, handlers)
        self.assertFalse(bpy.app.is_job_running('OBJECT_BAKE'))

    def test_headless_error_cancels(self):
        self.bake_map()
        context = self.context()
        self.assertEqual(self.baker.execute(context), {'CANCELLED'})
        self.assertEqual(self.props.bake_state, 'NONE')
        self.assertEqual(len(self.scene.BakeLab_Data), 0)
        messages = [call.kwargs.get('message', '') for call in self.baker.report.call_args_list]
        self.assertTrue(any('Select some objects' in message for message in messages), messages)

    def test_headless_batch_udim_save(self):
        # End-to-end proof that tile_add under temp_override works in a
        # production headless session: two material jobs, both UDIM.
        obj, mat_a, mat_b = self.multi_material_grid(uv_scale=0.5)
        self.props.bake_mode = 'ALL_TO_ONE'
        self.props.batch_source = 'MATERIAL'
        item = self.bake_map()
        item.use_udim = True
        item.img_name = '*'
        context = self.context()
        with tempfile.TemporaryDirectory() as directory:
            self.props.save_or_pack = 'SAVE'
            self.props.save_path = directory
            self.props.create_folder = False
            self.assertEqual(self.baker.execute(context), {'FINISHED'})
            self.assertEqual(sorted(os.listdir(directory)),
                             ['Grid_A_1001.png', 'Grid_B_1001.png'])
            for stem in ('Grid_A', 'Grid_B'):
                path = os.path.join(directory, stem + '_1001.png')
                tile = bpy.data.images.load(path, check_existing=False)
                self.addCleanup(bpy.data.images.remove, tile)
                # The grid spans [0,0.5] UV (64 px); each material covers half.
                self.assert_coverage(tile, 32)


class CompatLayer(unittest.TestCase):
    """Version-agnostic invariants of bakelab_compat, run on every build."""

    def setUp(self):
        self.scene = bpy.context.scene

    def test_tiled_image_helpers(self):
        self.assertTrue(COMPAT.SUPPORTS_IMAGE_TILES)
        image = COMPAT.new_tiled_image('compat_tiles', 8, 8, True)
        self.addCleanup(bpy.data.images.remove, image)
        self.assertEqual(image.source, 'TILED')
        self.assertEqual(COMPAT.tile_numbers(image), {1001})
        self.assertNotEqual(tuple(image.tiles.get(1001).size), (0, 0))
        failed = COMPAT.ensure_tiles(bpy.context, image, {1001, 1002, 1003},
                                     8, 8, False, (0, 0, 0, 0))
        self.assertEqual(failed, [])
        self.assertEqual(COMPAT.tile_numbers(image), {1001, 1002, 1003})
        # Idempotent: already-initialized tiles are left alone.
        self.assertEqual(COMPAT.ensure_tiles(bpy.context, image, {1002}, 8, 8,
                                             False, (0, 0, 0, 0)), [])
        self.assertTrue(COMPAT.prune_tiles(bpy.context, image, {1002}))
        self.assertEqual(COMPAT.tile_numbers(image), {1002})

    def test_environment_is_logged(self):
        print('BAKELAB COMPAT:', COMPAT.describe_environment())

    def test_none_look_resolves_on_this_build(self):
        view_settings = self.scene.render.image_settings.view_settings
        saved_look = view_settings.look
        self.addCleanup(lambda: setattr(view_settings, 'look', saved_look))
        self.assertIsNotNone(COMPAT.set_none_look(view_settings))

    def test_color_space_for_every_map_identifier(self):
        identifiers = [item[0] for item in
                       ADDON.bakelab_map.BakeLabMap.__annotations__['color_space'].keywords['items']
                       if item]
        image = bpy.data.images.new('compat_cs', 1, 1)
        self.addCleanup(bpy.data.images.remove, image)
        for name in identifiers:
            self.assertIsNotNone(
                COMPAT.set_image_colorspace(image.colorspace_settings, name),
                'no color space accepted for %r' % name)

    def test_file_format_survives_video_media_type(self):
        settings = self.scene.render.image_settings
        saved_media = getattr(settings, 'media_type', None)
        saved_format = settings.file_format
        self.addCleanup(lambda: COMPAT.set_image_file_format(settings, saved_format, saved_media))
        if COMPAT.SUPPORTS_IMAGE_MEDIA_TYPE:
            settings.media_type = 'VIDEO'
        for fmt in ('PNG', 'JPEG', 'OPEN_EXR'):
            self.assertEqual(COMPAT.set_image_file_format(settings, fmt), fmt)

    def test_socket_at_resolves_ambiguous_names(self):
        mat = bpy.data.materials.new('compat_sockets')
        self.addCleanup(bpy.data.materials.remove, mat)
        COMPAT.enable_nodes(mat)
        mix = mat.node_tree.nodes.new('ShaderNodeMixShader')
        # bpy returns fresh wrappers per access: compare, never check identity
        self.assertEqual(COMPAT.input_socket(mix, 'Fac', 0), mix.inputs[0])
        self.assertEqual(COMPAT.input_socket(mix, 'Shader', 1), mix.inputs[1])
        self.assertEqual(COMPAT.input_socket(mix, 'Shader', 2), mix.inputs[2])
        self.assertEqual(COMPAT.output_socket(mix, 'Shader', 0), mix.outputs[0])

    def test_uv_activation_round_trip(self):
        bpy.ops.mesh.primitive_plane_add()
        obj = bpy.context.object
        mesh = obj.data
        second = mesh.uv_layers.new(name='CompatUV')
        self.assertTrue(COMPAT.set_active_uv_layer(mesh.uv_layers, second))
        self.assertEqual(COMPAT.active_uv_name(obj), 'CompatUV')
        self.assertTrue(COMPAT.set_active_uv_layer(mesh.uv_layers, mesh.uv_layers[0]))
        self.assertEqual(COMPAT.active_uv_name(obj), mesh.uv_layers[0].name)


if __name__ == '__main__':
    ADDON.register()
    try:
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(area=area):
            loader = unittest.defaultTestLoader
            suite = unittest.TestSuite([
                loader.loadTestsFromTestCase(BakeLabRegressions),
                loader.loadTestsFromTestCase(BatchBaking),
                loader.loadTestsFromTestCase(UdimBaking),
                loader.loadTestsFromTestCase(HeadlessBaking),
                loader.loadTestsFromTestCase(CompatLayer),
            ])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        ADDON.unregister()
    if not result.wasSuccessful():
        raise SystemExit(1)
