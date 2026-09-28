# Changelog

All notable changes to BakeLab are documented here, starting with v3.
Entries before 3.0.0 are omitted.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses [Semantic Versioning](https://semver.org/): PATCH for
fixes, MINOR for backwards-compatible features, MAJOR for breaking changes
or raising `blender_version_min`.

## [Unreleased]

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

[Unreleased]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.3...HEAD
[3.3.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.2...v3.3
[3.2.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.1.1...v3.2
[3.1.1]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3.1...v3.1.1
[3.1.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/compare/v3...v3.1
[3.0.0]: https://github.com/CloudyTabzy/Blender-BakeLab2/releases/tag/v3
