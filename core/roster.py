"""Who was supposed to be there, and who was.

The coordinator's second job, after worrying about twenty-four people, is chasing fourteen
volunteers about whether they went. It is the work that makes her the single point of
failure, and none of it needs her judgment until the last rung.

The ladder is from the spec, and it is the whole design:

| A shift went unlogged           | ask the volunteer. The coordinator sees nothing.   |
| Still unlogged the next day     | open it to the group on V4 for anyone to claim.    |
| Unclaimed, 12 hours to go       | now it is hers, because now somebody must decide.  |

Each rung is decided here, in arithmetic, and every rung below the last is answered without
her. A gap that gets filled by a neighbour at nine at night is a gap she never hears about,
and that silence is the product.

Nothing in this module reads an observation. The roster agent is told about schedules and
never about anybody's health, so a message asking the group to cover Thursday cannot leak
what Thursday's visit found. That is a structural guarantee rather than a promise, which is
the only kind worth making about a group chat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from core.models import Shift
from core.store import Store

#: A shift unlogged this long stops being one person's to explain and becomes the group's.
OPEN_AFTER_DAYS = 1

#: Closer than this to the hour, waiting for a volunteer to notice is itself a decision.
ESCALATE_WITHIN_HOURS = 12

#: How far ahead an unclaimed shift is worth mentioning. A gap three weeks out is real, but
#: asking about it tonight, and again tomorrow night, and again the night after, is how a
#: group chat learns to ignore this product.
PLAN_AHEAD_DAYS = 7

#: How far back "carrying the network" and "gone quiet" are measured.
LOAD_WINDOW_DAYS = 14

#: When the roster pass runs. Late enough that today's visits are in, early enough that
#: somebody can still answer a message.
RUN_AT = time(20, 0)


@dataclass
class Missed:
    """A shift with nothing behind it, and who it currently belongs to."""

    shift: Shift
    elder_name: str
    volunteer_name: str = ""
    days_late: int = 0


@dataclass
class Coverage:
    """One evening's reading of the schedule. No model has touched any of it."""

    as_of: date
    checked: int = 0
    nudges: list[Missed] = field(default_factory=list)
    openings: list[Missed] = field(default_factory=list)
    escalations: list[Missed] = field(default_factory=list)
    load: dict[str, int] = field(default_factory=dict)
    carrying: list[str] = field(default_factory=list)
    quiet: list[str] = field(default_factory=list)

    @property
    def quiet_evening(self) -> bool:
        """The desired outcome. Most evenings the schedule held and nobody hears from us."""
        return not (self.nudges or self.openings or self.escalations)


def _visited_days(store: Store) -> set[tuple[str, date]]:
    return {(v.elder_id, v.started_at.date()) for v in store.visits}


def assess(store: Store, as_of: date, now: datetime | None = None) -> Coverage:
    """Read the schedule against what actually happened. Deterministic, and tested."""
    now = now or datetime.combine(as_of, RUN_AT)
    visited = _visited_days(store)
    names = store.volunteer_names()
    coverage = Coverage(as_of=as_of, checked=len(store.shifts))

    for shift in store.shifts:
        if shift.status in ("logged", "claimed"):
            continue

        when = shift.scheduled_at
        elder_name = store.elder(shift.elder_id).name

        # Somebody with the shift, and the hour has passed.
        if shift.volunteer_id and when <= now:
            if (shift.elder_id, when.date()) in visited:
                continue  # they went, they just logged it against another row
            missed = Missed(
                shift=shift,
                elder_name=elder_name,
                volunteer_name=names.get(shift.volunteer_id, shift.volunteer_id),
                days_late=(as_of - when.date()).days,
            )
            if missed.days_late < OPEN_AFTER_DAYS:
                coverage.nudges.append(missed)
            else:
                coverage.openings.append(missed)
            continue

        # Nobody has it.
        if shift.volunteer_id is None:
            hours_away = (when - now).total_seconds() / 3600
            if hours_away < 0:
                continue  # already gone; the gap it left is somebody else's row now
            if hours_away > PLAN_AHEAD_DAYS * 24:
                continue  # real, but not tonight's question
            missed = Missed(shift=shift, elder_name=elder_name, days_late=0)
            if hours_away <= ESCALATE_WITHIN_HOURS:
                coverage.escalations.append(missed)
            else:
                coverage.openings.append(missed)

    _read_load(store, as_of, coverage)
    for bucket in (coverage.nudges, coverage.openings, coverage.escalations):
        bucket.sort(key=lambda m: m.shift.scheduled_at)
    return coverage


def _read_load(store: Store, as_of: date, coverage: Coverage) -> None:
    """Who is carrying this, and who stopped showing up.

    Both halves matter and only one is obvious. A network where one person does a third of
    the visits is a network that ends the day that person gets tired.
    """
    since = as_of - timedelta(days=LOAD_WINDOW_DAYS)
    counts = {v.id: 0 for v in store.volunteers if v.active}
    for visit in store.visits:
        if visit.started_at.date() >= since and visit.volunteer_id in counts:
            counts[visit.volunteer_id] += 1

    coverage.load = counts
    total = sum(counts.values())
    if not total:
        return

    names = store.volunteer_names()
    fair_share = total / max(len(counts), 1)
    coverage.carrying = [
        names[vid] for vid, n in counts.items() if n >= fair_share * 2
    ]
    coverage.quiet = [names[vid] for vid, n in counts.items() if n == 0]
