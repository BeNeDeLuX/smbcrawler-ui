from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet

from .config import settings

_key = settings.fernet_key.encode() if settings.fernet_key else Fernet.generate_key()
_fernet = Fernet(_key)


def encrypt_json(data: dict[str, Any]) -> bytes:
    return _fernet.encrypt(json.dumps(data).encode())


def decrypt_json(blob: bytes) -> dict[str, Any]:
    return json.loads(_fernet.decrypt(blob).decode())
