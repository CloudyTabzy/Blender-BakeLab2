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
- [ ] Subsurface: bakes the material's **Subsurface Weight** (e.g. 0.3 gives a flat 0.3 grey, Non-Color). *Generate Materials* connects it to *Subsurface Weight* *(regression: used to bake the Transmission light pass)*
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
- [ ] **All To One** (Pre-Join on): same as above. The bake succeeds *(regression: used to fail with "No active UV layer found" on the merged object)*, the status display names the merged object while baking, and the temporary merged object is removed afterwards.
- [ ] **Selected to Active**: high-poly + low-poly cube, Normal map. Detail transfers, and the status display names the **active** object *(regression)*.
- [ ] **Selected to Active** with no active object (or an active object that isn't selected): error "Active object must be a selected mesh with faces", no traceback *(regression)*.
- [ ] **Shared meshes**: in Selected to Active (and All To One with Pre-Join), make the source a linked duplicate pair (*Alt+D*) sharing a material. After the bake, the original material still exists and is still assigned, with no `.001` copies left *(regression: the original material used to be deleted)*.
- [ ] **Max Ray Distance**: in Selected to Active, set it to a small non-zero value and confirm it's applied (*Render Properties > Bake > Selected to Active*). It's independent of Cage Extrusion *(regression: it used to copy the cage extrusion value)*. After the bake finishes, the scene's original bake settings are restored.

## 4. Image sizing

- [ ] **Fixed**: width/height match the map settings.
- [ ] **Adaptive** *(regression: used to crash with `NameError`/`TypeError`)*:
  - [ ] Bake succeeds, and the size follows `sqrt(surface area) * Texels Per Unit`.
  - [ ] Results are clamped between **Min Size** and **Max Size** (e.g. Max = 64 gives a 64x64 image).
  - [ ] Editing **Min Size** or **Max Size** doesn't crash Blender, and raising Min above Max pushes Max up (and vice versa) *(regression: stack overflow)*.
  - [ ] The map's **Image Scale** multiplies the size: a 2x2x2 cube at 10 Texels Per Unit gives 64x64, and 128x128 with Image Scale 2 *(regression: it was ignored)*.
  - [ ] *Round to power of two* gives power-of-two sizes.
  - [ ] Texels Per Unit = 0 doesn't crash (the size clamps to Min Size).
- [ ] **Anti-aliasing** = 2: the bake runs at 2x size, and the final image is downscaled back to the target size.

## 5. Materials

- [ ] **Node groups**: Albedo bake of a material whose Base Color comes from a node group that has **no Group Input** node (e.g. an RGB node inside a group). The bake finishes with the right color *(regression: Blender used to freeze, and grouped RGB/Value nodes baked as grey)*.

## 6. Clear image / transparency

- [ ] *Clear image* on: background pixels (pure black) get alpha 0, and the baked area stays opaque.
- [ ] 2048x2048 with AA 2 and *Clear image* on: the transparency pass finishes in about a second, not minutes *(regression: it used to be a pure-Python per-pixel loop)*.
- [ ] *Clear image* off with an existing image of the same name: the existing image is reused, not recreated, and resized to the map's size (times anti-aliasing while baking) *(regression: it kept its old size)*.

## 7. Output

- [ ] **Pack**: images are packed into the .blend.
- [ ] **Save**, PNG / JPEG / OpenEXR: files are written to the chosen folder, and *Create folder* makes the per-object folder (Individual) or the *Folder name* folder (All To One).
- [ ] The color space is set correctly (sRGB for Albedo, Non-Color for Normal/Roughness).
- [ ] **Saved colors are exact**: with the scene view transform on AgX (the default), save an Albedo of a pure red material as PNG. The file is pure red, not (0.86, 0.22, 0.13) *(regression: the view transform used to be written into the file)*.
- [ ] **Saved images survive reopening**: bake in Save mode, *Generate Materials*, save the .blend and reopen it. The textures still show the baked result, not black *(regression)*.
- [ ] After the bake, the render settings (file format, color depth, engine, device, samples) are restored to what they were before.

## 8. Post-bake actions

- [ ] *Generate Materials* creates materials using the baked images.
- [ ] *Apply AO* / *Apply Displacement* work when those maps were baked.
- [ ] *Finish* returns the panel to its initial state.

## 9. Cancel / errors

- [ ] Pressing **Esc** during a bake cancels it cleanly: original settings and materials are restored, and in Pre-Join mode the merged object is removed.
- [ ] Right-clicking during a bake does **not** cancel it.
- [ ] **A bake Blender rejects stops**: disable *Renders* for the object (*Object Properties > Visibility*) and bake. BakeLab reports an error, returns to the Bake button and restores the materials *(regression: it used to retry forever)*.
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
