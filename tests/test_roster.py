"""The escalation ladder, tested rung by rung.

Every one of these runs offline. Which rung a gap sits on is arithmetic, and the whole point
of putting it in `core.roster` rather than in a prompt is that it can be pinned down here.

The rung that matters most is the one that stays quiet. Three of the four gaps in the seed
are answered without the coordinator ever hearing about them, and if that ever stops being
true the product is just another notification.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from agents.roster import plain_messages
from core.models import Shift
from core.roster import ESCALATE_WITHIN_HOURS, assess
from core.store import JsonStore, Store

AS_OF = date(2026, 9, 14)
TONIGHT = datetime(2026, 9, 14, 20, 0)


@pytest.fixture(scope="module")
def store() -> Store:
    return JsonStore()


@pytest.fixture(scope="module")
def coverage(store: Store):
    return assess(store, AS_OF, TONIGHT)


def test_a_shift_unlogged_today_belongs_to_the_volunteer(coverage):
    assert len(coverage.nudges) == 1
    missed = coverage.nudges[0]
    assert missed.days_late == 0
    assert missed.volunteer_name, "somebody has this shift; the message goes to them"


def test_a_shift_still_unlogged_the_next_day_belongs_to_the_group(coverage):
    stale = [m for m in coverage.openings if m.days_late >= 1]
    assert stale, "asking the same person a second time is not a plan"
    assert all(m.volunteer_name for m in stale)


def test_unclaimed_shifts_further_out_stay_with_the_group(coverage):
    unassigned = [m for m in coverage.openings if not m.volunteer_name]
    assert len(unassigned) == 3
    assert all(m.shift.scheduled_at > TONIGHT for m in unassigned)


def test_only_the_last_rung_reaches_the_coordinator(coverage):
    assert len(coverage.escalations) == 1
    hours = (coverage.escalations[0].shift.scheduled_at - TONIGHT).total_seconds() / 3600
    assert 0 <= hours <= ESCALATE_WITHIN_HOURS


def test_the_ladder_answers_most_of_itself_without_her(coverage):
    handled = len(coverage.nudges) + len(coverage.openings)
    assert handled > len(coverage.escalations), (
        "if most gaps reach the coordinator, this is a notification system with extra steps"
    )


def test_an_evening_when_the_schedule_held_is_silent(store: Store):
    """The common case, and the desired one."""
    quiet = assess(store, AS_OF - timedelta(days=20), datetime(2026, 8, 25, 20, 0))
    assert quiet.quiet_evening
    assert plain_messages(quiet) == []


def test_a_gap_the_hour_has_passed_is_not_reported_as_coverable(store: Store):
    """An unclaimed shift whose time has gone is history, not something to staff tonight."""
    past = Shift(
        id="shift-gone",
        org_id="org-san-miguel",
        elder_id="elder-05",
        volunteer_id=None,
        scheduled_at=datetime(2026, 9, 13, 9, 0),
        status="open",
    )
    store.shifts.append(past)
    try:
        found = assess(store, AS_OF, TONIGHT)
        assert all(m.shift.id != "shift-gone" for m in found.openings + found.escalations)
    finally:
        store.shifts.remove(past)


def test_load_shows_who_is_carrying_it_and_who_stopped(coverage):
    """Scenario 3 of the dataset, as a number rather than an impression."""
    assert coverage.carrying, "one person doing double a fair share should be visible"
    assert coverage.quiet, "volunteers who have gone silent should be visible too"
    assert max(coverage.load.values()) > 2 * min(
        v for v in coverage.load.values() if v
    )


@pytest.mark.parametrize("locale", ["es", "en"])
def test_the_fallback_writes_to_every_rung(coverage, locale: str):
    messages = plain_messages(coverage, locale)
    audiences = {m.to for m in messages}

    assert audiences == {"volunteer", "group", "coordinator"}
    assert all(m.body.strip() for m in messages)
    assert all(m.written_by_model is False for m in messages)
    assert len([m for m in messages if m.to == "group"]) == 1, "the group gets one message"


def test_the_group_message_names_every_open_shift(coverage):
    group = next(m for m in plain_messages(coverage, "es") if m.to == "group")
    for missed in coverage.openings:
        assert missed.elder_name in group.body


def test_no_message_carries_anything_about_anyones_health(coverage):
    """Structural, not aspirational: the agent is never given an observation to leak."""
    from core.safety import names_a_condition

    for message in plain_messages(coverage, "es") + plain_messages(coverage, "en"):
        assert names_a_condition(message.body) is None
