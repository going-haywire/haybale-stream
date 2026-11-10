# haybale-stream — orientation for Claude

This repo is a **haybale library** (a plugin) for the **haywire** visual-programming
framework. It wraps NDI, OMT, Syphon and Spout as haywire
types, nodes, widgets, and renderers. It is *not* the framework itself — the framework
lives in a separate monorepo.

## Develop from the monorepo, not from here

The framework monorepo sits next to this repo and **symlinks this repo's package into
its `barn/`**, so the same source files are editable from both sides:

```
haywire/
├── haywire-repo/                       ← framework monorepo (docs, .codemap, .insights, skills)
│   └── barn/haybale-stream  →  symlink to ↓
└── haybale-stream/                ← THIS repo (own git, .venv, releases)
    └── barn/haybale-stream/haybale_stream/   ← the actual source
```

**Prefer opening Claude sessions in `../haywire-repo`** and editing this library through
`barn/haybale-stream/...`. There you get the framework docs, the `.codemap/` index,
the `.insights/` traps, the `haywire-*` skills, the live framework to import against, and
`uv run haywire` / `uv run pytest` running against the real framework. Edits there land in
*this* repo's files via the symlink; do git operations (commit, tag, release) from here.

If you are working in this repo directly (offline, packaging, or a fresh clone), the
authoritative framework knowledge is at:

- `../haywire-repo/docs/` — component authoring guides + architecture (start here for "how do I build a node/type/widget/renderer")
- `../haywire-repo/.codemap/INDEX.md` — repo layout map
- `../haywire-repo/.insights/` — non-obvious bugs and framework gotchas
- `../haywire-repo/CLAUDE.md` — framework conventions (reactive props, DI, testing rules)

## This repo

- Package: `haybale_stream` under `barn/haybale-stream/` (name `haybale-stream-dev` in dev).
- `marketstall.toml` — the published library feed manifest; rewritten by `haywire share`; never hand-edited.
- Setup, running, and sharing commands are in [README.md](README.md) — don't duplicate them here.

## Rules that carry over from the framework

These apply when editing this library; the long-form versions live in the monorepo:

- Read a file before editing it; grep for callers before changing a function signature.
- Follow the existing reactive-props / DI patterns — don't introduce singletons or
  alternate registration paths. Confirm before any change to class hierarchies or DI wiring.
- After multi-file changes, run `uv run pytest` (from the monorepo, against the live
  framework) and confirm it passes before calling work done.

## Releases

- Never edit version numbers, `install_spec` or `marketstall.toml` by hand, and never
  tag or push a release manually.
- Release only with `uv run --frozen haywire share --bump patch|minor|major` (or an explicit `X.Y.Z`),
  run **from this repo's root**, not from `../haywire-repo`: the CLI publishes the project in
  the current directory. It bumps every `barn/*` library in lockstep, regenerates docs,
  rebuilds `marketstall.toml`, then commits, tags `v<version>` and pushes to `origin` itself.
  `--dry-run` reports what it would do and writes nothing; run it first.
- `--frozen` matters: plain `uv run` re-locks and dirties `uv.lock`, which fails the clean-tree
  check. If `uv.lock` is already dirty, `git checkout uv.lock` before releasing.
- It needs a clean working tree, an `origin` remote, push credentials, and the default
  branch checked out. `distribute = "pypi"` is set here, so the marketstall rows pin
  `haybale-stream==<version>`.
- You do not upload to PyPI yourself: `share` pushes the `v<version>` tag and the `publish.yml`
  GitHub Actions workflow builds the wheel, checks that its dependencies resolve on PyPI, and uploads it. Watch it with `gh run watch`, then
  confirm `https://pypi.org/project/haybale-stream/<version>/` returns 200. If the publish job
  fails, fix the cause and re-run it on the same tag with `gh workflow run publish.yml --ref v<version>`;
  do not delete or move tags yourself, ask the user. `--first-release` is only for a new package name
  (see `publish-to-pypi.md`).
- Before releasing, read `../haywire-repo/docs/guides/sharing-libraries.md` (and
  `docs/architecture/sharing/share-pipeline-arch.md` if needed).
- If a dependency pin needs a version that is not released yet, stop and ask.
