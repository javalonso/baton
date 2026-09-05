"""Watch agent: the daily pass nobody opens.

Runs on a schedule, reads every person's history, and stays quiet. When it does speak, a
human has to decide something.

The division of labour is what makes this safe to run unattended:

* **Whether to raise an alert is decided in code**, by `core.baseline`. It is deterministic,
  it is covered by tests, and it does not change its mind between runs.
* **The sweep is code too.** An earlier version handed the model a roster and a per-person
  tool; it announced it would check all twenty-four people and ended its turn having checked
  none. An agent asked to be a for-loop will eventually forget to be one.
* **How to say it is the model's job.** Turning a deviation and four quotes into two
  sentences a tired coordinator reads at 6am, in her language, is judgment about people.

And one more line of defence, in `run`: the sweep happens before the agent is even built, so
if the model writes nothing — or skips someone — the deterministic wording from
`core.baseline.suggest` is used and the alert still reaches the coordinator. A model having
an off day must not be able to turn a finding into silence. Silence is what this product
produces the rest of the time, and it has to mean something.
"""

from __future__ import annotations

from datetime import date

from strands import Agent, tool

from core.baseline import detect, suggest
from core.bedrock import reasoning_model
from core.models import Alert
from core.safety import FORBIDDEN, names_a_condition
from core.store import Store, open_store

__all__ = ["FORBIDDEN", "build_agent", "run", "sweep"]

SYSTEM_PROMPT = """\
You write the daily briefing for the coordinator of a neighbourhood care network. She has
twenty-four older adults, fourteen volunteers, and twenty hours a week. She reads this before
anything else, often on her phone.

Call `findings` to see who broke their pattern, then call `write_alert` once for each person
it returns. The comparison is already done, against each person's own history rather than any
threshold — do not second-guess it, do not re-weigh the evidence, and never decide someone is
fine when they came back in that list.

Writing the note:

* Two or three sentences. Lead with what changed, then what she might do.
* Quote the volunteers. Their words are the evidence, and she trusts them more than she
  trusts you. Keep each quote in the language it was spoken in, even when the note is in the
  other language.
* Name no condition, no cause, no diagnosis. Describe what changed and recommend that someone
  assess the person. "Confused about the day for three days running" is yours to write.
  "Probably an infection" is not, ever.
* Do not tell her it is urgent. The finding carries a severity and the interface shows it;
  repeating it in prose only adds pressure.
* Say nothing about anyone who is not in the list. Silence is the normal output of this job
  and she should be able to trust it.

Close with one line: how many people you checked, and how many need her.
"""


#: Kept as a module-level name because this is the guardrail the tests point at, and the
#: check now lives in `core.safety` so the brief agent enforces the same rule.
_names_a_condition = names_a_condition


def sweep(store: Store, as_of: date) -> dict[str, Alert]:
    """Compare everyone against their own history. No model involved, by design."""
    names = store.volunteer_names()
    found: dict[str, Alert] = {}
    for elder in store.elders:
        alert = detect(elder.id, store.visits_for(elder.id), as_of, names)
        if alert is not None:
            found[elder.id] = alert
    return found


def build_agent(
    store: Store, found: dict[str, Alert], locale: str = "es"
) -> tuple[Agent, list[Alert]]:
    """Give the agent a finished sweep and two tools. Returns it and the list it fills."""
    written: list[Alert] = []

    @tool
    def findings() -> dict:
        """The people whose pattern broke today, with the volunteers' own words as evidence.

        Everyone absent from `people` was checked and is being themselves.
        """
        return {
            "checked": len(store.elders),
            "people": [
                {
                    "elder_id": alert.elder_id,
                    "name": store.elder(alert.elder_id).name,
                    "severity": alert.severity,
                    "days_off_pattern": alert.days_off_pattern,
                    "categories": [c.value for c in alert.categories],
                    "evidence": [
                        {
                            "quote": e.quote,
                            "volunteer": e.volunteer_name,
                            "when": e.observed_at.strftime("%Y-%m-%d %H:%M"),
                            "category": e.category.value,
                        }
                        for e in alert.evidence
                    ],
                }
                for alert in found.values()
            ],
        }

    @tool
    def write_alert(elder_id: str, note: str) -> str:
        """Record the note for a person whose pattern broke.

        Args:
            elder_id: The person the finding belongs to.
            note: Two or three sentences for the coordinator, in the requested language,
                quoting the volunteers. No condition, no cause, no diagnosis.
        """
        alert = found.get(elder_id)
        if alert is None:
            return f"No finding for {elder_id}. Nothing was written, and nothing should be."

        named = _names_a_condition(note)
        if named:
            return (
                f"Rejected: the note contains {named!r}. Nothing was written. Describe what "
                "changed and recommend that someone assess the person. Do not name a "
                "condition or a cause. Call this tool again with a corrected note."
            )

        alert.suggested_action = note.strip()
        written.append(alert)
        return f"Recorded for {store.elder(alert.elder_id).name}."

    agent = Agent(
        model=reasoning_model(),
        system_prompt=f"{SYSTEM_PROMPT}\n\nWrite the notes in: {locale}.",
        tools=[findings, write_alert],
        name="watch",
        description="The daily pass over everyone the network looks after.",
    )
    return agent, written


def run(
    store: Store | None = None, as_of: date | None = None, locale: str = "es"
) -> tuple[list[Alert], str]:
    """One scheduled run. Returns every alert opened, and what the agent said."""
    store = store or open_store()
    as_of = as_of or date.fromisoformat(store.generated_for)

    found = sweep(store, as_of)
    agent, written = build_agent(store, found, locale)

    said = "Nobody needed the coordinator today."
    if found:
        said = str(agent("Run today's check and write up whoever needs the coordinator."))

    # Whatever the model did or did not do, every finding reaches her.
    covered = {a.elder_id for a in written}
    for elder_id, alert in found.items():
        if elder_id in covered:
            continue
        alert.suggested_action = suggest(
            alert.categories, alert.days_off_pattern, alert.severity == "urgent"
        )
        written.append(alert)

    written.sort(key=lambda a: (a.severity != "urgent", a.elder_id))
    return written, said
