"""The closed observation vocabulary.

Free text is not comparable across days. A closed vocabulary is what makes change
detection possible at all, so this list is deliberately small and deliberately fixed.
Adding a category is a product decision, not an implementation detail.
"""

from enum import StrEnum


class Category(StrEnum):
    FOOD = "food"
    FLUIDS = "fluids"
    SLEEP = "sleep"
    MOOD = "mood"
    ORIENTATION = "orientation"
    MOBILITY = "mobility"
    MEDICATION = "medication"
    PAIN = "pain"
    SKIN = "skin"
    SOCIAL = "social"
    HOUSEHOLD = "household"
    INCIDENT = "incident"
    TASK = "task"


class Trend(StrEnum):
    """How an observation compares to this person's own normal, as heard in the note."""

    BETTER = "better"
    USUAL = "usual"
    WORSE = "worse"
    UNCLEAR = "unclear"


class Confidence(StrEnum):
    """Stated in words, never as a decimal. See docs/design-principles.md."""

    CLEAR = "clear"
    CONFIRM = "confirm"


#: Categories that make an alert urgent when they are part of a pattern break.
#: Sudden confusion is the signal that matters most in older adults, and it is the one
#: a volunteer is least likely to think of as medical.
URGENT_CATEGORIES = frozenset({Category.ORIENTATION, Category.INCIDENT})

#: Things that bypass every rule and escalate immediately.
IMMEDIATE_ESCALATION = ("fall", "bleeding", "chest pain", "unresponsive")
