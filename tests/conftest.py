"""Fixtures for this repo's own suite (mirrors haybale-visiongraph's conftest)."""

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """The repo root (the directory holding ``barn/``)."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def library_system(project_root: Path) -> Iterator[object]:
    """A fully initialised library system with this repo's library loaded."""
    from haywire.core.di.config import set_global_injector, set_library_system
    from haywire.core.di.test_config import create_test_library_system

    service = create_test_library_system(
        workspace_root=str(project_root),
        library_paths=[str(project_root / "barn")],
        load_libraries=True,
        enable_file_watching=False,
    )
    set_library_system(service)
    set_global_injector(service.injector)

    yield service

    lib_registry = service.get_library_registry()
    if hasattr(lib_registry, "stop_file_watching"):
        lib_registry.stop_file_watching()
    set_library_system(None)
    set_global_injector(None)
