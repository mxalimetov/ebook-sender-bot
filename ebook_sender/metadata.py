from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

LOGGER = logging.getLogger(__name__)
_FIELD_RE = re.compile(r"^(?P<key>[^:]+):\s*(?P<value>.*)$")


@dataclass(frozen=True)
class EbookMetadata:
    title: str | None
    authors: Tuple[str, ...]
    format: str | None = None


def extract_metadata(path: Path, file_format: str | None = None) -> EbookMetadata:
    """Return (title, authors) parsed via Calibre's `ebook-meta` CLI."""
    try:
        result = subprocess.run(  # noqa: S603,S607  (trusted path, no shell)
            ["ebook-meta", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        LOGGER.info("ebook-meta not found; skipping metadata extraction.")
        return EbookMetadata(title=None, authors=tuple(), format=file_format)
    except Exception:
        LOGGER.exception("Failed to run ebook-meta")
        return EbookMetadata(title=None, authors=tuple(), format=file_format)

    if result.returncode != 0:
        LOGGER.warning("ebook-meta exited with %s: %s", result.returncode, result.stderr.strip())

    title = _extract_field("Title", result.stdout)
    authors_field = _extract_field("Author(s)", result.stdout)
    authors: Tuple[str, ...] = tuple(
        value.strip()
        for value in (authors_field.split(",") if authors_field else [])
        if value.strip()
    )

    return EbookMetadata(title=title or None, authors=authors, format=file_format)


def _extract_field(key: str, text: str) -> str | None:
    for line in text.splitlines():
        match = _FIELD_RE.match(line.strip())
        if match and match.group("key").lower().startswith(key.lower()):
            value = match.group("value").strip()
            return value or None
    return None
