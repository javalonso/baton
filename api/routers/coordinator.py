"""The five screens the coordinator sees, and the one thing they are all for.

Her job is twenty-four people and fourteen volunteers, and the product's claim is that most
of it should not reach her. So C1 is allowed to be empty, and when it is empty it says so
rather than showing an encouraging dashboard of numbers nobody asked for.

Alerts are recomputed from the record on every read rather than trusted from a table. The
detection is deterministic -- same visits, same alert -- so a stored row can only be stale.
What is stored is what a human did about it: acknowledged, dismissed, or not yet.
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from agents import brief as brief_agent
from api.deps import AsOfDep, CoordinatorDep, LocaleDep, StoreDep
from api.schemas import (
    CoordinatorToday,
    CoverageGap,
    CoverageResponse,
    ElderCard,
    ElderRecord,
    WeeklyReport,
)
from api.views import elder_card, shift_card, timeline, volunteer_load
from core.baseline import compute_baseline, detect
from core.models import Alert
from core.roster import assess
from core.store import Store

router = APIRouter(prefix="/coordinator", tags=["coordinator"], dependencies=[])


def _current_alerts(store: Store, as_of: date) -> list[Alert]:
    """Every alert the record justifies today, carrying whatever a human already decided."""
    decided = {a.id: a for a in store.alerts}
    names = store.volunteer_names()
    live: list[Alert] = []
    for elder in store.elders:
        alert = detect(elder.id, store.visits_for(elder.id), as_of, names)
        if alert is None:
            continue
        previous = decided.get(alert.id)
        if previous is not None:
            alert.status = previous.status
            alert.acknowledged_by = previous.acknowledged_by
        live.append(alert)
    live.sort(key=lambda a: (a.severity != "urgent", a.elder_id))
    return live


def _age(dob: date | None, as_of: date) -> int | None:
    if dob is None:
        return None
    return as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))


@router.get("/today", response_model=CoordinatorToday)
def today(who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> CoordinatorToday:
    """C1. Who needs her, what is uncovered, and the right to show nothing."""
    alerts = [a for a in _current_alerts(store, as_of) if a.status == "open"]
    coverage = assess(store, as_of)
    gaps = [
        CoverageGap(shift=shift_card(m.shift, store), rung=rung, days_late=m.days_late)
        for rung, group in (
            ("nudge", coverage.nudges),
            ("open", coverage.openings),
            ("escalation", coverage.escalations),
        )
        for m in group
    ]
    return CoordinatorToday(
        as_of=as_of,
        organization=store.organization["name"],
        alerts=alerts,
        gaps=gaps,
        people_checked=len(store.elders),
        quiet=not alerts and not gaps,
    )


@router.get("/alerts/{alert_id}", response_model=ElderRecord)
def alert_detail(alert_id: str, who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> ElderRecord:
    """C2. The alert, the baseline it broke, and the quotes that produced it.

    Served as the person's record with the alert attached, because the question a
    coordinator actually asks is "what is going on with them", not "tell me about alert 7".
    """
    alert = next((a for a in _current_alerts(store, as_of) if a.id == alert_id), None)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such alert")
    return _record(store, alert.elder_id, as_of, alert)


@router.post("/alerts/{alert_id}/{decision}", response_model=Alert)
def decide(
    alert_id: str,
    decision: str,
    who: CoordinatorDep,
    store: StoreDep,
    as_of: AsOfDep,
) -> Alert:
    """Acknowledge or dismiss. Either way the decision is recorded with her name on it."""
    if decision not in ("acknowledge", "dismiss"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "acknowledge or dismiss")
    alert = next((a for a in _current_alerts(store, as_of) if a.id == alert_id), None)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such alert")

    alert.status = "acknowledged" if decision == "acknowledge" else "dismissed"
    alert.acknowledged_by = who["sub"]
    return store.save_alert(alert)


@router.get("/elders", response_model=list[ElderCard])
def people(who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> list[ElderCard]:
    """Everyone the network looks after, the ones off pattern first."""
    flagged = {a.elder_id: a for a in _current_alerts(store, as_of) if a.status == "open"}
    cards = [
        elder_card(
            elder,
            store,
            as_of,
            alert_text=flagged[elder.id].suggested_action if elder.id in flagged else "",
        )
        for elder in store.elders
    ]
    return sorted(cards, key=lambda c: (not c.alert, -(c.days_since_visit or 0)))


def _record(store: Store, elder_id: str, as_of: date, alert: Alert | None) -> ElderRecord:
    elder = store.elder(elder_id)
    visits = store.visits_for(elder_id)
    baseline = compute_baseline(visits, as_of)
    return ElderRecord(
        id=elder.id,
        name=elder.name,
        age=_age(elder.dob, as_of),
        address=elder.address,
        conditions=elder.conditions,
        allergies=elder.allergies,
        medications=elder.medications,
        contacts=elder.contacts,
        communication_notes=elder.communication_notes,
        decision_maker=elder.decision_maker,
        baseline=baseline.worse_rate,
        visits_counted=baseline.visits_counted,
        timeline=timeline(visits, store.volunteer_names()),
        alert=alert,
    )


@router.get("/elders/{elder_id}", response_model=ElderRecord)
def person(elder_id: str, who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> ElderRecord:
    """C3. The living record: timeline, medications, baseline, contacts."""
    try:
        store.elder(elder_id)
    except StopIteration:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such person") from None
    alert = next((a for a in _current_alerts(store, as_of) if a.elder_id == elder_id), None)
    return _record(store, elder_id, as_of, alert)


@router.get("/elders/{elder_id}/handoff.pdf")
def handoff(
    elder_id: str,
    who: CoordinatorDep,
    store: StoreDep,
    as_of: AsOfDep,
    locale: LocaleDep,
) -> FileResponse:
    """C3's button. One page somebody can carry into a hospital.

    Written to the container's scratch space rather than kept: the sheet is generated from
    the record on demand, so a stale copy is worse than no copy.
    """
    try:
        store.elder(elder_id)
    except StopIteration:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such person") from None
    sheet = brief_agent.handoff(
        elder_id, store=store, as_of=as_of, locale=locale, out_dir=Path(tempfile.gettempdir())
    )
    return FileResponse(
        sheet.pdf_key,
        media_type="application/pdf",
        filename=f"{elder_id}-{as_of.isoformat()}.pdf",
    )


@router.get("/coverage", response_model=CoverageResponse)
def coverage(who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> CoverageResponse:
    """C4. The roster, and the imbalance made countable."""
    reading = assess(store, as_of)
    horizon = as_of + timedelta(days=14)
    upcoming = [s for s in store.shifts if as_of <= s.scheduled_at.date() <= horizon]
    upcoming.sort(key=lambda s: s.scheduled_at)
    return CoverageResponse(
        as_of=as_of,
        load=volunteer_load(store, reading.carrying, reading.quiet),
        shifts=[shift_card(s, store) for s in upcoming],
        open_count=sum(1 for s in upcoming if s.volunteer_id is None),
    )


@router.get("/report/weekly", response_model=WeeklyReport)
def weekly(who: CoordinatorDep, store: StoreDep, as_of: AsOfDep) -> WeeklyReport:
    """C5. What Monday's message says, without being asked."""
    start = as_of - timedelta(days=7)
    week = [v for v in store.visits if start <= v.started_at.date() <= as_of]
    seen = {v.elder_id for v in week}
    alerts = _current_alerts(store, as_of)
    reading = assess(store, as_of)

    counts: dict[str, int] = {}
    for visit in week:
        counts[visit.volunteer_id] = counts.get(visit.volunteer_id, 0) + 1
    names = store.volunteer_names()
    busiest = sorted(
        (
            {"id": vid, "name": names.get(vid, vid), "visits": n}
            for vid, n in counts.items()
        ),
        key=lambda r: -r["visits"],
    )[:5]

    return WeeklyReport(
        week_ending=as_of,
        visits_logged=len(week),
        people_seen=len(seen),
        people_missed=sorted(e.name for e in store.elders if e.id not in seen),
        alerts_opened=len(alerts),
        alerts_acknowledged=sum(1 for a in alerts if a.status != "open"),
        busiest=busiest,
        gaps_next_week=len(reading.openings) + len(reading.escalations),
    )
