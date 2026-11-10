# Send Audio

`haybale-stream:node:SendAudioNode` · kind: node

Publishes the audio blocks of a flow to other applications over OMT

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to publish |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:EXEC_AUDIO` | Runs after the block is queued |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `backend` | stream | `'omt'` | Transport to publish audio on |
| `name` | stream | `'haywire-audio'` | Name other applications see for this sender |
| `fifo_blocks` | stream | `64` | Blocks queued between the flow and the network; a full FIFO drops new blocks |

## Notes

Queues each block in a FIFO; a sender thread stamps it from the frames sent so far and publishes it.

The stamps follow the sample count, never the arrival time, so the receiver sees a steady clock.
The flow in front paces the blocks (File Player, Mixer, Device In). Use blocks of 256 frames or
more: smaller ones make the receiver drop some. The status shows the FIFO depth and the blocks
dropped when it was full.

The sender opens with the first block and reopens if `Backend` or `Name` change.

```text
Audio Event → Send Audio
```

Inputs:
    write: Queue the block on `audio` (wire it to an Audio Event's Block Ready)
    stop: Close the sender; the next `write` opens it again
    audio: The block to publish

Outputs:
    next: Control flow after a block is queued
