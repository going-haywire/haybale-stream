"""Syphon backend (macOS, Metal), on syphon-python.

UNTESTED on the Linux development machine: the module imports cleanly everywhere, but
``syphon-python`` only has a macOS wheel, so ``unavailable_reason()`` reports the
platform elsewhere. Frames cross the CPU (numpy <-> MTLTexture) because haywire images
live in system memory; a zero-copy GPU path would need a GPU image type.

Server names are shown as ``"<app> | <name>"`` (just ``"<app>"`` when the server is unnamed).
"""

from __future__ import annotations

import numpy as np

from .base import Backend, BackendUnavailable, Frame, Receiver, Sender


def _title(server: object) -> str:
    return f"{server.app_name} | {server.name}" if server.name else server.app_name


class SyphonSender(Sender):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._server = None
        self._directory = None
        self._texture = None

    def open(self) -> None:
        import syphon

        self._server = syphon.SyphonMetalServer(self.name)
        # A headless process must pump the directory's run loop to answer discovery requests.
        self._directory = syphon.SyphonServerDirectory()

    def send(self, pixels: np.ndarray, frame_rate: float = 30.0) -> None:
        from syphon.utils.numpy import copy_image_to_mtl_texture
        from syphon.utils.raw import create_mtl_texture

        if self._server is None:
            return
        height, width = pixels.shape[:2]
        if self._texture is None or self._texture.width() != width or self._texture.height() != height:
            self._texture = create_mtl_texture(self._server.device, width, height)
        copy_image_to_mtl_texture(np.ascontiguousarray(pixels, dtype=np.uint8), self._texture)
        # Metal textures, like numpy rows, start at the top-left: flipped=True in Syphon terms.
        self._server.publish_frame_texture(self._texture, size=[width, height], is_flipped=True)
        self._directory.update_run_loop()

    def close(self) -> None:
        self._texture = None
        directory, self._directory = self._directory, None
        server, self._server = self._server, None
        if directory is not None:
            directory.stop()
        if server is not None:
            server.stop()


class SyphonReceiver(Receiver):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self._client = None
        self._directory = None

    def open(self, timeout: float = 5.0) -> None:
        import syphon

        directory = syphon.SyphonServerDirectory()
        directory.update_run_loop()
        description = next((s for s in directory.servers if _title(s) == self.source), None)
        if description is None:
            directory.stop()
            raise LookupError(f"Syphon server {self.source!r} not found")
        self._directory = directory
        self._client = syphon.SyphonMetalClient(description)

    def poll(self, timeout: float = 0.0) -> Frame | None:
        from syphon.utils.numpy import copy_mtl_texture_to_image

        client = self._client
        if client is None:
            return None
        self._directory.update_run_loop()
        if not client.has_new_frame:
            return None
        texture = client.new_frame_image
        return Frame(np.array(copy_mtl_texture_to_image(texture), dtype=np.uint8))

    def close(self) -> None:
        client, self._client = self._client, None
        directory, self._directory = self._directory, None
        if client is not None:
            client.stop()
        if directory is not None:
            directory.stop()


class SyphonBackend(Backend):
    key = "syphon"
    label = "Syphon"
    platforms = ("darwin",)
    channel_order = "rgba"

    @classmethod
    def _check_dependency(cls) -> str | None:
        try:
            import syphon  # noqa: F401
        except ImportError as exc:
            return f"Syphon needs the 'syphon-python' package ({exc})"
        return None

    @classmethod
    def discover(cls, wait: float = 0.0) -> list[str]:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        import time

        import syphon

        directory = syphon.SyphonServerDirectory()
        try:
            deadline = time.monotonic() + wait
            directory.update_run_loop()
            while time.monotonic() < deadline:
                time.sleep(0.05)
                directory.update_run_loop()
            return sorted(_title(s) for s in directory.servers)
        finally:
            directory.stop()

    @classmethod
    def create_sender(cls, name: str, *, steady_stream: bool = False) -> Sender:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return SyphonSender(name)

    @classmethod
    def create_receiver(cls, source: str) -> Receiver:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return SyphonReceiver(source)
