# Stream

<!-- marketstall:share-url:start -->
<!-- marketstall:share-url:end -->

Share video frames between applications over Syphon, Spout, NDI and OMT

## Nodes
### Stream
- **Receive Audio Emit** — Receives audio from an OMT source on its own thread and emits a callback per block
- **Receive Frame** — Receives the newest image from another application over NDI, OMT, Syphon or Spout
- **Receive Frame Emit** — Receives frames from NDI, OMT, Syphon or Spout on its own thread and emits a callback per frame
- **Send Audio** — Publishes the audio blocks of a flow to other applications over OMT
- **Send Frame** — Publishes an image to other applications over NDI, OMT, Syphon or Spout
