"""Source lists for UI dropdowns: what the last query found, and the query itself.

Discovery can take seconds (NDI, OMT wait for the network), so it runs only when asked
(``find_sources``, behind the dropdown's refresh button, off the UI thread). Building or
opening a dropdown reads ``known_sources``, which never touches the network.
"""

from __future__ import annotations

import logging
import threading

from . import BACKENDS

log = logging.getLogger(__name__)

_lock = threading.Lock()
_found: dict[str, list[str]] = {}


def known_sources(key: str) -> list[str]:
    """Sources the last ``find_sources(key)`` found (``[]`` before the first query)."""
    with _lock:
        return list(_found.get(key, []))


def find_sources(key: str, wait: float = 1.0) -> list[str]:
    """Query backend ``key`` for its sources now (blocks up to about ``wait`` s) and remember them."""
    backend = BACKENDS.get(key)
    if backend is None or not backend.is_available():
        return []
    try:
        found = backend.discover(wait=wait)
    except Exception:
        log.warning("discovery failed for %s", key, exc_info=True)
        return known_sources(key)
    with _lock:
        _found[key] = list(found)
    return list(found)


def all_known_sources() -> list[str]:
    """Sources last found on every backend, de-duplicated, for a backend-agnostic dropdown."""
    seen: dict[str, None] = {}
    for key in BACKENDS:
        for name in known_sources(key):
            seen.setdefault(name)
    return list(seen)
