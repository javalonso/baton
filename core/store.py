"""Reading and writing the world.

`Store` is an interface with two backends, and the split is not ceremony. The JSON backend
keeps the demo reproducible from a clone and the domain logic testable without AWS. The
DynamoDB backend is what runs in Lambda, where the filesystem is ephemeral and a visit
written during one invocation has to survive into the next.

Everything an agent can ask for is declared here. The agents never learn which backend
answered, which is the whole point: `agents/watch.py` reads `store.elders` the same way in a
test and in production.

The read helpers below are written once against the abstract collections. A backend that can
answer a question faster is free to override one -- `DynamoStore.visits_for` does, because a
person's visits are a single query rather than a filter over all of them.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from core.models import Alert, Elder, Shift, Visit, Volunteer

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"


class ShiftAlreadyClaimed(Exception):
    """Two volunteers pressed the same button. Exactly one of them is going to be told no.

    Raised rather than returned because the caller has to handle it: the second volunteer
    needs a different screen, not a slightly different success message.
    """


class Store(ABC):
    """What the rest of Baton is allowed to ask storage for."""

    # -- identity ------------------------------------------------------------

    @property
    @abstractmethod
    def organization(self) -> dict: ...

    @property
    @abstractmethod
    def generated_for(self) -> str:
        """The date the world is described as of, ISO. The demo's "today"."""

    @property
    def org_id(self) -> str:
        return self.organization["id"]

    # -- collections ---------------------------------------------------------

    @property
    @abstractmethod
    def elders(self) -> list[Elder]: ...

    @property
    @abstractmethod
    def volunteers(self) -> list[Volunteer]: ...

    @property
    @abstractmethod
    def visits(self) -> list[Visit]: ...

    @property
    @abstractmethod
    def shifts(self) -> list[Shift]: ...

    @property
    @abstractmethod
    def alerts(self) -> list[Alert]: ...

    # -- lookups -------------------------------------------------------------

    def elder(self, elder_id: str) -> Elder:
        return next(e for e in self.elders if e.id == elder_id)

    def volunteer(self, volunteer_id: str) -> Volunteer:
        return next(v for v in self.volunteers if v.id == volunteer_id)

    def shift(self, shift_id: str) -> Shift:
        return next(s for s in self.shifts if s.id == shift_id)

    def visits_for(self, elder_id: str) -> list[Visit]:
        return sorted(
            (v for v in self.visits if v.elder_id == elder_id), key=lambda v: v.started_at
        )

    def volunteer_names(self) -> dict[str, str]:
        return {v.id: v.name for v in self.volunteers}

    def visit_counts(self) -> dict[str, int]:
        """Visits logged per volunteer. The raw material for the coverage screen."""
        counts = {v.id: 0 for v in self.volunteers}
        for visit in self.visits:
            counts[visit.volunteer_id] = counts.get(visit.volunteer_id, 0) + 1
        return counts

    # -- writes --------------------------------------------------------------

    @abstractmethod
    def add_visit(self, visit: Visit) -> Visit:
        """Record a visit. If it closes a shift, the shift is marked logged in the same breath."""

    @abstractmethod
    def claim_shift(self, shift_id: str, volunteer_id: str) -> Shift:
        """Assign an unclaimed shift, or raise `ShiftAlreadyClaimed`.

        This is the one place in Baton where two people can race, so it is the one place
        that needs to be atomic rather than merely careful.
        """

    @abstractmethod
    def save_alert(self, alert: Alert) -> Alert: ...

    @abstractmethod
    def set_alert_status(self, alert_id: str, status: str, by: str | None = None) -> Alert: ...

    @abstractmethod
    def save_elder(self, elder: Elder) -> Elder: ...

    @abstractmethod
    def save_volunteer(self, volunteer: Volunteer) -> Volunteer: ...

    @abstractmethod
    def save_shift(self, shift: Shift) -> Shift: ...


class JsonStore(Store):
    """The whole world in one file, held in memory, written back on every change.

    Correct for one process and one organization, which is the demo and every test. It is
    wrong the moment two Lambdas run at once, which is why `DynamoStore` exists.
    """

    def __init__(self, path: Path | str = DEFAULT_PATH, writable: bool = False) -> None:
        self.path = Path(path)
        self.writable = writable
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._organization: dict = raw["organization"]
        self._generated_for: str = raw["generated_for"]
        self._elders = [Elder(**e) for e in raw["elders"]]
        self._volunteers = [Volunteer(**v) for v in raw["volunteers"]]
        self._visits = [Visit(**v) for v in raw["visits"]]
        self._shifts = [Shift(**s) for s in raw.get("shifts", [])]
        self._alerts = [Alert(**a) for a in raw.get("alerts", [])]

    @property
    def organization(self) -> dict:
        return self._organization

    @property
    def generated_for(self) -> str:
        return self._generated_for

    @property
    def elders(self) -> list[Elder]:
        return self._elders

    @property
    def volunteers(self) -> list[Volunteer]:
        return self._volunteers

    @property
    def visits(self) -> list[Visit]:
        return self._visits

    @property
    def shifts(self) -> list[Shift]:
        return self._shifts

    @property
    def alerts(self) -> list[Alert]:
        return self._alerts

    # -- writes --------------------------------------------------------------

    def _flush(self) -> None:
        if not self.writable:
            return
        payload = {
            "generated_for": self._generated_for,
            "organization": self._organization,
            "elders": [e.model_dump(mode="json") for e in self._elders],
            "volunteers": [v.model_dump(mode="json") for v in self._volunteers],
            "visits": [v.model_dump(mode="json") for v in self._visits],
            "shifts": [s.model_dump(mode="json") for s in self._shifts],
            "alerts": [a.model_dump(mode="json") for a in self._alerts],
        }
        self.path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    def _replace(self, items: list, item) -> None:
        for i, existing in enumerate(items):
            if existing.id == item.id:
                items[i] = item
                return
        items.append(item)

    def add_visit(self, visit: Visit) -> Visit:
        self._replace(self._visits, visit)
        if visit.shift_id:
            for shift in self._shifts:
                if shift.id == visit.shift_id:
                    shift.status = "logged"
                    shift.volunteer_id = shift.volunteer_id or visit.volunteer_id
        self._flush()
        return visit

    def claim_shift(self, shift_id: str, volunteer_id: str) -> Shift:
        shift = self.shift(shift_id)
        if shift.volunteer_id and shift.volunteer_id != volunteer_id:
            raise ShiftAlreadyClaimed(shift_id)
        shift.volunteer_id = volunteer_id
        shift.status = "claimed"
        self._flush()
        return shift

    def save_alert(self, alert: Alert) -> Alert:
        self._replace(self._alerts, alert)
        self._flush()
        return alert

    def set_alert_status(self, alert_id: str, status: str, by: str | None = None) -> Alert:
        alert = next(a for a in self._alerts if a.id == alert_id)
        alert.status = status  # type: ignore[assignment]
        alert.acknowledged_by = by
        self._flush()
        return alert

    def save_elder(self, elder: Elder) -> Elder:
        self._replace(self._elders, elder)
        self._flush()
        return elder

    def save_volunteer(self, volunteer: Volunteer) -> Volunteer:
        self._replace(self._volunteers, volunteer)
        self._flush()
        return volunteer

    def save_shift(self, shift: Shift) -> Shift:
        self._replace(self._shifts, shift)
        self._flush()
        return shift


def open_store() -> Store:
    """The backend the environment asks for.

    `BATON_STORE=dynamo` in Lambda, JSON everywhere else. Defaulting to JSON means a fresh
    clone runs the tests and the demo with no AWS account at all.
    """
    backend = os.environ.get("BATON_STORE", "json").lower()
    if backend == "dynamo":
        from core.dynamo import DynamoStore

        return DynamoStore()
    path = os.environ.get("BATON_DATA", DEFAULT_PATH)
    return JsonStore(path, writable=bool(os.environ.get("BATON_DATA")))


def now() -> datetime:
    """One clock, so tests can freeze it in one place."""
    return datetime.now()
