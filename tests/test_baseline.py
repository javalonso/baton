"""Tests for change detection.

The pair that matters is Rafael and Dolores. Their last eight days are the same: sleeping
badly, low mood. One gets an alert and the other does not, and no threshold could tell them
apart — only their own histories can. If this file ever passes for both, or fails for both,
the product's central claim has stopped being true.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.baseline import compute_baseline, detect, suggest
from core.store import JsonStore, Store
from core.vocabulary import Category

AS_OF = date(2026, 9, 14)


@pytest.fixture(scope="module")
def store() -> Store:
    return JsonStore()


def _detect(store: Store, elder_id: str):
    return detect(elder_id, store.visits_for(elder_id), AS_OF, store.volunteer_names())


def test_acute_change_opens_an_urgent_alert(store: Store):
    """Carmen: fluids, food and orientation all break over three days."""
    alert = _detect(store, "elder-01")

    assert alert is not None, "an acute multi-category break must be caught"
    assert alert.severity == "urgent"
    assert Category.ORIENTATION in alert.categories
    assert alert.days_off_pattern >= 2
    assert alert.evidence, "an alert without evidence is an assertion, not a finding"
    assert all(e.quote.strip() for e in alert.evidence)


def test_slow_drift_is_caught_without_any_threshold(store: Store):
    """Rafael: sleep and mood drift for eight days. Nothing crosses a number."""
    alert = _detect(store, "elder-02")

    assert alert is not None, "a slow drift must still be caught"
    assert alert.severity == "attention", "no orientation involved, so this is not urgent"
    assert {Category.SLEEP, Category.MOOD} <= set(alert.categories)


def test_the_same_days_are_not_news_for_someone_they_are_normal_for(store: Store):
    """Dolores: the same last eight days as Rafael, but this is simply how she is.

    This is the test the whole product rests on.
    """
    alert = _detect(store, "elder-03")

    assert alert is None, (
        "chronic sleep and mood problems are this person's baseline, not a change in her"
    )


def test_rafael_and_dolores_look_identical_recently(store: Store):
    """Guard the premise of the test above: if their recent data diverges, it proves nothing."""
    recent = {}
    for elder_id in ("elder-02", "elder-03"):
        visits = [v for v in store.visits_for(elder_id) if (AS_OF - v.started_at.date()).days <= 7]
        recent[elder_id] = {o.category for v in visits for o in v.observations if o.trend == "worse"}

    assert recent["elder-02"] == recent["elder-03"], (
        "the two people must be indistinguishable from recent data alone"
    )


def test_baselines_are_what_tell_them_apart(store: Store):
    """Same recent picture, opposite histories."""
    rafael = compute_baseline(store.visits_for("elder-02"), date(2026, 9, 6))
    dolores = compute_baseline(store.visits_for("elder-03"), date(2026, 9, 6))

    assert rafael.worse_rate.get("sleep", 0) < 0.34
    assert dolores.worse_rate.get("sleep", 0) > 0.34


def test_most_people_generate_nothing(store: Store):
    """The escalation rules exist to keep this quiet. A noisy agent is a failed agent."""
    alerts = [_detect(store, e.id) for e in store.elders]
    opened = [a for a in alerts if a is not None]

    assert len(opened) <= 4, f"{len(opened)} alerts across 24 people is a notification app"


def test_suggestions_never_name_a_condition():
    """The medical-safety posture, enforced rather than promised."""
    forbidden = ("infection", "uti", "dementia", "diagnos", "prescri", "dehydrated", "disease")

    for categories in (
        [Category.ORIENTATION, Category.FLUIDS],
        [Category.FLUIDS, Category.FOOD],
        [Category.SLEEP, Category.MOOD],
    ):
        for urgent in (True, False):
            text = suggest(categories, 3, urgent).lower()
            for term in forbidden:
                assert term not in text, f"suggestion named {term!r}: {text}"
            assert "assess" in text or "look" in text, "a suggestion must recommend a human act"
