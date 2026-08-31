"""Baseline and change detection.

The claim this module has to earn: Baton notices when a person stops being like
themselves, not when they cross a number someone picked. There is no model here and no
population average — only this person's own history.

Two definitions carry the whole design:

* A person's **baseline** is how often each category ran "worse" over a rolling window.
  Someone who sleeps badly most weeks has a high baseline for sleep, so a bad night is not
  news about them.
* A category **deviates** on a day when it ran worse *and* that is not usual for this
  person. A pattern break is two or more categories deviating on two or more consecutive
  days — one bad day is not a signal, and one bad category is not a pattern.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from core.models import Alert, AlertEvidence, Baseline, Visit
from core.vocabulary import IMMEDIATE_ESCALATION, URGENT_CATEGORIES, Category, Trend

#: Above this share of "worse" days, a category is simply how this person is.
USUAL_THRESHOLD = 0.34

#: A pattern break needs at least this many categories deviating on the same day.
MIN_CATEGORIES = 2

#: ...on at least this many consecutive days.
MIN_DAYS = 2

#: How far back a deviation is compared against.
WINDOW_DAYS = 21

#: The recent stretch being judged. The baseline is computed *before* this period, never
#: including it. A rolling window that contains the change absorbs it: eight days of bad
#: sleep quietly become "how he sleeps", and the drift makes itself invisible.
EVALUATION_DAYS = 10


def compute_baseline(
    visits: list[Visit],
    as_of: date,
    window_days: int = WINDOW_DAYS,
    exclude_recent_days: int = EVALUATION_DAYS,
) -> Baseline:
    """How often each category ran worse for this person, before the period being judged.

    The window stops `exclude_recent_days` short of `as_of`. This is the difference between
    catching a slow drift and never seeing one.
    """
    if not visits:
        return Baseline(elder_id="", window_days=window_days)

    end = as_of - timedelta(days=exclude_recent_days)
    start = end - timedelta(days=window_days)
    in_window = [v for v in visits if start <= v.started_at.date() < end]

    worse: dict[str, int] = defaultdict(int)
    seen: dict[str, int] = defaultdict(int)
    for visit in in_window:
        categories_today = {o.category for o in visit.observations}
        for category in categories_today:
            seen[category.value] += 1
        for category in {o.category for o in visit.observations if o.trend is Trend.WORSE}:
            worse[category.value] += 1

    return Baseline(
        elder_id=visits[0].elder_id,
        window_days=window_days,
        worse_rate={c: round(worse[c] / seen[c], 3) for c in seen},
        visits_counted=len(in_window),
        updated_at=datetime.combine(as_of, datetime.min.time()),
    )


def _deviating_categories(visit: Visit, baseline: Baseline) -> set[Category]:
    """Categories that ran worse on this visit and are not usually worse for this person."""
    return {
        o.category
        for o in visit.observations
        if o.trend is Trend.WORSE
        and baseline.worse_rate.get(o.category.value, 0.0) <= USUAL_THRESHOLD
    }


def _by_day(visits: list[Visit]) -> dict[date, list[Visit]]:
    days: dict[date, list[Visit]] = defaultdict(list)
    for visit in visits:
        days[visit.started_at.date()].append(visit)
    return days


def find_emergency(visits: list[Visit]) -> Visit | None:
    """A fall, bleeding, chest pain. These bypass every rule in this module."""
    for visit in sorted(visits, key=lambda v: v.started_at, reverse=True):
        haystack = " ".join(
            f"{o.summary} {o.quote}".lower()
            for o in visit.observations
            if o.category is Category.INCIDENT
        )
        if any(term in haystack for term in IMMEDIATE_ESCALATION):
            return visit
    return None


def detect(
    elder_id: str,
    visits: list[Visit],
    as_of: date,
    volunteer_names: dict[str, str] | None = None,
) -> Alert | None:
    """Run the daily check for one person. Returns an alert, or nothing at all.

    Returning nothing is the common case and the desired one. The escalation rules exist
    to keep this function quiet.
    """
    volunteer_names = volunteer_names or {}
    baseline = compute_baseline(visits, as_of)
    days = _by_day(visits)

    # Walk backwards through the evaluation period, counting consecutive visits that broke.
    streak: list[tuple[date, set[Category]]] = []
    for offset in range(0, EVALUATION_DAYS):
        day = as_of - timedelta(days=offset)
        if day not in days:
            # Nobody visited. That is silence, not evidence — it neither extends a streak
            # nor ends one. Unlogged visits are the roster agent's problem, not this one's.
            continue
        deviating: set[Category] = set()
        for visit in days[day]:
            deviating |= _deviating_categories(visit, baseline)
        if len(deviating) >= MIN_CATEGORIES:
            streak.append((day, deviating))
        else:
            break

    if len(streak) < MIN_DAYS:
        return None

    categories = sorted({c for _, cats in streak for c in cats}, key=lambda c: c.value)
    urgent = bool(set(categories) & URGENT_CATEGORIES)

    evidence: list[AlertEvidence] = []
    for day, cats in streak:
        for visit in days[day]:
            for observation in visit.observations:
                if observation.category in cats and observation.trend is Trend.WORSE:
                    evidence.append(
                        AlertEvidence(
                            quote=observation.quote,
                            volunteer_name=volunteer_names.get(
                                visit.volunteer_id, visit.volunteer_id
                            ),
                            observed_at=visit.started_at,
                            category=observation.category,
                        )
                    )

    return Alert(
        id=f"alert-{elder_id}-{as_of.isoformat()}",
        elder_id=elder_id,
        severity="urgent" if urgent else "attention",
        days_off_pattern=len(streak),
        categories=categories,
        evidence=evidence[:6],
        suggested_action=suggest(categories, len(streak), urgent),
        opened_at=datetime.combine(as_of, datetime.min.time()),
    )


def suggest(categories: list[Category], days: int, urgent: bool) -> str:
    """Phrase the recommendation.

    This function is the whole medical-safety posture of the product in one place. It
    describes what changed and recommends that a person be assessed. It must never name a
    condition, and it must never tell anyone what to do to a patient.

    Phrasing stays free of pronouns. The record does not store anyone's gender and has no
    business guessing it from a name.
    """
    named = ", ".join(c.value for c in categories)
    lead = f"Off the usual pattern for {days} days across {named}."

    if urgent and Category.ORIENTATION in categories:
        return (
            f"{lead} In older adults a sudden change in orientation is often the first sign "
            "of something treatable rather than a sign of decline. Worth arranging an "
            "assessment today."
        )
    if Category.FLUIDS in categories or Category.FOOD in categories:
        return (
            f"{lead} Eating and drinking less can precede other problems and is easy to miss "
            "day to day. Worth checking in, and arranging an assessment if it continues."
        )
    return f"{lead} Worth a closer look on the next visit, and an assessment if it continues."
