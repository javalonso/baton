"""Request-scoped wiring: a store, an identity, a language, and a date.

The store is per request rather than per process. A Lambda container outlives an invocation,
and a store that cached this morning's alerts would keep serving them all afternoon.

`today` is the dataset's date, not the wall clock. The seed describes a world as of a fixed
day, so a demo recorded in September still shows a network that visited people yesterday.
Passing `?date=` overrides it, which is how the tests walk through time.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status

from api.auth import verify
from core.models import Volunteer
from core.store import Store, open_store


def get_store() -> Store:
    return open_store()


StoreDep = Annotated[Store, Depends(get_store)]


def identity(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in first")
    payload = verify(authorization.split(" ", 1)[1])
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "that session has expired")
    return payload


IdentityDep = Annotated[dict, Depends(identity)]


def coordinator(who: IdentityDep) -> dict:
    if who["role"] != "coordinator":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "coordinators only")
    return who


CoordinatorDep = Annotated[dict, Depends(coordinator)]


def current_volunteer(who: IdentityDep, store: StoreDep) -> Volunteer:
    if who["role"] != "volunteer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "volunteers only")
    try:
        return store.volunteer(who["sub"])
    except StopIteration:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "that volunteer is gone") from None


VolunteerDep = Annotated[Volunteer, Depends(current_volunteer)]


def locale(
    lang: Annotated[str | None, Query(pattern="^(es|en)$")] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> str:
    """Language is resolved at the edge and nowhere else. Stored data stays neutral."""
    if lang:
        return lang
    if accept_language and accept_language.lower().startswith("en"):
        return "en"
    return "es"


LocaleDep = Annotated[str, Depends(locale)]


def as_of(store: StoreDep, date_: Annotated[date | None, Query(alias="date")] = None) -> date:
    return date_ or date.fromisoformat(store.generated_for)


AsOfDep = Annotated[date, Depends(as_of)]
