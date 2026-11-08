# Send Frame

`haybale-stream:node:SendFrameNode` · kind: node

Publishes an image to other applications over NDI, OMT, Syphon or Spout

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Sends the image |
| `image` | inlet | `haybale-image:type:IMAGE` | Image to publish |
| `next` | outlet | `haywire-core:type:EXEC` | Runs after sending |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `backend` | stream | `'ndi'` | Transport to publish on: NDI, OMT, Syphon, Spout |
| `name` | stream | `'haywire'` | Name other applications see for this sender |
| `frame_rate` | stream | `30.0` | Frame rate announced to receivers (NDI and OMT pace sending to it) |
| `steady_stream` | stream | `True` | Keep resending the last frame while no new one arrives (NDI, OMT) |

## Notes

Publishes `Image` under `Name` on the chosen `Backend` each time it runs.

- `Backend`: NDI and OMT run on every platform; Syphon only on macOS, Spout only
  on Windows. A backend that cannot run here makes the node report an error.
- `Steady stream`: keeps resending the last frame so receivers do not show
  "no signal" while the graph is idle (NDI, OMT).

The sender opens with the first frame and reopens if `Backend` or `Name` change.
Gray and RGB images are sent with an opaque alpha channel.

```text
Load Image → Send Frame
```
