"""Everything the API reads from its environment, in one place.

`BATON_SECRET` signs access tokens. It has a development default so a fresh clone runs, and
the deployment refuses to start without a real one -- a signing key that ships in a public
repo is not a signing key.
"""

from __future__ import annotations

import os

from core.aws import in_lambda

DEV_SECRET = "baton-development-secret-not-for-deployment"

SECRET = os.environ.get("BATON_SECRET", DEV_SECRET)
TOKEN_DAYS = int(os.environ.get("BATON_TOKEN_DAYS", "30"))
COORDINATOR_CODE = os.environ.get("BATON_COORDINATOR_CODE", "")
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("BATON_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]

if in_lambda() and SECRET == DEV_SECRET:
    raise RuntimeError("BATON_SECRET must be set outside development")
