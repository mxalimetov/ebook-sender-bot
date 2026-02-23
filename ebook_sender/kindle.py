from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Optional, Sequence, Tuple

LOGGER = logging.getLogger(__name__)


class KindleSender:
    """Handles Kindle delivery through a serialized stkclient Client."""

    def __init__(
        self,
        client_path: Path,
        device_serials: Optional[Sequence[str]] = None,
    ) -> None:
        self._client_path = client_path
        self._device_serials = tuple(device_serials) if device_serials else None
        self._lock = asyncio.Lock()
        self._client = self._load_client()
        self._destinations = self._device_serials or self._discover_destinations()
        if not self._destinations:
            raise RuntimeError(
                "No Kindle destinations configured. Provide KINDLE_DEVICE_SERIALS or ensure "
                "get_owned_devices() returns owned_devices entries."
            )

    def _load_client(self):
        loader = self._resolve_client_loader()
        with self._client_path.open("r", encoding="utf-8") as fh:
            LOGGER.debug("Loading stkclient Client from %s", self._client_path)
            return loader.load(fh)

    def _resolve_client_loader(self):
        import stkclient  # type: ignore

        if hasattr(stkclient, "Client"):
            return getattr(stkclient, "Client")

        module = importlib.import_module("stkclient.client")
        if hasattr(module, "Client"):
            return getattr(module, "Client")
        raise RuntimeError("stkclient Client class not found. Check your installation.")

    def _discover_destinations(self) -> Tuple[str, ...]:
        LOGGER.debug("Fetching owned Kindle devices via stkclient")
        devices = self._client.get_owned_devices()
        owned = getattr(devices, "owned_devices", None)
        if not owned:
            return tuple()
        serials = [getattr(device, "device_serial_number", None) for device in owned]
        cleaned = tuple(serial for serial in serials if serial)
        return cleaned

    async def send(self, document_path: Path, title: str, format: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._send_sync, document_path, title, format)

    def _send_sync(self, document_path: Path, title: str, format: str) -> None:
        LOGGER.info("Sending %s to Kindle devices", document_path.name)
        destinations = list(self._destinations)
        if not destinations:
            raise RuntimeError("No Kindle destinations available for delivery.")
        self._client.send_file(
            document_path,
            destinations,
            author="Telegram Bot",
            title=title,
            format=format,
        )
