"""Brief agent: what the next person needs to know before they knock.

Two outputs, one job. The pre-visit brief (V2) is read on a doorstep thirty seconds before
the door opens. The handoff sheet (C3) is read by a volunteer taking over a person they have
never met, or by a nurse asking questions nobody in the room can answer. Both are the same
three paragraphs; only the paper changes.

Today this knowledge exists, and it exists in one volunteer's head. Marco has been visiting
Carmen for two years and knows she hears better on the right. Nobody wrote it down, so the
person covering for him on Thursday starts from nothing and Carmen has to teach them again.

The split is the same one the watch agent uses, for the same reason:

* **What changed is decided in code.** `core.baseline` compares the last few days against
  this person's own history. The model is not asked whether someone is different; it is told.
* **The record is read out verbatim.** Medications, allergies, contacts and the note about
  how to talk to this person go on the sheet as written. Nothing there is generated.
* **Writing three short paragraphs is the model's job**, and only that.

One rule differs from the watch agent, and it is deliberate. The watch agent may never name
a condition, because it is describing a change it just noticed. The brief agent reads a
person's own chart aloud, where "hypertension" is a fact somebody wrote down. So it may
repeat what the record already says and nothing beyond it. `core.safety.names_a_new_condition`
is what enforces the difference.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from strands import Agent, tool

from core.baseline import EVALUATION_DAYS, compute_baseline, detect, deviating_categories
from core.bedrock import reasoning_model
from core.handoff import render
from core.models import Brief, Elder, HandoffSheet
from core.safety import names_a_new_condition
from core.store import Store, open_store
from core.vocabulary import Trend

SHEETS = Path(__file__).resolve().parents[1] / "data" / "handoffs"

SYSTEM_PROMPT = """\
You write the note a volunteer reads on the doorstep, thirty seconds before knocking, and the
same note goes on the one-page sheet an emergency room might read. Assume the reader has never
met this person and has no time.

Call `facts` first. It gives you the record and what already changed. The comparison against
this person's own history is done; do not redo it, do not argue with it, and do not decide
someone is fine when the facts say they are not. Then call `record_brief` exactly once.

Three fields, and each one is two or three sentences at most:

* `since_last_visit` — what is different, and how long it has been going on. Quote a volunteer
  where a quote says it better than you can, and keep the quote in the language it was spoken
  in. If nothing changed, say so plainly. "Nothing has changed since Tuesday" is a useful
  sentence and the reader will believe the next one more because you wrote it.
* `watch_for` — what this person should look at today, in the specific. "Whether she drinks
  anything while you are there" beats "monitor fluid intake."
* `how_to_be_with_them` — read the record's own note about this person and put it in your own
  words for someone who has never met them. Never invent one. If the record is empty here, say
  that nobody has written this down yet, because that is a true and useful thing to know.

You may repeat what the record already says, including anything on their chart. You may not
add a condition, a cause or a diagnosis that nobody wrote down. Describe what changed and,
where it matters, say it is worth having someone assess them.

Write in the language you are told to. Address the reader as a colleague, not as a patient's
relative and not as a system.
"""

PLAIN = {
    "es": {
        "steady": "Sin cambios desde la última visita, hace {days} día(s). {who} fue la última persona en verla o verlo.",
        "changed": "Lleva {days} día(s) fuera de su patrón en {cats}. Palabras de quien estuvo ahí: «{quote}».",
        "watch_changed": "Fíjate hoy en {cats}. Si sigue igual, vale la pena que alguien la o lo valore.",
        "watch_steady": "Nada en particular. Si algo se sale de lo normal, dilo en la nota de voz.",
        "no_notes": "Nadie ha escrito todavía cómo tratar a esta persona. Si aprendes algo hoy, déjalo en la nota.",
        "never": "No hay visitas registradas todavía.",
    },
    "en": {
        "steady": "Nothing has changed since the last visit {days} day(s) ago. {who} was the last person in.",
        "changed": "Off pattern for {days} day(s) across {cats}. In the words of whoever was there: “{quote}”.",
        "watch_changed": "Watch {cats} today. If it holds, it is worth having someone assess them.",
        "watch_steady": "Nothing in particular. If something is off, say so in the voice note.",
        "no_notes": "Nobody has written down how to be with this person yet. If you learn something today, leave it in the note.",
        "never": "No visits recorded yet.",
    },
}


def facts_for(store: Store, elder_id: str, as_of: date) -> dict:
    """Everything the brief rests on, assembled without a model.

    The agent never reaches into the store. It gets this dict, and it cannot ask for a
    person it was not given.
    """
    elder = store.elder(elder_id)
    visits = store.visits_for(elder_id)
    names = store.volunteer_names()
    baseline = compute_baseline(visits, as_of)
    alert = detect(elder_id, visits, as_of, names)

    recent: list[dict] = []
    horizon = as_of - timedelta(days=EVALUATION_DAYS)
    for visit in reversed(visits):
        if visit.started_at.date() < horizon:
            break
        off = deviating_categories(visit, baseline)
        recent.append(
            {
                "when": visit.started_at.strftime("%Y-%m-%d"),
                "volunteer": names.get(visit.volunteer_id, visit.volunteer_id),
                "off_pattern": sorted(c.value for c in off),
                "quotes": [
                    {"category": o.category.value, "trend": o.trend.value, "quote": o.quote}
                    for o in visit.observations
                    if o.trend is Trend.WORSE or o.category in off
                ],
            }
        )

    last = visits[-1] if visits else None
    return {
        "name": elder.name,
        "days_since_last_visit": (as_of - last.started_at.date()).days if last else None,
        "last_volunteer": names.get(last.volunteer_id, "") if last else "",
        "on_the_record": {
            "conditions": elder.conditions,
            "allergies": elder.allergies,
            "medications": [
                {"name": m.name, "dose": m.dose, "schedule": m.schedule} for m in elder.medications
            ],
            "how_to_communicate": elder.communication_notes,
            "decision_maker": elder.decision_maker,
        },
        "off_pattern": bool(alert),
        "days_off_pattern": alert.days_off_pattern if alert else 0,
        "categories_off": [c.value for c in alert.categories] if alert else [],
        "recent_visits": recent,
    }


def plain_brief(facts: dict, elder: Elder, locale: str = "es") -> Brief:
    """The brief this produces when the model produces nothing.

    Not a placeholder. A volunteer standing at a door with a phone in one hand gets a real
    briefing whether or not Bedrock answered, because the alternative is knocking blind.
    """
    words = PLAIN.get(locale, PLAIN["es"])
    days = facts["days_since_last_visit"]
    quote = next(
        (
            q["quote"]
            for visit in facts["recent_visits"]
            for q in visit["quotes"]
            if q["trend"] == Trend.WORSE.value
        ),
        "",
    )
    categories = ", ".join(facts["categories_off"])

    if days is None:
        since = words["never"]
    elif facts["off_pattern"]:
        since = words["changed"].format(
            days=facts["days_off_pattern"], cats=categories, quote=quote
        )
    else:
        since = words["steady"].format(days=days, who=facts["last_volunteer"])

    return Brief(
        elder_id=elder.id,
        locale=locale,
        since_last_visit=since,
        watch_for=(
            words["watch_changed"].format(cats=categories)
            if facts["off_pattern"]
            else words["watch_steady"]
        ),
        how_to_be_with_them=elder.communication_notes or words["no_notes"],
        generated_at=datetime.now(),
        written_by_model=False,
    )


def build_agent(
    store: Store, elder_id: str, as_of: date, locale: str = "es"
) -> tuple[Agent, list[Brief]]:
    """The agent, its two tools, and the list it is expected to fill."""
    elder = store.elder(elder_id)
    known = elder.written_down()
    dossier = facts_for(store, elder_id, as_of)
    written: list[Brief] = []

    @tool
    def facts() -> dict:
        """The record, and what has already been compared against this person's own history."""
        return dossier

    @tool
    def record_brief(since_last_visit: str, watch_for: str, how_to_be_with_them: str) -> str:
        """Record the brief for this person. Call once.

        Args:
            since_last_visit: What is different and for how long, quoting a volunteer.
            watch_for: What to pay attention to today, in the specific.
            how_to_be_with_them: How to talk to and be around this person, from the record.
        """
        for field, text in (
            ("since_last_visit", since_last_visit),
            ("watch_for", watch_for),
            ("how_to_be_with_them", how_to_be_with_them),
        ):
            invented = names_a_new_condition(text, known)
            if invented:
                return (
                    f"Rejected: {field} contains {invented!r}, which is not on this person's "
                    "record. Nothing was written. You may repeat what the record says and "
                    "describe what changed. Call this tool again with that field corrected."
                )

        written.append(
            Brief(
                elder_id=elder_id,
                locale=locale,
                since_last_visit=since_last_visit.strip(),
                watch_for=watch_for.strip(),
                how_to_be_with_them=how_to_be_with_them.strip(),
                generated_at=datetime.now(),
                written_by_model=True,
            )
        )
        return f"Recorded for {elder.name}."

    agent = Agent(
        model=reasoning_model(),
        system_prompt=f"{SYSTEM_PROMPT}\n\nWrite in: {locale}.",
        tools=[facts, record_brief],
        name="brief",
        description="What the next person needs to know before they knock.",
    )
    return agent, written


def write(
    elder_id: str,
    store: Store | None = None,
    as_of: date | None = None,
    locale: str = "es",
) -> Brief:
    """Write one brief. Falls back to the deterministic version if the model does not."""
    store = store or open_store()
    as_of = as_of or date.fromisoformat(store.generated_for)
    elder = store.elder(elder_id)

    agent, written = build_agent(store, elder_id, as_of, locale)
    try:
        agent(f"Write the brief for {elder.name}.")
    except Exception:  # noqa: BLE001 - a doorstep is no place to raise
        written.clear()

    return written[0] if written else plain_brief(facts_for(store, elder_id, as_of), elder, locale)


def handoff(
    elder_id: str,
    store: Store | None = None,
    as_of: date | None = None,
    locale: str = "es",
    out_dir: Path | str = SHEETS,
) -> HandoffSheet:
    """Write the brief, then lay it out as the one page somebody can carry."""
    store = store or open_store()
    as_of = as_of or date.fromisoformat(store.generated_for)
    elder = store.elder(elder_id)

    brief = write(elder_id, store=store, as_of=as_of, locale=locale)
    alert = detect(elder_id, store.visits_for(elder_id), as_of, store.volunteer_names())
    path = Path(out_dir) / f"{elder_id}-{as_of.isoformat()}-{locale}.pdf"

    render(
        elder,
        brief,
        path,
        as_of=as_of,
        locale=locale,
        urgent=bool(alert and alert.severity == "urgent"),
    )

    return HandoffSheet(
        id=f"handoff-{elder_id}-{as_of.isoformat()}",
        elder_id=elder_id,
        generated_at=brief.generated_at or datetime.now(),
        locale=locale,
        brief=brief,
        pdf_key=str(path),
    )
