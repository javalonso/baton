"""Writes, against the backend that needs no AWS.

The contract these tests pin down is the one both backends promise, so
`tests/test_dynamo.py` runs the same expectations against the real table.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta

import pytest

from core.models import Shift, Visit
from core.store import DEFAULT_PATH, JsonStore, ShiftAlreadyClaimed


@pytest.fixture
def store(tmp_path) -> JsonStore:
    path = tmp_path / "world.json"
    shutil.copy(DEFAULT_PATH, path)
    return JsonStore(path, writable=True)


def _visit(store: JsonStore, shift_id: str | None = None) -> Visit:
    elder = store.elders[0]
    return Visit(
        id="visit-new",
        shift_id=shift_id,
        elder_id=elder.id,
        volunteer_id=store.volunteers[0].id,
        started_at=datetime(2026, 9, 14, 10, 0),
        transcript="She was up and dressed, asked about the garden.",
    )


def test_a_visit_survives_being_written(store: JsonStore, tmp_path):
    store.add_visit(_visit(store))
    reopened = JsonStore(tmp_path / "world.json")
    assert any(v.id == "visit-new" for v in reopened.visits)


def test_a_logged_visit_closes_its_shift(store: JsonStore):
    open_shift = next(s for s in store.shifts if s.status != "logged")
    store.add_visit(_visit(store, shift_id=open_shift.id))
    assert store.shift(open_shift.id).status == "logged"


def test_a_visit_shows_up_under_the_person_in_order(store: JsonStore):
    elder = store.elders[0]
    before = store.visits_for(elder.id)
    store.add_visit(_visit(store))
    after = store.visits_for(elder.id)
    assert len(after) == len(before) + 1
    assert after == sorted(after, key=lambda v: v.started_at)


def test_an_unclaimed_shift_can_be_claimed(store: JsonStore):
    shift = Shift(
        id="shift-open-1",
        org_id=store.org_id,
        elder_id=store.elders[0].id,
        scheduled_at=datetime(2026, 9, 16, 9, 0),
        status="open",
    )
    store.save_shift(shift)
    claimed = store.claim_shift(shift.id, store.volunteers[3].id)
    assert claimed.volunteer_id == store.volunteers[3].id
    assert claimed.status == "claimed"


def test_the_second_volunteer_to_claim_is_told_no(store: JsonStore):
    """Two people press the same button. Exactly one of them can be going."""
    shift = Shift(
        id="shift-open-2",
        org_id=store.org_id,
        elder_id=store.elders[1].id,
        scheduled_at=datetime(2026, 9, 16, 9, 0),
        status="open",
    )
    store.save_shift(shift)
    store.claim_shift(shift.id, store.volunteers[3].id)
    with pytest.raises(ShiftAlreadyClaimed):
        store.claim_shift(shift.id, store.volunteers[4].id)
    assert store.shift(shift.id).volunteer_id == store.volunteers[3].id


def test_claiming_twice_yourself_is_not_an_error(store: JsonStore):
    """A volunteer on a flaky connection presses claim twice. That is not a conflict."""
    shift = Shift(
        id="shift-open-3",
        org_id=store.org_id,
        elder_id=store.elders[2].id,
        scheduled_at=datetime(2026, 9, 16, 9, 0),
        status="open",
    )
    store.save_shift(shift)
    store.claim_shift(shift.id, store.volunteers[5].id)
    assert store.claim_shift(shift.id, store.volunteers[5].id).volunteer_id == store.volunteers[5].id


def test_an_alert_can_be_acknowledged(store: JsonStore):
    from agents.watch import sweep
    from datetime import date

    found = sweep(store, date.fromisoformat(store.generated_for))
    alert = next(iter(found.values()))
    store.save_alert(alert)
    updated = store.set_alert_status(alert.id, "acknowledged", by="coordinator")
    assert updated.status == "acknowledged"
    assert updated.acknowledged_by == "coordinator"


def test_the_seed_file_is_never_written_to():
    """A read-only store is the default, so a demo run cannot rewrite the committed dataset."""
    before = DEFAULT_PATH.read_text(encoding="utf-8")
    readonly = JsonStore()
    readonly.add_visit(_visit(readonly))
    assert DEFAULT_PATH.read_text(encoding="utf-8") == before
    assert json.loads(before)["organization"]["id"] == "org-san-miguel"


def test_shift_times_round_trip_through_a_write(store: JsonStore, tmp_path):
    shift = Shift(
        id="shift-tz-1",
        org_id=store.org_id,
        elder_id=store.elders[0].id,
        scheduled_at=datetime(2026, 9, 16, 9, 0) + timedelta(minutes=30),
        status="open",
    )
    store.save_shift(shift)
    reopened = JsonStore(tmp_path / "world.json")
    assert reopened.shift("shift-tz-1").scheduled_at == shift.scheduled_at
