"""The one rule the product cannot afford to get wrong, tested.

The system prompt asks the model not to name a condition. This checks that asking is not
the only thing standing between a volunteer network and a diagnosis it is not qualified to
make.
"""

from __future__ import annotations

import pytest

from agents.watch import FORBIDDEN, _names_a_condition


@pytest.mark.parametrize(
    "note",
    [
        "Lleva tres días fuera de su patrón. Vale la pena que alguien la valore.",
        "Off her pattern for three days. Worth having someone assess her.",
        "Menos líquidos y más confusión. Conviene una valoración en persona.",
    ],
)
def test_safe_notes_pass(note: str):
    assert _names_a_condition(note) is None


@pytest.mark.parametrize(
    "note",
    [
        "Parece una infección urinaria.",
        "This looks like a urinary tract infection.",
        "Probably dehydration, give her more water.",
        "Signs of early dementia.",
        "Suspected UTI, needs antibiotics.",
    ],
)
def test_notes_that_name_a_condition_are_rejected(note: str):
    assert _names_a_condition(note) is not None


def test_the_check_covers_both_product_languages():
    """A guardrail that only works in English is not a guardrail for this product."""
    spanish = {"infección", "demencia", "enfermedad", "receta", "diagnóst"}
    assert spanish & set(FORBIDDEN), "the Spanish side of the vocabulary is missing"
