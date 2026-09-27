# AGENTS.md — BakeLab

Guidance for agents working in this repository.

## Objective

BakeLab is a Blender extension for baking textures with automatic image and
material setup: one-click image creation and material generation,
anti-aliased baking, UDIM tile baking, batch/queue baking (selection,
material, collection, scene), and headless runs via `blender -b`.

One build supports **Blender 4.2 LTS through 5.2**; all version differences
are handled by capability detection in `bakelab_compat.py`.

## Workspace layout

This repository **is** the add-on package — every file here ships in the
extension (minus the patterns in `paths_exclude_pattern` in
`blender_manifest.toml`).

In the full development workspace this repo lives nested at
`blender_bakelab/`; the parent is a local-only workspace that is **not**
hosted on GitHub:

```
<workspace>/                    (local workspace repo, no remotes)
├── blender_bakelab/            <- THIS repository (nested git, pushed to GitHub)
├── docs/TESTING.md             <- release test checklist + manual test steps
├── dist/                       <- built extension zips
└── *.zip                       <- older packaged releases
```

Repository contents:

```
blender_bakelab/
├── __init__.py                 bl_info, Scene properties (BakeLabProps), register()
├── blender_manifest.toml       extension manifest: id, version, build excludes
├── bakelab_bake.py             core bake operator and batch job queue (largest file)
├── bakelab_map.py              bake-map PropertyGroup, map list UI, presets
├── bakelab_uv.py               unwrap operators and UV helpers
├── bakelab_post.py             post-bake ops: generate materials, Apply AO/Displace, Finish
├── bakelab_baked_data.py       baked-data bookkeeping PropertyGroups
├── bakelab_compat.py           ALL Blender-version differences, as capability shims
├── bakelab_tools.py            small shared helpers
├── bakelab_ui.py               3D View sidebar panel (BakeLab tab)
└── tests/
    └── blender_regressions.py  headless Blender regression suite
```

The installed copy lives at
`%APPDATA%\Blender Foundation\Blender\<ver>\extensions\user_default\blender_bakelab`.

## Rules

### Versioning — SemVer

Bump the version for every release-bound change:

- **PATCH** — bug fixes and internal cleanups with no behavior change
- **MINOR** — new features, bake maps, or options (backwards compatible)
- **MAJOR** — breaking behavior changes or raising `blender_version_min`

Update all of these together — they must never disagree:

1. `blender_manifest.toml` → `version`
2. `__init__.py` → `bl_info["version"]`
3. `README.md` → "Current release" line plus a "Changes in X.Y.Z" section

### Commits

- Commit every completed implementation or fix; never leave finished work
  uncommitted.
- One feature or fix per commit; keep commits scoped.
- Commit messages describe the *why*, not just the what.
- Push to `origin` (GitHub) only when the user asks.

### Compatibility

- A version difference goes in `bakelab_compat.py` and is chosen by
  capability detection (RNA lookups, `hasattr`, try/except) — never by
  comparing `bpy.app.version`.
- Keep `blender_version_min` / `blender_version_max` in the manifest honest.
- New sockets/passes must bind through `input_socket`/`output_socket`/
  `find_socket_by_alias`, not raw indices or names alone.

### Code style

- Match the existing module layout and naming; keep code compact.
- Only write comments where the surrounding code already has them.
- New files belong in this package only if the extension needs them at
  runtime; dev/test/docs files that shouldn't ship go in
  `paths_exclude_pattern` or the outer workspace.

## Verification

```bash
# Lint
ruff check .            # or: python -m ruff check .

# Headless regression suite — run with EVERY supported Blender version
blender --background --factory-startup --python-exit-code 1 \
    --python tests/blender_regressions.py
# must print "OK" and exit 0

# Build the extension zip (run from this folder)
blender --command extension build --output-dir ../dist
```

The release checklist and manual test steps live in `docs/TESTING.md` in the
outer workspace. Blender-side manual checks (Esc cancellation, UI state)
can't be covered headless.
