# Receive Frame Emit

`haybale-stream:node:ReceiveFrameEmitNode` · kind: node

Receives frames from NDI, OMT, Syphon or Spout on its own thread and emits a callback per frame

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to Image Event nodes |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `backend` | stream | `'ndi'` | Transport to receive from |
| `source` | stream | `''` | Name of the sender to receive from; pick a discovered one or type it |

## Notes

Receives frames in the background and hands each new one to the connected Image Event nodes.

Unlike Receive Frame, nothing has to poll it: send `Start` once and every frame that
arrives triggers the Image Event nodes wired to `Subscribers`. A source that is not
there yet is retried every two seconds while the node runs.

```text
Begin Play → Receive Frame Emit ⇢ Image Event → View Image
```

Inputs:
    start: Begin receiving
    stop: Stop receiving
    callbacks: Pooled subscriptions from Image Event nodes

Outputs:
    started / stopped: Control flow after the receiver starts or stops
