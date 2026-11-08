# haybale-stream — design

Status: milestone 1 (Linux). NDI and OMT are implemented and loopback-tested here;
Syphon (macOS) and Spout (Windows) are implemented, import-guarded and **untested**.

## Goal

Send and receive video frames between a haywire graph and other applications, behind
one abstraction, as haywire nodes that speak the shared `IMAGE` type from
`haybale-image`.

## Layers

```
nodes/           Send Frame, Receive Frame          (haywire; the only layer that knows haywire)
backends/convert ImageValue <-> packed H×W×4 uint8  (the only layer that knows ImageValue)
backends/        Backend, Sender, Receiver          (numpy in, numpy out; no haywire imports)
  ndi.py omt.py syphon.py spout.py                  (each imports its native dep lazily)
```

A backend moves packed 8-bit 4-channel frames. Its channel order (`rgba` / `bgra`) is a
class attribute; `convert` converts exactly once at the boundary, via
`ImageValue.array(np.uint8, order)`, so no backend ever swaps channels.

### Contract (`backends/base.py`)

| Type | Role |
|------|------|
| `Backend` | Class-level facade: `is_available()` / `unavailable_reason()`, `discover(wait)`, `create_sender(name)`, `create_receiver(source)`. |
| `Sender` | `open()`, `send(pixels, frame_rate)`, `close()`. |
| `ClockedSender` | NDI/OMT: their send call blocks one frame period, so `send` stores the newest frame and a worker thread writes it (latest wins; optional `steady_stream` resend). Ported from the TextureSharing servers. |
| `Receiver` | `open()`, `poll(timeout) -> Frame | None` (newest unseen frame, non-blocking by default), `close()`. |
| `BACKENDS`, `get_backend`, `available_backends` | Registry. Importing it is safe on every platform. |

Gating: `Backend.platforms` (`sys.platform` prefixes) plus a lazy dependency import.
On the wrong platform `unavailable_reason()` explains why and every factory raises
`BackendUnavailable`; nothing native is imported at module load.

### Why polling, not callbacks

A haywire worker runs once per frame and wants the latest image. `poll()` fits that
directly and keeps threads inside the backend. NDI's frame-sync API repeats the last
frame, so the NDI receiver tells a new frame from a repeat by timestamp.

## Image types

Nodes use `IMAGE` from `haybale-image` (any layout). Send accepts any layout (gray/RGB get
opaque alpha). Receive emits `IMAGE_RGBA`, which `haybale-image`'s adapters turn into
gray/RGB on demand. `haybale-visiongraph` has its own `RGB_FRAME`/`GRAY_FRAME` and no
`IMAGE` bridge yet — see "Proposed changes to other repos" in the report; nothing here
depends on it.

Frames cross system memory. A GPU-resident path (Syphon/Spout zero-copy) would need a GPU
image type that does not exist in `haybale-image`; out of scope.

## Backends

| | Linux | macOS | Windows | Dependency | Transport |
|-|:-:|:-:|:-:|-|-|
| NDI | tested | wheel exists | wheel exists | `cyndilib` (MIT; bundles libndi 6.3) | network, mDNS |
| OMT | tested | wheel exists | wheel exists | `cyomtlib` (MIT; bundles libomt) | network, DNS-SD |
| Syphon | – | untested | – | `syphon-python` (`sys_platform=='darwin'`) | local GPU sharing |
| Spout | – | – | untested | `SpoutGL` (`sys_platform=='win32'`, BSD-3) | local GPU sharing |

Platform markers in `pyproject.toml` mean `pip install haybale-stream` pulls only what the
OS can use. NDI and OMT are hard dependencies because their wheels are self-contained.

### Syphon notes (unverified)

Metal via `syphon.SyphonMetalServer`/`SyphonMetalClient`, CPU round-trip through
`syphon.utils.numpy`. Server names are displayed `"<app> | <name>"`. Open points that need
a Mac: vertical orientation of received textures (`is_flipped`), and whether a headless
process needs `SyphonServerDirectory.update_run_loop()` pumped (we do pump it).

### Spout notes (unverified)

`SpoutGL.SpoutSender.sendImage` / `SpoutReceiver.receiveImage`, GL_RGBA, no invert. Receiver
follows SpoutGL's documented loop (`isUpdated()` → reallocate; skip the empty first frame).

## Licensing and NDI SDK distribution

- haybale-stream: MIT (like the other haybales).
- `cyndilib` is MIT. Its wheels **bundle the NDI runtime** (`libndi`, © Vizrt NDI AB) under
  the NDI SDK license (<http://ndi.link/ndisdk_license>), which permits redistribution of the
  runtime with attribution. cyndilib ships `libndi_licenses.txt` inside the wheel; we depend
  on the wheel, we do not repackage or vendor libndi ourselves, so that notice travels with
  it. We must (a) keep the trademark line in README ("NDI® is a registered trademark of
  Vizrt NDI AB") and (b) not claim endorsement. **Open:** confirm the exact attribution
  wording NDI requires for software that merely depends on a wheel containing it.
- `cyomtlib` is MIT and bundles `libomt` (OMT is MIT-licensed, Open Media Transport project).
- `SpoutGL` BSD-3, Spout itself BSD-2; `syphon-python`/Syphon framework are BSD-style.
  Neither is bundled by us.

## Native packaging

No native code is built or vendored here. All native code arrives through manylinux/macOS/
Windows wheels of the dependencies. Consequences:

- `haybale-stream` itself is a pure-Python `py3-none-any` wheel, published to PyPI by the
  tag-triggered workflow in `.github/workflows/publish.yml` (same as the other haybales).
- The smoke-test job dry-resolves dependencies on Linux/3.12, so a wheel gap (e.g. new
  Python without `cyndilib`) fails before upload.
- `cyndilib` wheels exist for cp310–cp315 on Linux x86_64/aarch64, macOS arm64/x86_64 and
  Windows x64; `cyomtlib` is `py3-none` (any Python) for the same set plus win-arm64.
  `requires-python` stays `>=3.12`.
- Runtime needs on Linux: nothing system-wide. Discovery relies on mDNS (NDI) / DNS-SD
  (OMT), so network loopback and multicast must be allowed; tests are marked `network`.

## Nodes

- **Send Frame** (CONTROL): inlets `image`, settings `backend`, `name`, `steady stream`, `frame rate`.
  Opens the sender on first frame, reopens if backend/name change, closes on shutdown.
- **Receive Frame** (CONTROL): settings `backend`, `source` (dropdown of discovered sources,
  refreshed on open), outlets `image` (IMAGE_RGBA), `received` exec / `none` exec paths.
  Keeps the last image when no new frame arrived.

Both report a clear error on an unavailable backend instead of failing at import.
