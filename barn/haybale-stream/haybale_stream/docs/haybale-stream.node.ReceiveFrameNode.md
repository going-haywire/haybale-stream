# Receive Frame

`haybale-stream:node:ReceiveFrameNode` · kind: node

Receives the newest image from another application over NDI, OMT, Syphon or Spout

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Fetches the newest frame |
| `frame` | outlet | `haywire-core:type:EXEC` | A new frame arrived |
| `none` | outlet | `haywire-core:type:EXEC` | No new frame |
| `image` | outlet | `haybale-image:type:IMAGE_RGBA` | The newest frame received |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `backend` | stream | `'ndi'` | Transport to receive from |
| `source` | stream | `''` | Name of the sender to receive from; pick a discovered one or type it |

## Notes

Fetches the newest frame from `Source` each time it runs and passes it on as `Image`.

Control continues through `Frame` when a frame newer than the last one arrived, and
through `No frame` otherwise (no sender, or nothing new yet). `Image` then keeps the
last frame received, so a downstream node never sees an empty image after the first.

- `Backend`: NDI and OMT run on every platform; Syphon only on macOS, Spout only
  on Windows.
- `Source`: pick a discovered sender or type its name. A source that is not there
  yet is retried every two seconds while the node runs.

```text
Receive Frame → View Image
```
