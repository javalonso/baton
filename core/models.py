"""Domain models.

Storage is language-neutral: an observation records a category, a trend and the verbatim
quote it came from. `source_lang` travels with the visit, so a note spoken in Spanish can
be read in a portal set to English without ever translating the stored record.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.vocabulary import Category, Confidence, Trend

Locale = Literal["es", "en"]


class Observation(BaseModel):
    """One thing a volunteer noticed, extracted from a visit note.

    `quote` is not optional by accident. Nothing is asserted about a person without the
    words that produced it, so a coordinator can always read the source.
    """

    category: Category
    summary: str = Field(description="What was observed, in one short clause.")
    trend: Trend = Field(description="How this compares to the person's own normal.")
    confidence: Confidence
    quote: str = Field(description="The verbatim words from the note that support this.")


class Extraction(BaseModel):
    """What the intake agent returns for a single visit note."""

    source_lang: Locale
    observations: list[Observation]
    followups: list[str] = Field(
        default_factory=list,
        description="Anything the volunteer said needs doing that is not a health observation.",
    )


class Contact(BaseModel):
    name: str
    relationship: str
    phone: str


class Elder(BaseModel):
    id: str
    org_id: str
    name: str
    dob: date | None = None
    address: str = ""
    contacts: list[Contact] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    communication_notes: str = ""
    decision_maker: str = ""


class Volunteer(BaseModel):
    id: str
    org_id: str
    name: str
    phone: str = ""
    locale: Locale = "es"
    active: bool = True


class Visit(BaseModel):
    id: str
    elder_id: str
    volunteer_id: str
    started_at: datetime
    transcript: str = ""
    source_lang: Locale = "es"
    audio_key: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    confirmed: bool = False


class Baseline(BaseModel):
    """A person's own normal, over a rolling window. Never a population average."""

    elder_id: str
    window_days: int = 21
    # category -> share of visits in the window where the trend was "worse"
    worse_rate: dict[str, float] = Field(default_factory=dict)
    visits_counted: int = 0
    updated_at: datetime | None = None


class AlertEvidence(BaseModel):
    quote: str
    volunteer_name: str
    observed_at: datetime
    category: Category


class Alert(BaseModel):
    id: str
    elder_id: str
    severity: Literal["attention", "urgent"]
    days_off_pattern: int
    categories: list[Category]
    evidence: list[AlertEvidence] = Field(default_factory=list)
    suggested_action: str = ""
    opened_at: datetime
    status: Literal["open", "acknowledged", "dismissed"] = "open"
    acknowledged_by: str | None = None
