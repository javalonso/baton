"""The four screens a volunteer sees, standing outside somebody's door.

Every response here is scoped to the person holding the phone. A volunteer can read the
record of somebody they are scheduled to visit and nobody else, which is enforced in
`_may_visit` rather than trusted to the client.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from agents import brief as brief_agent
from agents import intake
from api.deps import AsOfDep, LocaleDep, StoreDep, VolunteerDep
from api.schemas import (
    BriefResponse,
    ClaimResponse,
    ConfirmRequest,
    RecordRequest,
    RecordResponse,
    ShiftCard,
    TodayResponse,
)
from api.views import elder_card, shift_card
from core.models import Visit
from core.store import ShiftAlreadyClaimed, Store

router = APIRouter(prefix="/me", tags=["volunteer"])

#: How far ahead the open-shift list looks. Beyond this a gap is real but not yet anybody's
#: evening, and a list that shows every hole for the next month is a list nobody reads.
OPEN_HORIZON_DAYS = 7


def _may_visit(store: Store, volunteer_id: str, elder_id: str) -> bool:
    """True if this volunteer is scheduled to see this person, or ever has."""
    if any(s.elder_id == elder_id and s.volunteer_id == volunteer_id for s in store.shifts):
        return True
    return any(v.volunteer_id == volunteer_id for v in store.visits_for(elder_id))


def _guard(store: Store, volunteer_id: str, elder_id: str) -> None:
    if not _may_visit(store, volunteer_id, elder_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "that is not one of your visits")


@router.get("/today", response_model=TodayResponse)
def today(volunteer: VolunteerDep, store: StoreDep, as_of: AsOfDep) -> TodayResponse:
    """V1. Today's rounds, in the order they happen."""
    mine = [
        s
        for s in store.shifts
        if s.volunteer_id == volunteer.id and s.scheduled_at.date() == as_of
    ]
    mine.sort(key=lambda s: s.scheduled_at)
    cards = [shift_card(s, store) for s in mine]
    people = [elder_card(store.elder(s.elder_id), store, as_of) for s in mine]
    return TodayResponse(as_of=as_of, volunteer=volunteer.name, shifts=cards, people=people)


@router.get("/elders/{elder_id}/brief", response_model=BriefResponse)
def brief(
    elder_id: str,
    volunteer: VolunteerDep,
    store: StoreDep,
    as_of: AsOfDep,
    locale: LocaleDep,
    refresh: bool = False,
) -> BriefResponse:
    """V2. The thing that does not exist today: what changed, and how to be with them.

    Slow the first time somebody asks for a person on a given day, and immediate after that.
    The prose describes one person as of one date, so the second volunteer through the same
    door reads what the first one read rather than paying for it again.
    """
    _guard(store, volunteer.id, elder_id)
    elder = store.elder(elder_id)
    cached = store.get_brief(elder_id, as_of, locale) is not None and not refresh
    written = brief_agent.write(
        elder_id, store=store, as_of=as_of, locale=locale, refresh=refresh
    )
    visits = store.visits_for(elder_id)
    return BriefResponse(
        elder_id=elder_id,
        elder_name=elder.name,
        brief=written,
        last_visit=visits[-1].started_at if visits else None,
        written_by_model=written.written_by_model,
        cached=cached,
    )


@router.post("/visits", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
def record(
    body: RecordRequest,
    volunteer: VolunteerDep,
    store: StoreDep,
) -> RecordResponse:
    """V3. A spoken note becomes chips the volunteer can correct. Never a form.

    The visit is stored unconfirmed. What the model heard is a proposal until somebody who
    was actually in the room agrees with it.
    """
    _guard(store, volunteer.id, body.elder_id)
    elder = store.elder(body.elder_id)
    try:
        extraction = intake.extract(body.transcript)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could not read that note; it was not saved"
        ) from exc

    visit = Visit(
        id=f"visit-{uuid.uuid4().hex[:12]}",
        shift_id=body.shift_id,
        elder_id=body.elder_id,
        volunteer_id=volunteer.id,
        started_at=datetime.now(),
        transcript=body.transcript,
        source_lang=extraction.source_lang,
        observations=extraction.observations,
        confirmed=False,
    )
    store.add_visit(visit)
    return RecordResponse(
        visit_id=visit.id,
        elder_name=elder.name,
        source_lang=extraction.source_lang,
        observations=extraction.observations,
        followups=extraction.followups,
    )


@router.patch("/visits/{visit_id}", response_model=RecordResponse)
def confirm(
    visit_id: str,
    body: ConfirmRequest,
    volunteer: VolunteerDep,
    store: StoreDep,
) -> RecordResponse:
    """The volunteer's corrections win. Their version is the one the record keeps."""
    visit = next((v for v in store.visits if v.id == visit_id), None)
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such visit")
    if visit.volunteer_id != volunteer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "that is not your visit")

    visit.observations = body.observations
    visit.confirmed = True
    store.add_visit(visit)
    return RecordResponse(
        visit_id=visit.id,
        elder_name=store.elder(visit.elder_id).name,
        source_lang=visit.source_lang,
        observations=visit.observations,
        followups=body.followups,
    )


@router.get("/shifts/open", response_model=list[ShiftCard])
def open_shifts(volunteer: VolunteerDep, store: StoreDep, as_of: AsOfDep) -> list[ShiftCard]:
    """V4. Gaps anybody can fill, soonest first."""
    horizon = as_of + timedelta(days=OPEN_HORIZON_DAYS)
    gaps = [
        s
        for s in store.shifts
        if s.volunteer_id is None and as_of <= s.scheduled_at.date() <= horizon
    ]
    gaps.sort(key=lambda s: s.scheduled_at)
    return [shift_card(s, store) for s in gaps]


@router.post("/shifts/{shift_id}/claim", response_model=ClaimResponse)
def claim(shift_id: str, volunteer: VolunteerDep, store: StoreDep, locale: LocaleDep) -> ClaimResponse:
    """One tap. The second person to tap is told plainly, not shown a stale success."""
    try:
        shift = store.claim_shift(shift_id, volunteer.id)
    except StopIteration:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such shift") from None
    except ShiftAlreadyClaimed:
        taken = {
            "es": "Alguien mas ya lo tomo. Gracias por ofrecerte.",
            "en": "Somebody else got there first. Thank you for offering.",
        }
        raise HTTPException(status.HTTP_409_CONFLICT, taken[locale]) from None

    done = {
        "es": "Listo, quedaste tu.",
        "en": "Done, it is yours.",
    }
    return ClaimResponse(shift=shift_card(shift, store), message=done[locale])


@router.get("/code-check")
def code_check(volunteer: VolunteerDep) -> dict:
    """Cheap call the app makes on launch to find out whether its token still works."""
    return {"id": volunteer.id, "name": volunteer.name, "locale": volunteer.locale}
