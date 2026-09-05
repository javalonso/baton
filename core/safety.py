"""The one rule this product cannot afford to get wrong.

A network of volunteers is not qualified to diagnose anyone, and a model asked politely not
to diagnose will still do it every so often. The system prompts ask. This module checks.
Every agent that puts words in front of a human goes through here.

Two agents, two different questions:

* The watch agent describes a change it just noticed and must never name a cause. Any term
  in `FORBIDDEN` is a rejection, full stop.
* The brief agent reads a person's own record aloud, where "hypertension" is a fact somebody
  wrote down rather than a guess the model made. It may repeat what the record already says
  and nothing beyond it, which is what `names_a_new_condition` allows for.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: Words a note must not contain. The system prompt asks the model not to name a condition;
#: this checks. A prompt is a request, and the one rule this product cannot afford to get
#: wrong is worth enforcing where enforcement is possible.
#:
#: Matched at the start of a word, never inside one. Plain substring matching read "uti" out
#: of the middle of "rutina" and "routine" and rejected the sentence, which cost a retry
#: against a reasoning model every time a brief mentioned somebody's usual routine. A
#: guardrail that fires on ordinary words is one somebody eventually turns off.
FORBIDDEN = (
    "infection", "infección", "infeccion", "uti", "urinary", "urinaria",
    "dementia", "demencia", "alzheimer", "deshidrat", "dehydrat",
    "diagnos", "diagnóst", "prescri", "receta", "medicate", "medicar",
    "disease", "enfermedad", "syndrome", "síndrome",
)


#: Each term as a word-initial pattern, so stems still catch what they should: "infeccion"
#: matches "infecciones", "deshidrat" matches "deshidratada", "diagnos" matches "diagnosticar".
_PATTERNS = tuple((term, re.compile(rf"\b{re.escape(term)}", re.IGNORECASE)) for term in FORBIDDEN)


def names_a_condition(text: str) -> str | None:
    """The first forbidden term in `text`, or `None` if it is clean."""
    return next((term for term, pattern in _PATTERNS if pattern.search(text)), None)


def names_a_new_condition(text: str, known: Iterable[str]) -> str | None:
    """Same check, except a term the record already carries is not the model's invention.

    A handoff sheet that could not say the word on the person's own chart would be useless
    to the shift taking over. What it must not do is add a word nobody wrote down.
    """
    already_written = " ".join(known)
    return next(
        (
            term
            for term, pattern in _PATTERNS
            if pattern.search(text) and not pattern.search(already_written)
        ),
        None,
    )
