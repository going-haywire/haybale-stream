"""Keeps the macOS main run loop turning inside haywire, for Syphon.

Syphon finds servers through distributed notifications, which macOS delivers only while
the main thread's run loop runs. haywire's main thread runs asyncio instead, so without
this a Syphon receiver finds no server and a Syphon sender answers no client's request.
A callback on the app's event loop hands the pending run-loop events through every 100 ms.
"""

import logging
import sys
import threading

log = logging.getLogger(__name__)

_INTERVAL = 0.1
_lock = threading.Lock()
_started = False


def ensure_main_run_loop(backend_key: str) -> None:
    """Start the pump for a Syphon backend, once; a no-op elsewhere or before the app runs."""
    global _started
    if backend_key != "syphon" or sys.platform != "darwin" or _started:
        return
    from nicegui import core

    from ..backends import get_backend

    loop = core.loop
    if loop is None or not loop.is_running() or not get_backend("syphon").is_available():
        return  # tried again on the next call
    with _lock:
        if _started:
            return
        _started = True

    from ..backends.syphon import pump_main_run_loop

    def tick() -> None:
        if threading.current_thread() is not threading.main_thread():
            log.warning("the event loop is not on the main thread; Syphon discovery cannot run")
            return
        try:
            pump_main_run_loop()
        except Exception:
            log.exception("pumping the main run loop failed")
        loop.call_later(_INTERVAL, tick)

    loop.call_soon_threadsafe(tick)
