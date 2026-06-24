from __future__ import annotations

import os
from pathlib import Path


class SecretConfigurationError(ValueError):
    pass


def read_secret(name: str, default: str | None = None) -> str | None:
    value = _blank_to_none(os.getenv(name))
    file_path = _blank_to_none(os.getenv(f"{name}_FILE"))
    if value and file_path:
        raise SecretConfigurationError(f"configure only one of {name} or {name}_FILE")
    if file_path:
        try:
            value = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretConfigurationError(f"{name}_FILE could not be read") from exc
    return _blank_to_none(value) or default


def secret_configured(name: str) -> bool:
    return bool(_blank_to_none(os.getenv(name)) or _blank_to_none(os.getenv(f"{name}_FILE")))


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None
