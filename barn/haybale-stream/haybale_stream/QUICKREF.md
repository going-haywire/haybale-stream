# haybale-stream — component index (v0.1.2)

## node
- `haybale-stream:node:ReceiveAudioEmitNode` — Receive Audio Emit — Receives audio from an OMT source on its own thread and emits a callback per block  _tags: stream, receive, emit, callback, omt, audio, sound, input_
- `haybale-stream:node:ReceiveFrameEmitNode` — Receive Frame Emit — Receives frames from NDI, OMT, Syphon or Spout on its own thread and emits a callback per frame  _tags: stream, receive, emit, callback, ndi, omt, syphon, spout, video, input_
- `haybale-stream:node:ReceiveFrameNode` — Receive Frame — Receives the newest image from another application over NDI, OMT, Syphon or Spout  _tags: stream, receive, ndi, omt, syphon, spout, video, input, texture sharing_
- `haybale-stream:node:SendAudioNode` — Send Audio — Publishes the audio blocks of a flow to other applications over OMT  _tags: stream, send, omt, audio, sound, output_
- `haybale-stream:node:SendFrameNode` — Send Frame — Publishes an image to other applications over NDI, OMT, Syphon or Spout  _tags: stream, send, ndi, omt, syphon, spout, video, output, texture sharing_
