# Receive Audio Emit

`haybale-stream:node:ReceiveAudioEmitNode` · kind: node

Receives audio from an OMT source on its own thread and emits a callback per block

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to Audio Event nodes |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `backend` | stream | `'omt'` | Transport to receive from |
| `source` | stream | `''` | Name of the sender to receive from; pick a discovered one or type it |

## Notes

Receives audio in the background and hands each block to the connected Audio Event nodes.

Send `Start` once and every block that arrives triggers the Audio Event nodes wired to
`Subscribers`. The remote sender owns the clock: each OMT frame becomes one block at the
frame's own sample rate and channel count, so a node that needs another format converts it
(Reblock/Resample). A source that is not there yet is retried every two seconds.

```text
Begin Play → Receive Audio Emit ⇢ Audio Event → Device Out
```

Inputs:
    start: Begin receiving
    stop: Stop receiving
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    started / stopped: Control flow after the receiver starts or stops
