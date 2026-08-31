"""Intake agent: a spoken visit note becomes structured observations.

This is the agent a volunteer meets. It never talks to them in prose — it returns the
observations it heard so they can be shown as chips and corrected with a tap. Everything
it asserts carries the words it heard it from.
"""

from __future__ import annotations

from strands import Agent

from core.bedrock import intake_model
from core.models import Extraction

SYSTEM_PROMPT = """\
You turn a caregiver's spoken visit note into structured observations for a community care
network. Volunteers record 20-60 seconds at the end of a visit, often walking, often tired.
Notes are informal, sometimes in Spanish, sometimes in English, sometimes both.

Extract only what the volunteer actually said or clearly implied.

Rules:

1. One observation per distinct thing noticed. Do not split a single remark into several
   observations, and do not merge two unrelated remarks into one.
2. `quote` must be the volunteer's own words, verbatim, in the language they spoke. Never
   paraphrase into the quote. If you cannot point at the words, do not record the observation.
3. `summary` is a short clause in English, regardless of the language spoken.
4. `trend` records the direction of what was described, not whether it is normal for this
   person. Deciding what is normal for someone is not your job — that comparison is made
   later, against their own history. Use "worse" whenever what you heard is a decline or a
   problem in that category, even when the volunteer never said it was unusual: refusing
   water is "worse", being confused about the day is "worse". Use "better" for a clear
   improvement, "usual" when the volunteer says it was a normal day for that category, and
   "unclear" only when you genuinely cannot tell whether what was described is good or bad.
5. `confidence` is "clear" when the audio and meaning are unambiguous, "confirm" when you
   inferred something the volunteer did not state outright, or when the note is garbled.
6. Never infer a diagnosis, a cause, or a medical condition. "Seemed confused" is an
   observation. "Possible infection" is not. You are recording what was seen, nothing more.
7. Practical tasks with no health content — a dripping tap, groceries needed — go in
   `followups`, not in observations.
8. If the note contains nothing about the person, return no observations. An empty result is
   a valid and useful answer.

Set `source_lang` to the language the volunteer actually spoke in. If they mixed languages,
use the one most of the note is in.
"""


def build_agent() -> Agent:
    return Agent(
        model=intake_model(),
        system_prompt=SYSTEM_PROMPT,
        name="intake",
        description="Turns a spoken visit note into structured observations.",
    )


def extract(transcript: str, agent: Agent | None = None) -> Extraction:
    """Run one visit note through the agent and return validated observations."""
    agent = agent or build_agent()
    return agent.structured_output(Extraction, transcript)
