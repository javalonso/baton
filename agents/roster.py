"""Roster agent: the chasing nobody should have to do.

Every evening this reads the schedule against what actually happened and answers as much of
it as it can without the coordinator. Which rung of the ladder each gap sits on is decided in
`core.roster`, in arithmetic, before the model sees anything. The model writes messages.

Three rungs, three audiences, and the order is the point:

* A shift went unlogged today. That is one message to one person, and she never hears about it.
* Still nothing the next day. Now it goes to the group, because asking the same person twice
  is not a plan.
* Twelve hours out and still unclaimed. Now it is hers, because now somebody has to decide.

Two things this agent structurally cannot do. It never receives an observation, so a message
asking the group to cover Thursday cannot leak what Tuesday's visit found. And
`tell_coordinator` refuses to write anything when nothing reached the top rung, so the model
cannot promote a problem by being helpful about it. Interrupting her is the expensive act in
this product, and the code decides when it happens.
"""

from __future__ import annotations

from datetime import date, datetime

from strands import Agent, tool

from core.bedrock import intake_model
from core.models import Message
from core.roster import Coverage, Missed, assess
from core.safety import names_a_condition
from core.store import Store, open_store

SYSTEM_PROMPT = """\
You keep the schedule of a neighbourhood care network honest. Fourteen volunteers, one
part-time coordinator, and a rota that only works because somebody chases it. That somebody
is you now.

Call `schedule` first. Everything is already sorted into who each gap belongs to. Do not
re-sort it, do not decide a gap is urgent because it feels urgent, and do not move anything up.

Then write, in this order:

* `nudge_volunteer` once per person in `nudges`. Short and friendly. They probably went and
  forgot to record it, and that is the most likely thing by far. Ask, do not accuse, and give
  them the easy answer: send the voice note now, or say you could not make it.
* `ask_group` once, if there is anything in `openings`. One message covering all of them, with
  the day and time of each. Ask, do not assign. Nobody in this group is paid.
* `tell_coordinator` once, only if `escalations` is not empty. State which shift, when it is,
  and that nobody has claimed it. She is the one who decides what happens next, so give her
  the facts and stop.

Say nothing about anyone's health. You have not been told anything about it, and a message
about Thursday's rota is not the place. Use first names for volunteers, full names for the
people they visit.

If the coverage comes back empty, write nothing at all and say so in one line. Most evenings
should be that evening.

Write in the language you are told to.
"""

PLAIN = {
    "es": {
        "nudge": (
            "Hola {volunteer}, no quedó registrada la visita a {elder} de hoy a las {time}. "
            "Si fuiste, mándanos la nota de voz cuando puedas. Si no pudiste, dinos y la abrimos "
            "al grupo."
        ),
        "group": "Nos faltan manos esta semana:\n{lines}\n¿Alguien puede? Con responder aquí basta.",
        "line": "· {elder}, {when}",
        "coordinator": (
            "{elder}, {when}: nadie ha tomado el turno y faltan menos de 12 horas. "
            "Ya se preguntó al grupo."
        ),
        "quiet": "Todo cubierto hoy. Nadie necesita nada.",
    },
    "en": {
        "nudge": (
            "Hi {volunteer}, today's visit to {elder} at {time} did not get logged. If you went, "
            "send the voice note whenever you can. If you could not make it, say so and we will "
            "open it to the group."
        ),
        "group": "We are short this week:\n{lines}\nCan anyone cover? Replying here is enough.",
        "line": "· {elder}, {when}",
        "coordinator": (
            "{elder}, {when}: nobody has claimed this and it is less than 12 hours away. "
            "The group has already been asked."
        ),
        "quiet": "Everything is covered today. Nobody needs anything.",
    },
}


def _when(missed: Missed, locale: str) -> str:
    stamp = missed.shift.scheduled_at
    return stamp.strftime("%a %d %H:%M") if locale == "en" else stamp.strftime("%d/%m %H:%M")


def plain_messages(coverage: Coverage, locale: str = "es") -> list[Message]:
    """What gets sent when the model sends nothing.

    A rota that only gets chased when Bedrock is up is not a rota that gets chased.
    """
    words = PLAIN.get(locale, PLAIN["es"])
    messages: list[Message] = []

    for missed in coverage.nudges:
        messages.append(
            Message(
                to="volunteer",
                recipient=missed.volunteer_name,
                about_shift=missed.shift.id,
                written_by_model=False,
                body=words["nudge"].format(
                    volunteer=missed.volunteer_name.split()[0],
                    elder=missed.elder_name,
                    time=missed.shift.scheduled_at.strftime("%H:%M"),
                ),
            )
        )

    if coverage.openings:
        lines = "\n".join(
            words["line"].format(elder=m.elder_name, when=_when(m, locale))
            for m in coverage.openings
        )
        messages.append(
            Message(
                to="group", body=words["group"].format(lines=lines), written_by_model=False
            )
        )

    for missed in coverage.escalations:
        messages.append(
            Message(
                to="coordinator",
                about_shift=missed.shift.id,
                written_by_model=False,
                body=words["coordinator"].format(
                    elder=missed.elder_name, when=_when(missed, locale)
                ),
            )
        )

    return messages


def build_agent(coverage: Coverage, locale: str = "es") -> tuple[Agent, list[Message]]:
    """The agent, three tools shaped like the ladder, and the outbox it fills."""
    outbox: list[Message] = []

    def _clean(body: str) -> str | None:
        named = names_a_condition(body)
        if named:
            return (
                f"Rejected: the message contains {named!r}. Nothing was sent. This is a message "
                "about the schedule, and you have not been told anything about anyone's health. "
                "Call this tool again without it."
            )
        return None

    @tool
    def schedule() -> dict:
        """Tonight's reading of the schedule, already sorted by who each gap belongs to."""
        return {
            "shifts_checked": coverage.checked,
            "nudges": [
                {
                    "shift_id": m.shift.id,
                    "volunteer": m.volunteer_name,
                    "elder": m.elder_name,
                    "scheduled_at": m.shift.scheduled_at.strftime("%Y-%m-%d %H:%M"),
                }
                for m in coverage.nudges
            ],
            "openings": [
                {
                    "shift_id": m.shift.id,
                    "elder": m.elder_name,
                    "scheduled_at": m.shift.scheduled_at.strftime("%Y-%m-%d %H:%M"),
                    "days_unlogged": m.days_late,
                }
                for m in coverage.openings
            ],
            "escalations": [
                {
                    "shift_id": m.shift.id,
                    "elder": m.elder_name,
                    "scheduled_at": m.shift.scheduled_at.strftime("%Y-%m-%d %H:%M"),
                }
                for m in coverage.escalations
            ],
            "carrying_the_network": coverage.carrying,
            "gone_quiet": coverage.quiet,
        }

    @tool
    def nudge_volunteer(volunteer: str, message: str) -> str:
        """Ask one volunteer about a shift that was not logged. They do not hear about it twice.

        Args:
            volunteer: The volunteer's name, exactly as `schedule` gave it.
            message: One or two friendly sentences. Ask whether they went; do not accuse.
        """
        rejected = _clean(message)
        if rejected:
            return rejected
        known = {m.volunteer_name: m for m in coverage.nudges}
        if volunteer not in known:
            return f"No unlogged shift for {volunteer}. Nothing was sent, and nothing should be."
        outbox.append(
            Message(
                to="volunteer",
                recipient=volunteer,
                body=message.strip(),
                about_shift=known[volunteer].shift.id,
            )
        )
        return f"Sent to {volunteer}."

    @tool
    def ask_group(message: str) -> str:
        """Ask the whole network to cover the open shifts. One message, all of them.

        Args:
            message: The days and times that need somebody, and a question. Never an assignment.
        """
        rejected = _clean(message)
        if rejected:
            return rejected
        if not coverage.openings:
            return "Nothing is open. Nothing was sent."
        outbox.append(Message(to="group", body=message.strip()))
        return f"Sent to the group about {len(coverage.openings)} shift(s)."

    @tool
    def tell_coordinator(message: str) -> str:
        """Hand a gap to the coordinator. Only for shifts the group has already been asked about.

        Args:
            message: Which shift, when, and that nobody has claimed it. Facts, then stop.
        """
        rejected = _clean(message)
        if rejected:
            return rejected
        if not coverage.escalations:
            return (
                "Nothing reached her. The group has not run out of time on anything yet, so "
                "this stays with them. Nothing was sent."
            )
        outbox.append(Message(to="coordinator", body=message.strip()))
        return "Sent to the coordinator."

    agent = Agent(
        model=intake_model(max_tokens=4000),
        system_prompt=f"{SYSTEM_PROMPT}\n\nWrite in: {locale}.",
        tools=[schedule, nudge_volunteer, ask_group, tell_coordinator],
        name="roster",
        description="The evening pass over the schedule.",
    )
    return agent, outbox


def run(
    store: Store | None = None,
    as_of: date | None = None,
    now: datetime | None = None,
    locale: str = "es",
) -> tuple[Coverage, list[Message]]:
    """One evening's pass. Returns what was found and what will be sent."""
    store = store or open_store()
    as_of = as_of or date.fromisoformat(store.generated_for)
    coverage = assess(store, as_of, now)

    if coverage.quiet_evening:
        return coverage, []

    agent, outbox = build_agent(coverage, locale)
    try:
        agent("Read tonight's coverage and send what needs sending.")
    except Exception:  # noqa: BLE001 - a rota does not stop because a model did
        outbox.clear()

    if not outbox:
        return coverage, plain_messages(coverage, locale)

    # A gap the model forgot about is a person nobody visits. Fill in what it missed, and
    # nothing else: the group and the coordinator each get one message or none, so a model
    # that already wrote one must not be seconded by a fallback saying the same thing twice.
    nudged = {m.about_shift for m in outbox if m.to == "volunteer"}
    spoken_to = {m.to for m in outbox}

    fallback: list[Message] = []
    for message in plain_messages(coverage, locale):
        if message.to == "volunteer":
            if message.about_shift not in nudged:
                fallback.append(message)
        elif message.to not in spoken_to:
            fallback.append(message)

    return coverage, outbox + fallback
