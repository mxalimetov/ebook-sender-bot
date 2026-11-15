from __future__ import annotations

import asyncio
import gzip
import importlib
import json
import logging
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from .metadata import EbookMetadata

LOGGER = logging.getLogger(__name__)
_SEND_PATCH_APPLIED = False


class KindleSender:
    """Handles Kindle delivery through a serialized stkclient Client."""

    def __init__(
        self,
        client_path: Path,
        device_serials: Optional[Sequence[str]] = None,
    ) -> None:
        _ensure_fixed_send_to_kindle()
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
        if self._client_path.exists():
            loader = self._resolve_client_loader()
            with self._client_path.open("r", encoding="utf-8") as fh:
                LOGGER.debug("Loading stkclient Client from %s", self._client_path)
                return loader.load(fh)

        return self._bootstrap_client()

    def _resolve_client_loader(self):
        import stkclient  # type: ignore

        if hasattr(stkclient, "Client"):
            return getattr(stkclient, "Client")

        module = importlib.import_module("stkclient.client")
        if hasattr(module, "Client"):
            return getattr(module, "Client")
        raise RuntimeError("stkclient Client class not found. Check your installation.")

    def _bootstrap_client(self):
        oauth = self._create_oauth()
        signin_url = oauth.get_signin_url()
        LOGGER.warning(
            "stkclient client file missing at %s. Authorize the application via: %s",
            self._client_path,
            signin_url,
        )

        redirect_url = self._prompt_redirect_url()
        client = oauth.create_client(redirect_url)
        self._persist_client(client)
        LOGGER.info("Created new stkclient client at %s", self._client_path)
        return client

    def _create_oauth(self):
        import stkclient  # type: ignore

        if not hasattr(stkclient, "OAuth2"):
            raise RuntimeError("This stkclient version does not expose OAuth2 support.")
        return stkclient.OAuth2()

    def _prompt_redirect_url(self) -> str:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "stkclient client file is missing and the process is non-interactive. "
                "Re-run the bot from a terminal to supply the redirect URL after authorizing."
                f" Expected location: {self._client_path}"
            )

        prompt = (
            "Paste the final redirect URL from Amazon after authorizing stkclient: "
        )
        redirect_url = input(prompt).strip()
        if not redirect_url:
            raise RuntimeError("No redirect URL provided; cannot create stkclient client.")
        return redirect_url

    def _persist_client(self, client) -> None:
        self._client_path.parent.mkdir(parents=True, exist_ok=True)
        with self._client_path.open("w", encoding="utf-8") as fh:
            client.dump(fh)

    def _discover_destinations(self) -> Tuple[str, ...]:
        LOGGER.debug("Fetching owned Kindle devices via stkclient")
        devices = self._client.get_owned_devices()
        owned = getattr(devices, "owned_devices", None)
        if not owned:
            return tuple()

        serials = []
        for device in owned:
            serial = getattr(device, "device_serial_number", None)
            name = (
                getattr(device, "device_name", None)
                or getattr(device, "friendly_name", None)
                or getattr(device, "name", None)
            )
            if serial:
                serials.append(serial)
                LOGGER.info(
                    "Detected Kindle device serial %s%s",
                    serial,
                    f" ({name})" if name else "",
                )

        if serials and not self._device_serials:
            LOGGER.info(
                "KINDLE_DEVICE_SERIALS is unset; using all detected devices. "
                "Set it to a comma-separated subset to target specific devices."
            )

        return tuple(serials)

    async def send(self, document_path: Path, metadata: EbookMetadata) -> None:
        async with self._lock:
            await asyncio.to_thread(self._send_sync, document_path, metadata)

    def _send_sync(self, document_path: Path, metadata: EbookMetadata) -> None:
        LOGGER.info("Sending %s to Kindle devices", document_path.name)
        destinations = list(self._destinations)
        if not destinations:
            raise RuntimeError("No Kindle destinations available for delivery.")

        title = metadata.title or document_path.stem
        author = ", ".join(metadata.authors) if metadata.authors else "Telegram Bot"
        fmt = (metadata.format or document_path.suffix.lstrip(".")) or "pdf"
        self._client.send_file(
            document_path,
            destinations,
            author=author,
            title=title,
            format=fmt,
        )


def _ensure_fixed_send_to_kindle() -> None:
    global _SEND_PATCH_APPLIED
    if _SEND_PATCH_APPLIED:
        return

    import stkclient  # type: ignore

    api_module = importlib.import_module("stkclient.api")

    def _patched_request(path, signer, body):
        data = json.dumps(
            {
                "clientInfo": api_module.DEFAULT_CLIENT_INFO,
                **body,
            },
            indent=4,
        )
        req = urllib.request.Request(
            url="https://kd.amazon.com" + path,
            data=data.encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
                "X-ADP-Request-Digest": signer.digest_header_for_request("POST", path, data),
                "X-ADP-Authentication-Token": signer.adp_token,
                "Accept-Language": "en-US,*",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            encoding = r.headers.get("Content-Encoding", "")
            if encoding == "gzip":
                raw = gzip.decompress(raw)
            val: Mapping[str, Any] = json.loads(raw)
            return val

    api_module._request = _patched_request
    _SEND_PATCH_APPLIED = True
