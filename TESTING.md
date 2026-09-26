# BakeLab Gate Tests

Run these checks on **each supported version: Blender 4.2 LTS, 4.5 LTS, 5.0,
and 5.2 LTS** before merging or releasing. One extension zip serves all of
them; the gate is per version. Every item must pass. Items marked
*(regression)* cover specific bugs that have been fixed, so they should never
fail again.

## 0.1 Version matrix

Fill in at release time; a blank row blocks the release.

| Version | extension validated | regression suite OK | manual gate OK | compat report (media_type / tiles / look / sRGB / Non-Color / cycles) |
|---|---|---|---|---|
| 4.2 LTS | | | | |
| 4.5 LTS | | | | |
| 5.0 | | | | |
| 5.2 LTS | | | | |

The compat report column is the `BAKELAB COMPAT:` line the regression suite
prints; it makes a version-specific difference visible rather than mysterious.

## 0. Setup (per version)

Replace `<blender>` with that version's executable. Portable builds of
several Blender versions can sit side by side and do not share configs.

```bash
# build once, from the repository folder (any supported version)
<blender> --background --command extension build --output-dir dist
# validate the zip with every target version
<blender> --background --command extension validate dist/blender_bakelab-3.0.0.zip
# install headlessly (or via Edit > Preferences > Get Extensions > Install from Disk)
<blender> --background --command extension install-file -r user_default -e dist/blender_bakelab-3.0.0.zip
```

1. Open *Window > Toggle System Console* (Windows) or start Blender from a terminal, so Python errors are visible.
2. Test scene: default cube + a UV sphere (both with UVs, both with a Principled BSDF material). For section 3, also add a subdivided, displaced copy of the cube as the high-poly source.

**Version-specific expectations** (behavior differs, the code must not):
`media_type` in *Output Properties* exists only on 5.0+; colorspace names may
resolve to an OCIO alias (the compat report shows what was picked); BakeLab
enables the Cycles add-on for a session when it is off, without saving it to
preferences. All of this is absorbed in `bakelab_compat.py`.

**Gate rule:** no unexpected Python traceback. Deliberately triggered failures may
log diagnostics, but must restore the scene and leave BakeLab usable.

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
- [ ] Shader groups with linked or unlinked Shader inputs bake without errors. Direct Group Input → Group Output connections and unconnected output defaults retain their values, including inside nested groups.
- [ ] Custom Pass presets for Specular, Sheen, Clearcoat and Transmission extract the corresponding Principled weights rather than black.
- [ ] With different editing and render UV maps, the bake uses the editing UV map. Changing the editing map after baking does not change the UV map used by Generate Materials, Apply AO or Apply Displacement. Repeat All To One with Pre-Join enabled and differently named bake UV maps on the source objects.

## 6. Clear image / transparency

- [ ] *Clear image* on: pixels outside UV coverage have alpha 0, and baked black surfaces and zero-valued data remain opaque. Check Normal maps too; coverage must not depend on RGB values.
- [ ] **Transparency survives export**: with *Clear image* on, open the result in an external image editor. In **Save** mode (PNG, even with the channels set to RGB) the file is RGBA with a transparent background. In **Pack** mode, *Image > Save As* also writes RGBA with a transparent background *(regression: both used to write RGB and lose the alpha)*.
- [ ] *Clear image* on with **JPEG**: the panel warns that JPEG can't store transparency, and baking reports a warning.
- [ ] 2048x2048 with AA 2 and *Clear image* on: transparency is preserved after downscaling without a separate per-pixel background-removal pass.
- [ ] *Clear image* off with an existing image of the same name: the existing image is reused, not recreated, and resized to the map's size (times anti-aliasing while baking) *(regression: it kept its old size)*.

## 7. Output

- [ ] **Pack**: images are packed into the .blend.
- [ ] **Save**, PNG / JPEG / OpenEXR: files are written to the chosen folder, and *Create folder* makes the per-object folder (Individual) or the *Folder name* folder (All To One).
- [ ] The color space is set correctly (sRGB for Albedo, Non-Color for Normal/Roughness).
- [ ] **Saved colors are exact**: with the scene view transform on AgX (the default), save an Albedo of a pure red material as PNG. The file is pure red, not (0.86, 0.22, 0.13) *(regression: the view transform used to be written into the file)*.
- [ ] **Saved images survive reopening**: bake in Save mode, *Generate Materials*, save the .blend and reopen it. The textures still show the baked result, not black *(regression)*.
- [ ] After the bake, the render settings (file format, media type on 5.0+, color depth, engine, device, samples) are restored to what they were before.
- [ ] *(5.0+ only)* With the scene's *Output > Media Type* set to *Video* beforehand, a Save-mode bake still writes the chosen image format correctly, and the media type is restored afterwards.

## 8. Post-bake actions

- [ ] *Generate Materials* creates materials using the baked images.
- [ ] *Apply AO* / *Apply Displacement* work when those maps were baked.
- [ ] Apply AO accepts Mix Shader, Add Shader, Emission and grouped Surface outputs, preserving the existing shader connection.
- [ ] *Finish* returns the panel to its initial state.

## 9. Cancel / errors

- [ ] Pressing **Esc** during a bake cancels it cleanly: original settings and materials are restored, and in Pre-Join mode the merged object is removed.
- [ ] Right-clicking during a bake does **not** cancel it.
- [ ] **A bake Blender rejects stops**: disable *Renders* for the object (*Object Properties > Visibility*) and bake. BakeLab reports an error, returns to the Bake button and restores the materials *(regression: it used to retry forever)*.
- [ ] Bake with nothing selected: error "Select some objects", no traceback.
- [ ] Bake an object without UVs: error "Not all objects have UV maps", no traceback.
- [ ] Bake with no maps added: error "Add bake maps", no traceback.
- [ ] Bake with the **Cycles add-on disabled** (*Edit > Preferences > Extensions*): BakeLab enables it for the session and bakes; if enabling is not possible, it reports "Cycles is required for baking and could not be enabled" and the scene is untouched, no traceback.
- [ ] A failed image write restores original materials, scene settings and selection, removes temporary objects, and returns to the Bake button. A modifier failure during Pre-Join leaves no merged object or clone behind. Expected failures may log a diagnostic traceback, but must not leave BakeLab stuck.

## 10. UDIM (3.0+)

Test scene: a plane (or two) whose UVs span more than one UDIM tile, e.g. one
plane in tile 1001 and one in 1002. Add a map with **UDIM** enabled.

- [ ] The map's *UDIM* toggle shows the "Bakes at final size, AA disabled" note; *Anti-alias Override* is greyed out; a global note appears next to *Anti-aliasing* when any enabled map is UDIM.
- [ ] Baking creates one image whose *Source* is *UDIM Tiles*, with exactly the tiles the UVs cover (Image Editor shows 1001, 1002, ...).
- [ ] Each tile contains its own region's pixels (check in the Image Editor by switching tiles).
- [ ] **Save** mode writes one file per tile named `<image>_1001.png`, `<image>_1002.png`, ... into the chosen folder; **Pack** mode packs the tiled image.
- [ ] Bake margin is applied per tile (visual check on a tile edge).
- [ ] Anti-aliasing > 1 with a UDIM map: one warning "Anti-aliasing is disabled for UDIM maps", tiles bake at final size.
- [ ] Reuse: with *Clear image* off and an existing tiled image missing a tile, the missing tile is added and its content baked; existing tiles keep their pixels.
- [ ] An existing NON-tiled image with the target name is replaced with a warning ("UDIM setting changed"); and vice versa for a non-UDIM map.
- [ ] UVs entirely outside the valid UDIM grid (negative, u ≥ 10 — the grid is ten columns wide — or tile > 2000): the job fails cleanly with "No UVs inside the UDIM tile range"; partially outside: a warning reports the skipped coordinate count and valid tiles still bake.
- [ ] *Generate Materials* wires the tiled image into the texture node (UDIM sampling works in Cycles/EEVEE renders); *Apply Displacement* from a UDIM map warns "uses only the first tile".
- Known limitation: with *By Material* + UDIM, tiles are collected from the job objects' whole UV extent, so a material confined to one tile can still produce blank tile files covering other materials' regions.

Per-version note: tile initialization (`image.tile_add` under an edit-image
override), one-pass multi-tile baking, and `<UDIM>` saving were verified live
on 5.2 headless; the 4.2 API docs are identical, but every matrix row must
still run the automated suite (it covers all of the above via disk
round-trips) before release.

## 11. Batch / headless (3.0+)

- [ ] **Batch source** appears under Bake mode: Selection / By Material / Collection / Scene.
- [ ] *Selection* behaves exactly like previous versions (single job).
- [ ] *By Material* on a multi-material object (All To One): one job per material; **each job's image contains only that material's faces** (the other material's region stays transparent with Clear image on).
- [ ] *By Material* + *Pre-Join Meshes*: error "By Material batching cannot be combined with Pre-Join Meshes", nothing baked.
- [ ] *By Material* + Individual Objects: info report that per-object image names repeat across jobs.
- [ ] *Collection*: one job per collection (empty collections skipped with an info report); with a collection picked, its children are included only when *Include Child Collections* is on.
- [ ] *Scene*: bakes every valid mesh in the scene with nothing selected.
- [ ] *Selected to Active* with a non-Selection source: error "Selected to Active baking needs the Selection batch source".
- [ ] A job that fails (e.g. object with no UVs inside a multi-job batch) is reported as `Job "<name>" failed`, its partial records are dropped, its materials are restored, and the remaining jobs still bake; the run ends Baked with a warning naming the failed jobs.
- [ ] If every job fails, the run cancels and restores like a single failed bake.
- [ ] **Esc** during a batch cancels the whole queue and restores everything.
- [ ] The Baking panel shows `Job: i of N (name)` while batching, and the Baked panel shows the job count.
- [ ] SAVE-mode folders: All To One + Selection uses *Folder name*; every other job source uses a per-job folder (no cross-job file collisions).
- [ ] **Headless**: with a prepared .blend (maps + settings), this completes without a window and writes the outputs:

```bash
<blender> -b scene.blend --python-expr "
import bpy
bpy.ops.preferences.addon_enable(module='bl_ext.user_default.blender_bakelab')
print(bpy.ops.bakelab.bake())
print('HEADLESS BAKE DONE')"
```

Expected: `{'FINISHED'}` then `HEADLESS BAKE DONE`. There is no Esc
cancellation headless; the run is synchronous to the end.

## Automated regression suite

From the repository root, run with **every** supported version (the suite
loads the addon straight from the repo, so no install is needed):

```bash
<blender> --background --factory-startup --python-exit-code 1 --python tests/blender_regressions.py
```

The suite runs real Cycles bakes and checks image coverage, PNG output, image reuse,
all bake modes, saved UV choices, shader groups, AO connections, presets,
UDIM tile baking (verified through saved per-tile files, since in-memory
per-tile pixel access is unreliable), batch sources including per-material
face isolation, the headless synchronous driver, compat shims (`media_type`,
tiles, none-look, color spaces, sockets, UV activation, Cycles availability)
and cleanup after injected errors. It prints one
`BAKELAB COMPAT:` line to paste into the §0.1 matrix. It uses synchronous
baking and a simulated timer to run without a UI. Interactive Esc
cancellation still needs the manual checks above. Deliberately injected
errors print diagnostic tracebacks; the suite must finish with `OK` and exit
code 0 on every version.

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
