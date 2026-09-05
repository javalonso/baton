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
    from datetime import date

    from agents.watch import sweep

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


def test_a_brief_is_written_once_a_day_and_read_after_that(store: JsonStore, monkeypatch):
    """Eighteen seconds of a reasoning model, per person per day per language. Once."""
    from datetime import date

    from agents import brief as brief_agent
    from core.models import Brief

    calls = []

    def fake_build_agent(store_, elder_id, as_of, locale):
        calls.append(elder_id)
        written = [
            Brief(
                elder_id=elder_id,
                locale=locale,
                since_last_visit="Ha comido menos.",
                watch_for="Si sigue asi.",
                how_to_be_with_them="Despacio.",
                written_by_model=True,
            )
        ]

        class _Agent:
            def __call__(self, _prompt):
                return ""

        return _Agent(), written

    monkeypatch.setattr(brief_agent, "build_agent", fake_build_agent)
    as_of = date.fromisoformat(store.generated_for)
    elder_id = store.elders[0].id

    first = brief_agent.write(elder_id, store=store, as_of=as_of, locale="es")
    second = brief_agent.write(elder_id, store=store, as_of=as_of, locale="es")
    assert calls == [elder_id]
    assert second.since_last_visit == first.since_last_visit

    brief_agent.write(elder_id, store=store, as_of=as_of, locale="en")
    assert len(calls) == 2, "a different language is a different brief"

    brief_agent.write(elder_id, store=store, as_of=as_of, locale="es", refresh=True)
    assert len(calls) == 3, "refresh has to actually refresh"


def test_a_failed_brief_is_never_cached(store: JsonStore, monkeypatch):
    """The fallback is what a volunteer gets on a bad minute. Caching it makes it a bad day."""
    from datetime import date

    from agents import brief as brief_agent

    def exploding_build_agent(store_, elder_id, as_of, locale):
        class _Agent:
            def __call__(self, _prompt):
                raise RuntimeError("bedrock is having a day")

        return _Agent(), []

    monkeypatch.setattr(brief_agent, "build_agent", exploding_build_agent)
    as_of = date.fromisoformat(store.generated_for)
    elder_id = store.elders[0].id

    fallback = brief_agent.write(elder_id, store=store, as_of=as_of, locale="es")
    assert fallback.written_by_model is False
    assert store.get_brief(elder_id, as_of, "es") is None
