# app/utils.py
import os
import requests
from typing import Optional
from .lean_auth import LeanTokenManager

LEAN_BASE = os.getenv("LEAN_BASE_URL", "https://sandbox.leantech.me")

CERT: Optional[tuple[str, str]] = None
# if os.getenv("LEAN_CLIENT_CERT_PATH") and os.getenv("LEAN_CLIENT_KEY_PATH"):
#     CERT = (
#         os.getenv("LEAN_CLIENT_CERT_PATH"),
#         os.getenv("LEAN_CLIENT_KEY_PATH"),
#     )


def lean_request(method: str, path: str, *, json: Optional[dict] = None, timeout: int = 20) -> dict:
    """Generic request handler for Lean API (with Redis-backed token cache)."""
    url = f"{LEAN_BASE}{path}"

    access_token = LeanTokenManager.get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    request_args = {
        "headers": headers,
        "timeout": timeout,
        "cert": CERT if CERT else None,
    }
    if json is not None:
        request_args["json"] = json

    r = requests.request(method, url, **{k: v for k, v in request_args.items() if v is not None})
    r.raise_for_status()
    return r.json()


def lean_post(path: str, json: dict, timeout: int = 20) -> dict:
    return lean_request("POST", path, json=json, timeout=timeout)


def lean_get(path: str, timeout: int = 20) -> dict:
    return lean_request("GET", path, timeout=timeout)
