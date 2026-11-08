"""Non-blocking source lists for UI dropdowns.

Discovery can take seconds (NDI, OMT wait for the network), and a dropdown is built on the
UI thread. ``cached_sources`` returns what was last found and refreshes in the background.
"""

from __future__ import annotations

import logging
import threading
import time

from . import BACKENDS

log = logging.getLogger(__name__)

_REFRESH_EVERY = 3.0
_lock = threading.Lock()
_cache: dict[str, list[str]] = {}
_stamp: dict[str, float] = {}
_running: set[str] = set()


def _refresh(key: str) -> None:
    try:
        found = BACKENDS[key].discover(wait=1.0)
    except Exception:
        log.debug("discovery failed for %s", key, exc_info=True)
        found = []
    with _lock:
        _cache[key] = found
        _stamp[key] = time.monotonic()
        _running.discard(key)


def cached_sources(key: str) -> list[str]:
    """Sources last seen on backend ``key`` (``[]`` until the first refresh finishes)."""
    backend = BACKENDS.get(key)
    if backend is None or not backend.is_available():
        return []
    with _lock:
        stale = time.monotonic() - _stamp.get(key, float("-inf")) > _REFRESH_EVERY
        if stale and key not in _running:
            _running.add(key)
            threading.Thread(target=_refresh, args=(key,), name=f"hb-discover-{key}", daemon=True).start()
        return list(_cache.get(key, []))


def all_cached_sources() -> list[str]:
    """Sources from every runnable backend, de-duplicated, for a backend-agnostic dropdown."""
    seen: dict[str, None] = {}
    for key in BACKENDS:
        for name in cached_sources(key):
            seen.setdefault(name)
    return list(seen)
