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

## Release reminders

([sharing-libraries §7.1](https://github.com/going-haywire/haywire/blob/master/docs/guides/sharing-libraries.md#71-release-reminders))

A release reminder is an issue that records a decision affecting the next release, so it is not forgotten. It is a help, not a rule: open one only when the owner agrees. When a change you make needs something done at release time (most often a dependency floor to raise once a release contains a change), propose the issue to the owner: its title, the label, the steps, and for `after-core-release` a first line `Waits for: going-haywire/haywire@<sha> (#<pr>)`. Link a prepared branch's draft PR to it.

| Label | Meaning | Read |
|---|---|---|
| `todo-pre-release` | Something the owner decided to do before the next release of this project. | Before `haywire share`, `--dry-run` included: `gh issue list --label todo-pre-release --state open`. If any are open, list them and ask the owner whether to release anyway. |
| `after-core-release` | A dependency to raise (usually the `haywire-core` floor) once a released haywire-core contains the change on the issue's `Waits for:` line. | At the start of a session: `gh issue list --label after-core-release --state open`; check each one as below and tell the owner which can now be done. |

The change on a `Waits for:` line is released when the latest haywire-core on PyPI contains the commit:

```sh
v=$(curl -s https://pypi.org/pypi/haywire-core/json | jq -r .info.version)
gh api "repos/going-haywire/haywire/compare/v$v...<sha>" --jq .status  # behind or identical: released
```

Create the labels when the owner agrees to the first reminder (safe to repeat):

```sh
gh label create todo-pre-release --color D93F0B --description "Reminder: to do before the next release" --force
gh label create after-core-release --color FBCA04 --description "Reminder: to do once a haywire-core release contains the needed change" --force
```

If `gh` is missing or not logged in, or the repository is not on GitHub, tell the owner the reminders could not be read; never report that none are open.
