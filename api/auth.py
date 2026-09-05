"""Who is holding the phone.

Volunteers do not have passwords. They have a six-digit code, and the code is derived from
their volunteer id with an HMAC rather than stored, so there is no password column to leak
and no reset flow to build. A coordinator who needs to revoke somebody rotates `BATON_SECRET`
and hands out new codes.

This is the right amount of authentication for a neighborhood roster and the wrong amount
for anything holding money. It is written down here so nobody has to guess later which one
this is.

The code is compared in constant time. Six digits is a small space, so the rate limit at the
edge is doing real work; see `infra/api.yaml`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Literal

from api.settings import COORDINATOR_CODE, SECRET, TOKEN_DAYS
from core.store import Store

Role = Literal["volunteer", "coordinator"]


def code_for(subject: str) -> str:
    """The six digits this person types in. Derived, never stored."""
    digest = hmac.new(SECRET.encode(), f"code:{subject}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 1_000_000:06d}"


def coordinator_code(org_id: str) -> str:
    return COORDINATOR_CODE or code_for(f"coordinator:{org_id}")


def identify(store: Store, code: str) -> tuple[Role, str] | None:
    """Match a code against the coordinator and then every volunteer.

    Every candidate is checked even after a match is found, so the time this takes says
    nothing about which volunteer it was.
    """
    code = code.strip()
    found: tuple[Role, str] | None = None
    if hmac.compare_digest(code, coordinator_code(store.org_id)):
        found = ("coordinator", store.org_id)
    for volunteer in store.volunteers:
        if hmac.compare_digest(code, code_for(volunteer.id)) and volunteer.active:
            found = ("volunteer", volunteer.id)
    return found


# -- tokens ------------------------------------------------------------------
#
# A minimal signed token rather than a JWT library. The payload is ours, the algorithm is
# fixed at HMAC-SHA256, and there is no `alg` field to be talked out of -- which is the
# failure mode that keeps happening to people who do use a library and accept `none`.


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(role: Role, subject: str, org_id: str) -> str:
    payload = {
        "role": role,
        "sub": subject,
        "org": org_id,
        "exp": int(time.time()) + TOKEN_DAYS * 86400,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def verify(token: str) -> dict | None:
    """Return the payload, or nothing at all. Never raises on a malformed token."""
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            return None
        payload = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001 -- anything malformed is simply not a token
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
