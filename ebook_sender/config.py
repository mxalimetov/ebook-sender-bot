from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    stkclient_client_path: Path
    device_serials: Optional[Tuple[str, ...]] = None


def load_settings() -> Settings:
    """Load settings from the environment (supports .env files)."""
    load_dotenv()

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    client_path_str = os.getenv("STKCLIENT_CLIENT_PATH")
    device_serials_env = os.getenv("KINDLE_DEVICE_SERIALS")

    missing = {
        "TELEGRAM_BOT_TOKEN": telegram_token,
        "STKCLIENT_CLIENT_PATH": client_path_str,
    }

    missing_vars = [name for name, value in missing.items() if not value]
    if missing_vars:
        joined = ", ".join(missing_vars)
        raise RuntimeError(f"Missing required environment variables: {joined}")

    client_path = Path(client_path_str)
    if not client_path.exists():
        raise RuntimeError(f"stkclient client file not found: {client_path}")

    device_serials: Optional[Tuple[str, ...]] = None
    if device_serials_env:
        parts = [value.strip() for value in device_serials_env.split(",") if value.strip()]
        if parts:
            device_serials = tuple(parts)

    return Settings(
        telegram_token=telegram_token,
        stkclient_client_path=client_path,
        device_serials=device_serials,
    )
