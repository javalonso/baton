"""Domain objects to the shapes screens want.

Every join a client would otherwise make itself lives here: a shift carries the names of the
person and the volunteer, a person's card carries when somebody last knocked. A phone on a
bad connection should make one request per screen.
"""

from __future__ import annotations

from datetime import date, datetime

from api.schemas import ElderCard, ShiftCard, Timeline, VolunteerLoad
from core.models import Elder, Shift, Visit
from core.store import Store


def shift_card(shift: Shift, store: Store) -> ShiftCard:
    names = store.volunteer_names()
    elder = store.elder(shift.elder_id)
    return ShiftCard(
        id=shift.id,
        elder_id=elder.id,
        elder_name=elder.name,
        address=elder.address,
        scheduled_at=shift.scheduled_at,
        status=shift.status,
        volunteer_id=shift.volunteer_id,
        volunteer_name=names.get(shift.volunteer_id or "", ""),
    )


def elder_card(elder: Elder, store: Store, as_of: date, alert_text: str = "") -> ElderCard:
    visits = store.visits_for(elder.id)
    last = visits[-1] if visits else None
    names = store.volunteer_names()
    return ElderCard(
        id=elder.id,
        name=elder.name,
        address=elder.address,
        last_visit=last.started_at if last else None,
        last_visit_by=names.get(last.volunteer_id, "") if last else "",
        days_since_visit=(as_of - last.started_at.date()).days if last else None,
        alert=alert_text,
    )


def timeline(visits: list[Visit], names: dict[str, str], limit: int = 20) -> list[Timeline]:
    """Most recent first. Quotes travel with the summary, so a reader can always check."""
    rows = []
    for visit in sorted(visits, key=lambda v: v.started_at, reverse=True)[:limit]:
        rows.append(
            Timeline(
                at=visit.started_at,
                volunteer_name=names.get(visit.volunteer_id, ""),
                summary="; ".join(o.summary for o in visit.observations) or visit.transcript[:120],
                quotes=[o.quote for o in visit.observations if o.quote],
            )
        )
    return rows


def volunteer_load(store: Store, carrying: list[str], quiet: list[str]) -> list[VolunteerLoad]:
    counts = store.visit_counts()
    rows = [
        VolunteerLoad(
            id=v.id,
            name=v.name,
            visits=counts.get(v.id, 0),
            carrying=v.name in carrying or v.id in carrying,
            quiet=v.name in quiet or v.id in quiet,
        )
        for v in store.volunteers
        if v.active
    ]
    return sorted(rows, key=lambda r: -r.visits)


def same_day(moment: datetime, day: date) -> bool:
    return moment.date() == day
