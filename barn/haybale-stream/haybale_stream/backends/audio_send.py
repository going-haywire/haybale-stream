"""A FIFO and sender thread that put audio blocks on the wire with sample-count timestamps."""

from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

from .base import AudioSender

log = logging.getLogger(__name__)

#: OMT timestamps count 100 ns ticks.
TICKS_PER_SECOND = 10_000_000


def timestamp_ticks(sample_count: int, sample_rate: int) -> int:
    """The stream time of the sample ``sample_count`` frames in, in 100 ns ticks."""
    return sample_count * TICKS_PER_SECOND // sample_rate


class AudioSendQueue:
    """Decouples a node's worker from the network: ``put`` queues a copy, a thread sends it.

    The thread stamps each block with the frames sent so far on this connection, so the
    receiver sees a steady clock whatever the upstream jitter. The count restarts when the
    sample rate or channel count changes. A full FIFO drops the new block and counts it.
    """

    def __init__(self, sender: AudioSender, capacity: int = 64) -> None:
        self._sender = sender
        self._fifo: queue.Queue[tuple[np.ndarray, int, float]] = queue.Queue(maxsize=capacity)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._format: tuple[int, int] | None = None
        self.sample_count = 0
        self.blocks_sent = 0
        self.dropped = 0
        self.last_wait = 0.0
        self.max_wait = 0.0
        self.error: Exception | None = None

    @property
    def depth(self) -> int:
        return self._fifo.qsize()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"AudioSend-{self._sender.name}", daemon=True)
        self._thread.start()

    def put(self, samples: np.ndarray, sample_rate: int) -> bool:
        """Queue a copy of ``samples``; ``False`` when the FIFO is full and the block is dropped."""
        block = np.array(samples, dtype=np.float32, order="C")
        try:
            self._fifo.put_nowait((block, sample_rate, time.perf_counter()))
        except queue.Full:
            self.dropped += 1
            return False
        return True

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                block, rate, queued_at = self._fifo.get(timeout=0.05)
            except queue.Empty:
                continue
            self.last_wait = time.perf_counter() - queued_at
            self.max_wait = max(self.max_wait, self.last_wait)
            fmt = (rate, block.shape[0])
            if fmt != self._format:
                self._format, self.sample_count = fmt, 0
            try:
                self._sender.send_audio(block, rate, timestamp_ticks(self.sample_count, rate))
            except Exception as exc:
                log.exception("audio send failed")
                self.error = exc
                return
            self.sample_count += block.shape[1]
            self.blocks_sent += 1
