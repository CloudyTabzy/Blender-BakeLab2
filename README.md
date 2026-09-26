# Blender-BakeLab2
![Thumbnail](bakelab_thumbnail_text_logo_small.png)
BakeLab - A blender addon for baking images.<br>
Compatible with Blender 4.2 LTS through 5.2 from a single build.<br>
Current release: **3.0.0** (tag `v3`).

**Fork:** https://github.com/CloudyTabzy/Blender-BakeLab2

Main Features:
* Automatically create images, setup materials, bake objects and save/pack images in one click;
* Automatically generating materials;
* Anti-Aliased baking;
* Baking cycles displacement to real geometry;
* Bake any PBR attributes of your material by its name (Metallic, Roughness, Specular and etc);
* Adaptive image size by object's surface size;
* Unwrap and Bake Multiple Objects into one image;
* **UDIM-aware baking: one tile per UV tile, auto-detected, saved per tile**;
* **Batch/queue baking: by selection, material, collection or scene, with per-job error isolation**;
* **Headless baking: run batches from `blender -b` scripts**;
* **Per-map clear image option for transparent backgrounds**;
* **Max ray distance support for improved baking control**;
* **Runs on Blender 4.2 LTS through 5.2 from one build** (version differences handled in `bakelab_compat.py` by capability detection);
* **Blender Extensions manifest for official extension support**;

![Screen](bakelab_screen.png)

## Installation

1. Download or build the extension zip (see below).
2. In Blender, go to *Edit > Preferences > Get Extensions*, open the drop-down at the top right and choose *Install from Disk...*.
3. Find the **BakeLab** tab in the 3D View sidebar (*N*).

### Building the zip

From the repository folder (or a checkout of the release tag `v3`), run:

```
blender --command extension build
```

This writes `blender_bakelab-<version>.zip`, containing only the files the add-on needs.

## Changes in 3.0.0

* **UDIM baking**: a per-map *UDIM* toggle bakes one tile per UV tile (1001+).
  Needed tiles are auto-detected from the bake UVs, initialized, baked in one
  pass, and saved as `name_1001.png`, `name_1002.png`, ... (or packed). Tiles
  bake at final size — anti-aliasing is unavailable for UDIM maps, and
  *Apply Displacement* from a UDIM image uses only the first tile (warned).
* **Batch baking**: a new *Batch* source picks what forms the bake queue —
  Selection (default, unchanged behavior), By Material (one job per material,
  with each job baking only its own material's faces), Collection, or Scene.
  A failing job is reported and skipped without killing the rest; Esc still
  cancels everything.
* **Headless baking**: with no window (`blender -b`), Bake runs synchronously
  to completion, so batches can be scripted:
  `bpy.ops.bakelab.bake()` after enabling the extension.
* Progress display shows the running job (index, count, name) during batches.
* **Blender 4.2 LTS - 5.2 from a single build** (2.1.0 required 5.0+): a new
  `bakelab_compat.py` holds every version difference, chosen by capability
  detection rather than version-number checks —
  * the 5.0+ `media_type`/`file_format` coupling when choosing save formats,
    with the scene's original media type restored afterwards;
  * "no look" and image color spaces resolved against the active OCIO config
    (named differently across builds), warning with the attempted names when
    nothing matches;
  * Cycles enabled automatically when its add-on is off, with a clean error
    instead of a crash when that is not possible;
  * node sockets looked up by name and identifier with position as
    tie-breaker, so renamed or ambiguous sockets (e.g. Mix Shader's two
    "Shader" inputs) bind to the intended socket on every version;
  * saved images keep their exact colors on all supported versions.
* UDIM/tile behavior verified on 5.2 with API-identical 4.2 docs — see the
  TESTING.md version matrix, whose gate runs on each supported version.

## Changes in 2.1.0

* Fixed Blender freezing on materials with node groups that have no Group Input
* Fixed crashes: Transmission maps, Adaptive image size, editing Min/Max Size, Selected to Active without an active object
* Original materials are no longer deleted when baking linked duplicates
* Saved images keep their exact colors (the scene's AgX view transform is no longer applied) and still show after reopening the .blend
* Transparent backgrounds (*Clear image*) are kept when saving, packing and exporting
* Pre-Join Meshes works again, and cancelling with *Esc* restores materials
* Subsurface maps now bake the material's Subsurface Weight
* All To One no longer wipes earlier objects, and Max Ray Distance is its own setting
* Adaptive size applies each map's Image Scale; reused images are resized to the map size

See [TESTING.md](TESTING.md) for the release test checklist.

### Correctness fixes

* Transparent backgrounds follow UV coverage, preserving black surfaces and zero-valued maps.
* Baking uses the selected editing UV map and records it for post-bake actions, including merged atlases with different UV map names.
* Bake errors clean up temporary materials, objects, handlers and timers and restore scene settings.
* Shader group inputs, direct connections and output defaults are preserved when extracting passes.
* Apply AO supports mixed and grouped shaders; custom-pass presets use current Principled socket names.
* Automated Blender regression checks are available in `tests/blender_regressions.py`.
