# Haybale Stream

A haywire library that sends and receives video frames between applications over
[Syphon](https://syphon.github.io/) (macOS), [Spout](https://spout.zeal.co/) (Windows),
[NDI](https://ndi.video) and [OMT](https://www.openmediatransport.org) (Open Media Transport,
cross-platform).

Ideas and backend code come from [TextureSharing](https://github.com/maybites/TextureSharing)
(Spout for Blender).

| Backend | Linux | macOS | Windows |
|---------|:-----:|:-----:|:-------:|
| NDI     | yes   | yes   | yes     |
| OMT     | yes   | yes   | yes     |
| Syphon  |       | yes   |         |
| Spout   |       |       | yes     |

Frames travel as `IMAGE` values from `haybale-image`. See [docs/design.md](docs/design.md).

## Nodes

| Node | What it does |
|------|--------------|
| Send Frame | Publishes an `IMAGE` under a name on NDI, OMT, Syphon or Spout. |
| Receive Frame | Fetches the newest frame from a named source as `IMAGE_RGBA`; exits through `Frame` or `No frame`. |
| Receive Frame Emit | Receives on its own thread and emits a callback per frame to connected Frame Event nodes (like the visiongraph camera nodes). |
| Frame Event | Event node: runs its flow per frame from a Receive Frame Emit; outputs `Image`, `Frame Number`, `Timestamp`. |

Status: NDI and OMT are tested on Linux. Syphon and Spout are implemented but not yet run
on macOS / Windows.

## Subscribe

<!-- marketstall:share-url:start -->
<!-- marketstall:share-url:end -->

## Getting started

```sh
uv sync
uv run haywire
uv run pytest
```

Develop from `../haywire-repo` (this package is symlinked into its `barn/`); see [CLAUDE.md](CLAUDE.md).

## Share the library

```shell
uv run haywire share --bump patch|minor|major --save
```

## Credits

Syphon: Tom Butterworth and Anton Marini. Spout: Lynn Jarvis. SpoutGL: Jason Lai.
syphon-python: Florian Bruggisser. cyndilib: Matthew Reid. OMT: the Open Media Transport project
(cyomtlib wrapper). NDI® is a registered trademark of Vizrt NDI AB; NDI runtime © Vizrt NDI AB, bundled in the cyndilib wheel under the NDI SDK license (http://ndi.link/ndisdk_license).

Martin Froehlich. Implementation for [haywire](https://github.com/going-haywire/haywire)
