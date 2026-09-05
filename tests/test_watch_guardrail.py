"""The one rule the product cannot afford to get wrong, tested.

The system prompt asks the model not to name a condition. This checks that asking is not
the only thing standing between a volunteer network and a diagnosis it is not qualified to
make.
"""

from __future__ import annotations

import pytest

from agents.watch import FORBIDDEN, _names_a_condition
from core.safety import names_a_condition


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


@pytest.mark.parametrize(
    "innocent",
    [
        "Todo dentro de su rutina de siempre.",
        "Her routine was unchanged.",
        "Le costo levantarse de la silla, como es habitual.",
        "Comio menos que otros dias.",
    ],
)
def test_ordinary_words_are_not_conditions(innocent: str):
    """`uti` lives inside `rutina` and `routine`. Substring matching rejected both.

    Every false rejection is a retry against a reasoning model, and a guardrail that fires
    on ordinary words is one somebody eventually turns off.
    """
    assert names_a_condition(innocent) is None


@pytest.mark.parametrize(
    "named",
    [
        "Parece una infeccion urinaria.",
        "Podria ser deshidratacion.",
        "Signs of a UTI.",
        "Esto sugiere demencia.",
        "Habria que medicarla hoy.",
        "Sospecho una enfermedad renal.",
    ],
)
def test_a_named_condition_is_still_caught(named: str):
    """Stems have to keep working: infecciones, deshidratada, diagnosticar."""
    assert names_a_condition(named) is not None
