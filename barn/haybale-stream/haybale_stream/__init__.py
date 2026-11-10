"""Haybale Stream: send and receive video frames over NDI, OMT, Syphon and Spout, and audio over OMT."""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry


@library(file_watcher=False)
class Library(BaseLibrary):
    """Stream library: frame and audio sharing nodes over the backends in ``haybale_stream.backends``."""

    def register_components(self):
        """Register the node folder."""
        base_path = Path(__file__).parent
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

    def validate(self) -> bool:
        return True


__all__ = ["Library"]
