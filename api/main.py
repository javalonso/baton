"""The only thing the apps talk to.

FastAPI in front of `core/`, deployed as a single Lambda behind an HTTP API. The agents are
called in-process rather than over HTTP: they read `core/` directly, so putting the API
between them would mean the API calling itself.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from api.auth import identify, issue
from api.deps import IdentityDep, LocaleDep, StoreDep
from api.routers import coordinator, internal, volunteer
from api.schemas import LoginRequest, Session
from api.settings import ALLOWED_ORIGINS

app = FastAPI(
    title="Baton",
    description="An agent that carries the memory of a community care network.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"ok": True}


@app.post("/auth/login", response_model=Session, tags=["auth"])
def login(body: LoginRequest, store: StoreDep, locale: LocaleDep) -> Session:
    """Six digits and nothing else.

    The failure message never says whether the code was almost right, because there is no
    version of "no such volunteer" that helps an honest person and does not help a guesser.
    """
    found = identify(store, body.code)
    if not found:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "that code did not work")

    role, subject = found
    name = store.organization["name"] if role == "coordinator" else store.volunteer(subject).name
    if role == "volunteer":
        locale = store.volunteer(subject).locale
    return Session(
        token=issue(role, subject, store.org_id),
        role=role,
        id=subject,
        name=name,
        org=store.organization["name"],
        locale=locale,
    )


@app.get("/auth/me", response_model=Session, tags=["auth"])
def me(who: IdentityDep, store: StoreDep, locale: LocaleDep) -> Session:
    """Who this token belongs to, so an app can resume without asking for the code again."""
    role, subject = who["role"], who["sub"]
    name = store.organization["name"] if role == "coordinator" else store.volunteer(subject).name
    return Session(
        token="",
        role=role,
        id=subject,
        name=name,
        org=store.organization["name"],
        locale=locale,
    )


app.include_router(volunteer.router)
app.include_router(coordinator.router)
app.include_router(internal.router)

handler = Mangum(app)
