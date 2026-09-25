# BakeLab Gate Tests

Run these checks in **Blender 5.0+** before merging or releasing. Every
item must pass. Items marked *(regression)* cover specific bugs that have
been fixed, so they should never fail again.

## 0. Setup

1. Zip the repo root and install it via *Edit > Preferences > Get Extensions > Install from Disk*.
2. Open *Window > Toggle System Console* (Windows) or start Blender from a terminal, so Python errors are visible.
3. Test scene: default cube + a UV sphere (both with UVs, both with a Principled BSDF material). For section 3, also add a subdivided, displaced copy of the cube as the high-poly source.

**Gate rule:** no Python traceback in the console for any step below.

## 1. Registration

- [ ] Add-on enables without errors.
- [ ] *View3D > Sidebar > BakeLab* panel appears.
- [ ] Disabling and re-enabling the add-on works without errors.
- [ ] Bake settings show **Cage Extrusion** and **Max Ray Distance** in *Selected to Active* mode, and in *All To One* when *Pre-Join Meshes* is on.

## 2. Map types (Individual mode, 512x512, Pack)

Add each map type, bake the cube, and check that an image is produced and looks plausible:

- [ ] Albedo
- [ ] Normal
- [ ] Glossy
- [ ] Roughness
- [ ] Emission
- [ ] Diffuse
- [ ] Subsurface *(regression: used to pass invalid bake type `'Transmission'`)*
- [ ] Transmission *(regression: used to crash with `UnboundLocalError`)*
- [ ] Shadow
- [ ] Environment
- [ ] UV
- [ ] Combined
- [ ] Custom Pass (e.g. `Metallic`)
- [ ] Ambient Occlusion
- [ ] Displacement

## 3. Bake modes

- [ ] **Individual**: cube + sphere selected, Albedo map. Result: one image per object, named after it.
- [ ] **All To One** (Pre-Join off): cube + sphere, Albedo, *Clear image* **on**. Result: one `Atlas` image containing **both** objects *(regression: only the last object used to survive)*.
- [ ] **All To One** (Pre-Join on): same as above. The status display names the merged object while baking, and the temporary merged object is removed afterwards.
- [ ] **Selected to Active**: high-poly + low-poly cube, Normal map. Detail transfers, and the status display names the **active** object *(regression)*.
- [ ] **Max Ray Distance**: in Selected to Active, set it to a small non-zero value and confirm it's applied (*Render Properties > Bake > Selected to Active*). It's independent of Cage Extrusion *(regression: it used to copy the cage extrusion value)*. After the bake finishes, the scene's original bake settings are restored.

## 4. Image sizing

- [ ] **Fixed**: width/height match the map settings.
- [ ] **Adaptive** *(regression: used to crash with `NameError`/`TypeError`)*:
  - [ ] Bake succeeds, and the size follows `sqrt(surface area) * Texels Per Unit`.
  - [ ] Results are clamped between **Min Size** and **Max Size** (e.g. Max = 64 gives a 64x64 image).
  - [ ] *Round to power of two* gives power-of-two sizes.
  - [ ] Texels Per Unit = 0 doesn't crash (the size clamps to Min Size).
- [ ] **Anti-aliasing** = 2: the bake runs at 2x size, and the final image is downscaled back to the target size.

## 5. Clear image / transparency

- [ ] *Clear image* on: background pixels (pure black) get alpha 0, and the baked area stays opaque.
- [ ] 2048x2048 with AA 2 and *Clear image* on: the transparency pass finishes in about a second, not minutes *(regression: it used to be a pure-Python per-pixel loop)*.
- [ ] *Clear image* off with an existing image of the same name: the existing image is reused, not recreated.

## 6. Output

- [ ] **Pack**: images are packed into the .blend.
- [ ] **Save**, PNG / JPEG / OpenEXR: files are written to the chosen folder, and *Create folder* makes the per-object folder (Individual) or the *Folder name* folder (All To One).
- [ ] The color space is set correctly (sRGB for Albedo, Non-Color for Normal/Roughness).
- [ ] After the bake, the render settings (file format, color depth, engine, device, samples) are restored to what they were before.

## 7. Post-bake actions

- [ ] *Generate Materials* creates materials using the baked images.
- [ ] *Apply AO* / *Apply Displacement* work when those maps were baked.
- [ ] *Finish* returns the panel to its initial state.

## 8. Cancel / errors

- [ ] Pressing **Esc** during a bake cancels it cleanly and restores the original settings and materials.
- [ ] Bake with nothing selected: error "Select some objects", no traceback.
- [ ] Bake an object without UVs: error "Not all objects have UV maps", no traceback.
- [ ] Bake with no maps added: error "Add bake maps", no traceback.

## Optional: headless smoke test

This quick check needs no UI. It catches registration errors and invalid map-type to bake-type mappings. Install the extension first (step 0), then run:

```bash
blender -b --python-expr "
import bpy
bpy.ops.preferences.addon_enable(module='bl_ext.user_default.blender_bakelab')
from bl_ext.user_default.blender_bakelab import bakelab_bake, bakelab_map
valid = {i.identifier for i in bpy.ops.object.bake.get_rna_type().properties['type'].enum_items}
types = [i[0] for i in bakelab_map.BakeLabMap.__annotations__['type'].keywords['items'] if i]
for t in types:
    assert t in bakelab_bake.Baker.BAKE_TYPES, 'missing mapping: ' + t
    assert bakelab_bake.Baker.BAKE_TYPES[t] in valid, 'invalid bake type for ' + t
print('SMOKE OK')
"
```

Expected output includes `SMOKE OK`.
