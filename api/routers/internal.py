"""The two passes nobody presses a button for.

EventBridge calls these on a schedule: the watch sweep in the morning, the roster pass at
eight in the evening. They are the reason the product works when everybody is asleep, and
they are the endpoints most likely to be found by a scanner, so they take a shared token
that is never issued to a browser.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from agents import roster as roster_agent
from agents import watch as watch_agent
from api.deps import AsOfDep, LocaleDep, StoreDep

router = APIRouter(prefix="/internal", tags=["scheduled"])

JOB_TOKEN = os.environ.get("BATON_JOB_TOKEN", "")


def _authorize(x_baton_job: Annotated[str | None, Header()] = None) -> None:
    import hmac

    if not JOB_TOKEN or not x_baton_job or not hmac.compare_digest(x_baton_job, JOB_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not a scheduled caller")


@router.post("/watch")
def watch(
    store: StoreDep,
    as_of: AsOfDep,
    locale: LocaleDep,
    x_baton_job: Annotated[str | None, Header()] = None,
) -> dict:
    """The daily pass over everyone. Alerts are written so C1 keeps her decisions."""
    _authorize(x_baton_job)
    alerts, said = watch_agent.run(store=store, as_of=as_of, locale=locale)
    kept = {a.id for a in store.alerts}
    for alert in alerts:
        if alert.id not in kept:
            store.save_alert(alert)
    return {
        "as_of": as_of.isoformat(),
        "checked": len(store.elders),
        "opened": [a.id for a in alerts],
        "said": said,
    }


@router.post("/roster")
def roster(
    store: StoreDep,
    as_of: AsOfDep,
    locale: LocaleDep,
    x_baton_job: Annotated[str | None, Header()] = None,
) -> dict:
    """The evening pass over the schedule. Returns what would be sent, and to which rung."""
    _authorize(x_baton_job)
    coverage, messages = roster_agent.run(store=store, as_of=as_of, locale=locale)
    return {
        "as_of": as_of.isoformat(),
        "checked": coverage.checked,
        "quiet_evening": coverage.quiet_evening,
        "messages": [m.model_dump() for m in messages],
    }
