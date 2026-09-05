"""What the brief agent rests on, tested without a model.

Everything here runs offline on purpose. The parts that must be right when Bedrock is slow,
throttled or simply wrong are the parts that never needed a model: the facts, the fallback,
and the guardrail that decides whether a sentence is allowed on the page.
"""

from __future__ import annotations

from datetime import date

import pytest

from agents.brief import facts_for, plain_brief
from core.handoff import render
from core.safety import names_a_condition, names_a_new_condition
from core.store import JsonStore, Store

AS_OF = date(2026, 9, 14)
CARMEN = "elder-01"  # acute: three days, fluids, orientation, food
DOLORES = "elder-03"  # the control: always been this way, so it is not news about her


@pytest.fixture(scope="module")
def store() -> Store:
    return JsonStore()


def test_facts_carry_the_record_and_the_comparison(store: Store):
    facts = facts_for(store, CARMEN, AS_OF)

    assert facts["off_pattern"] is True
    assert "orientation" in facts["categories_off"]
    assert facts["on_the_record"]["medications"], "a handoff sheet with no medications is a blank"
    assert facts["on_the_record"]["how_to_communicate"]
    assert facts["days_since_last_visit"] is not None


def test_the_control_case_is_not_reported_as_a_change(store: Store):
    """Dolores looks like Rafael for eight days. Only her own history tells them apart."""
    assert facts_for(store, DOLORES, AS_OF)["off_pattern"] is False


def test_recent_visits_carry_quotes_a_reader_can_check(store: Store):
    quotes = [q for v in facts_for(store, CARMEN, AS_OF)["recent_visits"] for q in v["quotes"]]
    assert quotes, "nothing is asserted about a person without the words that produced it"
    assert all(q["quote"].strip() for q in quotes)


@pytest.mark.parametrize("locale", ["es", "en"])
def test_the_fallback_brief_is_a_real_briefing(store: Store, locale: str):
    """A model having a bad day must not leave a volunteer knocking blind."""
    elder = store.elder(CARMEN)
    brief = plain_brief(facts_for(store, CARMEN, AS_OF), elder, locale)

    assert brief.written_by_model is False
    assert brief.since_last_visit.strip()
    assert brief.watch_for.strip()
    assert brief.how_to_be_with_them.strip()
    assert brief.locale == locale


def test_the_fallback_says_plainly_when_nothing_changed(store: Store):
    elder = store.elder(DOLORES)
    brief = plain_brief(facts_for(store, DOLORES, AS_OF), elder, "en")
    assert "Nothing has changed" in brief.since_last_visit


def test_the_brief_may_repeat_the_chart_but_not_add_to_it():
    """The difference between the two agents' guardrails, stated as a test.

    The watch agent describes a change and may never name a cause. The brief agent reads a
    person's own record aloud, where the same word is a fact somebody wrote down.
    """
    on_the_chart = ["dementia", "hypertension", "Losartán 50 mg"]

    reads_the_chart = "Her dementia is on the record, so repeat things without impatience."
    assert names_a_condition(reads_the_chart) is not None, "the strict check objects, correctly"
    assert names_a_new_condition(reads_the_chart, on_the_chart) is None, (
        "a word already on the chart is a fact somebody wrote down, not the model's guess"
    )

    invents = "The confusion is probably a urinary tract infection."
    assert names_a_new_condition(invents, on_the_chart) is not None
    assert names_a_new_condition("Signs of early dementia are appearing.", []) is not None


def test_the_sheet_is_one_page(store: Store, tmp_path):
    """One page is the product, not a formatting preference.

    A sheet that spills onto a second page loses whatever was on it, because the reader is
    standing in a hallway holding one sheet of paper.
    """
    elder = store.elder(CARMEN)
    brief = plain_brief(facts_for(store, CARMEN, AS_OF), elder, "es")

    path = render(elder, brief, tmp_path / "carmen.pdf", as_of=AS_OF, locale="es")
    raw = path.read_bytes()

    assert raw.startswith(b"%PDF")
    assert b"/Count 1" in raw, "the handoff sheet grew a second page"


def test_a_record_that_will_not_fit_is_cut_rather_than_spilled(store: Store, tmp_path):
    elder = store.elder(CARMEN).model_copy(deep=True)
    elder.communication_notes = "Habla despacio. " * 400
    elder.conditions = [f"condition {i}" for i in range(40)]

    brief = plain_brief(facts_for(store, CARMEN, AS_OF), elder, "es")
    brief.since_last_visit = "Se salió de su patrón. " * 200

    path = render(elder, brief, tmp_path / "overflow.pdf", as_of=AS_OF, locale="es")
    assert b"/Count 1" in path.read_bytes()
