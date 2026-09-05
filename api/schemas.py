"""What the API sends and accepts.

Separate from `core.models` on purpose. The domain model is what Baton knows; these are what
a screen needs, which is usually less and occasionally joined. `ElderCard` carries the
volunteer's name rather than the volunteer's id because the card shows a name, and a client
that has to fetch fourteen volunteers to render one card is a client that will render it
late.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from core.models import Alert, Brief, Contact, Medication, Observation


class LoginRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class Session(BaseModel):
    token: str
    role: str
    id: str
    name: str
    org: str
    locale: str = "es"


class ElderCard(BaseModel):
    """One person as they appear in a list."""

    id: str
    name: str
    address: str = ""
    last_visit: datetime | None = None
    last_visit_by: str = ""
    days_since_visit: int | None = None
    alert: str = ""


class ShiftCard(BaseModel):
    id: str
    elder_id: str
    elder_name: str
    address: str = ""
    scheduled_at: datetime
    status: str
    volunteer_id: str | None = None
    volunteer_name: str = ""


class TodayResponse(BaseModel):
    """V1. What one volunteer has to do today, and nothing about anybody else."""

    as_of: date
    volunteer: str
    shifts: list[ShiftCard]
    people: list[ElderCard]


class BriefResponse(BaseModel):
    """V2. Prose from the model plus the facts it was allowed to see."""

    elder_id: str
    elder_name: str
    brief: Brief
    last_visit: datetime | None = None
    written_by_model: bool = True
    cached: bool = False


class RecordRequest(BaseModel):
    """V3. A visit note as spoken, before anybody has agreed what it says."""

    elder_id: str
    shift_id: str | None = None
    transcript: str = Field(min_length=1)


class RecordResponse(BaseModel):
    """The chips the volunteer taps to correct. Nothing is stored as confirmed yet."""

    visit_id: str
    elder_name: str
    source_lang: str
    observations: list[Observation]
    followups: list[str] = []


class ConfirmRequest(BaseModel):
    observations: list[Observation]
    followups: list[str] = []


class ClaimResponse(BaseModel):
    shift: ShiftCard
    message: str


class Timeline(BaseModel):
    at: datetime
    volunteer_name: str
    summary: str
    quotes: list[str] = []


class ElderRecord(BaseModel):
    """C3. The living record, which is the point of the whole product."""

    id: str
    name: str
    age: int | None = None
    address: str = ""
    conditions: list[str] = []
    allergies: list[str] = []
    medications: list[Medication] = []
    contacts: list[Contact] = []
    communication_notes: str = ""
    decision_maker: str = ""
    baseline: dict[str, float] = {}
    visits_counted: int = 0
    timeline: list[Timeline] = []
    alert: Alert | None = None


class CoverageGap(BaseModel):
    shift: ShiftCard
    rung: str
    days_late: int = 0


class CoordinatorToday(BaseModel):
    """C1. The landing screen: who needs her, what is uncovered, and nothing else."""

    as_of: date
    organization: str
    alerts: list[Alert]
    gaps: list[CoverageGap]
    people_checked: int
    quiet: bool


class VolunteerLoad(BaseModel):
    id: str
    name: str
    visits: int
    carrying: bool = False
    quiet: bool = False


class CoverageResponse(BaseModel):
    """C4. The imbalance, with numbers, because it is invisible without them."""

    as_of: date
    load: list[VolunteerLoad]
    shifts: list[ShiftCard]
    open_count: int


class WeeklyReport(BaseModel):
    """C5. What the agent sends on Monday without being asked."""

    week_ending: date
    visits_logged: int
    people_seen: int
    people_missed: list[str]
    alerts_opened: int
    alerts_acknowledged: int
    busiest: list[VolunteerLoad]
    gaps_next_week: int
