# Changelog

All notable changes to BakeLab are documented here, starting with v3.
Entries before 3.0.0 are omitted.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses [Semantic Versioning](https://semver.org/): PATCH for
fixes, MINOR for backwards-compatible features, MAJOR for breaking changes
or raising `blender_version_min`.

## [Unreleased]

## [3.9.1] - 2026-09-28

### Fixed

- **UDIM tile detection** follows triangle coverage on the evaluated
  mesh. A standard 0-1 unwrap no longer creates blank tiles 1002, 1011
  and 1012 (and writes their files); UV offsets from modifiers such as
  Mirror or Array now get their tiles; a NaN UV is skipped and reported
  instead of failing the job.
- **Adaptive image size** with UDIM splits the surface area across the
  tiles, so each tile gets the requested texel density rather than
  sqrt(tile count) times it.
- **AORM** occlusion (red channel) traces as far as the AO map does
  (the world's AO distance) instead of stopping at 1 m, so both maps
  agree.
- Rebaking into a kept image (Clear image off) after changing the save
  folder no longer fails with "does not have any image data", for flat
  and UDIM images; a kept image whose files were deleted is recreated
  with a warning.
- The texture importer darkens Base Color by an AORM map's red channel
  only (the full color tinted it by roughness and metallic), no longer
  stacks another AO multiply when a file is imported again, and loads a
  UDIM tile set (`name_1001.png`, `name_1002.png`...) as one image.
- Object, material, collection and texture-set names with characters a
  file name cannot hold (`:` `/` `\` `*`...) no longer fail the save;
  they are replaced by `_` in the file and folder names.

## [3.9.0] - 2026-09-28

### Added

- **Map defaults in the addon preferences**: every bake-map type gets an
  editable row — name pattern (`*`), sample count and color space —
  applied by Add Map, the auto-added default map and the auto-detected
  Alpha map. Rows seed from the shipped defaults on first view and a
  **Reset** button restores them; a map type introduced by a later
  version slots into an existing table without touching user edits.
- **Texture-import aliases** in the preferences: extra
  filename-suffix → channel rules (e.g. `msk` → alpha) that are checked
  before the builtin table, so project naming conventions work without
  renaming files.

### Changed

- Per-type bake-map defaults now live in a shared `MAP_TYPE_DEFAULTS`
  table (`properties/maps.py`), and the importer's channel table moved
  to `utils/tools.py` so both the importer and preferences share it.

## [3.8.0] - 2026-09-28

### Added

- **Texture Sets** batch source: named groups of objects edited inline
  in the Batch section (add/remove sets, assign/unassign the selected
  meshes, select a set's members). Each enabled set bakes All To One
  into maps named after the set (`Vehicle_albedo.png`,
  `Env_normal.png`), Substance-Painter style. An object can only live
  in one set — assigning moves it — and a stray duplicate membership
  bakes under the first set with a report. Sets are scene data and
  persist in the .blend file.
- The preflight checklist previews set/member counts, missing UVs,
  duplicate set names (which overwrite each other's images) and
  cross-set memberships, and greys out Bake when no set is usable.

### Changed

- The Selected-to-Active conflict message now names both valid batch
  sources (Selection or High-Low Pairs) instead of only Selection.

## [3.7.0] - 2026-09-28

### Added

- **UV Grid** and **Color Grid** bake maps: bake Blender's generated
  test grids (`generated_type` UV_GRID / COLOR_GRID) through the
  object's UVs via an emission conversion, so stretching in the unwrap
  shows as distorted squares or broken numbering in the output image.
  Generate Materials wires the baked grid into Base Color so it can be
  inspected on the model. The generated source image is shared per
  bake and dropped afterwards; Clean Leftovers also removes stray
  `BAKELAB_TMP_*` images (previously only objects, meshes and
  materials).

## [3.6.0] - 2026-09-28

### Added

- **Addon preferences** (Edit → Preferences → Add-ons → BakeLab): a
  **GPU Backend** option lists the Cycles compute backends the machine
  supports (OptiX, CUDA, HIP, oneAPI, Metal…) and writes the choice
  through to Cycles — both when changed and again at bake start, so a
  manually changed Cycles setting can't silently override it. `Auto`
  leaves Blender's own backend selection alone, and a stored backend
  that the current machine lacks is ignored rather than erroring.
- The preflight checklist shows the effective GPU backend whenever
  Device is GPU Compute.

## [3.5.0] - 2026-09-28

### Added

- **Import Textures** (image icon beside the UV tools): opens a file
  picker and wires textures into materials by filename convention —
  `<object-or-material>_<channel>[_<tile>]` (`sword_albedo.png`,
  `sword_low_normal.png`, `prop_roughness_1001.png`). Covers albedo,
  normal (via Normal Map), roughness, metallic, specular, emission,
  alpha (with transparency enabled), AO (multiplied into Base Color),
  packed AORM (channel-split), and height/displacement (via Bump).
  Data maps get Non-Color, `_####` files load as UDIM tiles, bare
  channel names (`albedo.png`) target the active object, and
  unrecognized or unmatched files are reported instead of dropped.

## [3.4.0] - 2026-09-28

### Added

- **High–Low pair batching**: a new *High-Low Pairs* batch source scans
  the scene for `*_low` meshes and bakes each one Selected-to-Active from
  its matching `*_high*` sources. A bare `foo_low` collects every
  `foo_high*` variant; a `foo_low_1` is scoped to `foo_high_1` plus a
  shared variant-free `foo_high`. Orphan lows are reported, never
  blockers, and the preflight checklist previews the pairs.
- **Clean Leftovers** operator (bin icon beside the UV tools): recovers a
  scene after a crashed or interrupted bake — re-points stranded material
  copies to their surviving originals, strips `BAKELAB_TMP_*` nodes when
  no original can be identified, removes temp objects/meshes/materials,
  and resets a bake state stuck in a file saved mid-bake.

## [3.3.1] - 2026-09-28

### Fixed

- Unregister no longer throws a `missing bl_rna` RuntimeError when Blender
  calls it during shutdown — scene properties are detached before their
  classes, and teardown errors are tolerated.

### Changed

- README reworked into a feature overview — per-version change sections
  removed; release notes now live only in this changelog.

## [3.3.0] - 2026-09-28

### Added

- **AORM packed map type**: one EMIT pass packs occlusion into red,
  roughness into green and metallic into blue (ambient occlusion is
  computed in-shader, roughness/metallic come from the leaf shader's
  sockets, linked or static). Generate Materials splits the channels
  back into Principled Roughness/Metallic and darkens via the AO mix.
- **Preflight checklist**: the panel now shows what a bake will do
  before you click — selected mesh count, missing UVs (named),
  configured/enabled map count, batch/mode conflicts, and when an
  Alpha map or a default Albedo map will be auto-added. A blocking
  item greys out the Bake button.

## [3.2.0] - 2026-09-28

### Added

- **Metallic map type**: EMIT pass from the material's `Metallic`/
  `Metalness`/`Metal` socket (previously only reachable as a CustomPass
  preset), wired into the Principled `Metallic` input by Generate
  Materials.
- **Material ID map type**: bakes a flat, stable color per material via
  EMIT — hues are hashed from the material's original name so copies and
  rebakes keep identical IDs.
- **Position map type**: native `POSITION` bake of world-space surface
  coordinates; defaults to Non-Color OpenEXR for the full value range.

## [3.1.1] - 2026-09-28

### Added

- **Alpha bake map type**: bakes the material's opacity (wired Alpha
  inputs, `Opacity`/`Transparency`/`Transparent` aliases, or a static
  value) into a grayscale mask via an EMIT pass. Materials without an
  alpha socket bake opaque; a Transparent BSDF leaf bakes clear.
- **Wired-alpha detection**: when a bake runs and any source material has
  an Alpha input fed by nodes — or a Transparent BSDF in the chain — the
  baker adds an enabled Alpha map itself and reports it, unless one is
  already in the map list.
- *Generate Materials* wires a baked Alpha map (or a CustomPass baked
  into `Alpha`) into the Principled BSDF's Alpha input and enables the
  transparency render method (`surface_render_method` on 4.2+, legacy
  `blend_method` before that) so the material is actually transparent in
  Eevee too.

## [3.1.0] - 2026-09-28

### Changed

- Pressing Bake with an empty map list on a ready object no longer errors
  with "Add bake maps" — the baker adds the Add Map operator's default
  (Albedo) and reports exactly what was created (type, image name, size,
  samples), so a valid scene bakes on the first click.
- Validation messages name the offending object ("Object \"X\" has no UV
  map" instead of "Not all objects have UV maps") and the Selected to
  Active errors were clarified. A bake with all maps disabled now reports
  that instead of silently baking nothing.
- Reorganized the package into role-based sub-packages: `utils/` (compat
  shims, tools), `properties/` (scene settings, bake maps, baked data),
  `operators/` (all operators) and `ui/` (panel, map list). `__init__.py`
  now holds only `bl_info` and registration. No behavior change.
- The extension zip now contains only the add-on code, the manifest and
  the license — README, CHANGELOG, images, tests and lint config stay in
  the repository but are excluded from installs.

## [3.0.0] - 2026-09-26

### Added

- UDIM baking: a per-map *UDIM* toggle bakes one image per UV tile (1001+),
  auto-detected from the bake UVs, saved as `name_1001.png`, `name_1002.png`,
  ... or packed. Tiles bake at final size; anti-aliasing is unavailable for
  UDIM maps.
- Batch baking: the *Batch* source picks the bake queue — Selection (one
  job, unchanged behavior), By Material (one job per material, each baking
  only its own faces), Collection, or Scene. A failing job is reported and
  skipped without killing the rest; Esc still cancels everything.
- Headless baking: with no window (`blender -b`), Bake runs synchronously to
  completion, so batches can be scripted via `bpy.ops.bakelab.bake()`.
- Progress display shows the running job (index, count, name) during
  batches.

### Changed

- One build now runs on Blender 4.2 LTS through 5.2 (2.1.0 required 5.0+):
  all version differences live in `utils/compat.py`, chosen by capability
  detection rather than version-number checks —
  - the 5.0+ `media_type`/`file_format` coupling when choosing save
    formats, with the scene's original media type restored afterwards;
  - "no look" and image color spaces resolved against the active OCIO
    config, warning with the attempted names when nothing matches;
  - Cycles enabled automatically when its add-on is off, with a clean error
    instead of a crash when that is not possible;
  - node sockets looked up by name and identifier with position as
    tie-breaker, so renamed or ambiguous sockets (e.g. Mix Shader's two
    "Shader" inputs) bind to the intended socket on every version;
  - saved images keep their exact colors on all supported versions.

[Unreleased]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.9...HEAD
[3.9.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.8...v3.9
[3.8.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.7...v3.8
[3.7.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.6...v3.7
[3.6.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.5...v3.6
[3.5.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.4...v3.5
[3.4.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.3.1...v3.4
[3.3.1]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.3...v3.3.1
[3.3.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.2...v3.3
[3.2.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.1.1...v3.2
[3.1.1]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.1...v3.1.1
[3.1.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3...v3.1
[3.0.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/releases/tag/v3
