"""Resolve the backend-only Supabase server credential."""

from __future__ import annotations

import base64
import binascii
import json
import os


def _is_privileged_key(value: str) -> bool:
    if value.startswith("sb_secret_"):
        return True
    parts = value.split(".")
    if len(parts) != 3:
        return False
    try:
        payload_part = parts[1].replace("-", "+").replace("_", "/")
        payload_part += "=" * ((4 - len(payload_part) % 4) % 4)
        payload = json.loads(base64.b64decode(payload_part).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return payload.get("role") == "service_role"


def get_supabase_service_key() -> str:
    canonical = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    legacy = os.getenv("SUPABASE_KEY", "").strip()
    if canonical and not _is_privileged_key(canonical):
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY must be a privileged Supabase service/secret key")
    if legacy and not _is_privileged_key(legacy):
        raise RuntimeError("SUPABASE_KEY must be a privileged server key; anon/public keys are not accepted")
    return canonical or legacy or _raise_missing_key()


def _raise_missing_key() -> str:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for backend access")
