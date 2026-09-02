"""Reading and writing the world.

A JSON-file store, deliberately. The demo has to be reproducible from a clone, the domain
logic has to be testable without AWS, and the shape below is the same one DynamoDB will be
given later — `Store` is the seam, so swapping the backend does not reach into the agents.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.models import Alert, Elder, Shift, Visit, Volunteer

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"


class Store:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.organization: dict = raw["organization"]
        self.generated_for: str = raw["generated_for"]
        self.elders: list[Elder] = [Elder(**e) for e in raw["elders"]]
        self.volunteers: list[Volunteer] = [Volunteer(**v) for v in raw["volunteers"]]
        self.visits: list[Visit] = [Visit(**v) for v in raw["visits"]]
        self.shifts: list[Shift] = [Shift(**s) for s in raw.get("shifts", [])]
        self.alerts: list[Alert] = [Alert(**a) for a in raw.get("alerts", [])]

    # -- lookups -------------------------------------------------------------

    def elder(self, elder_id: str) -> Elder:
        return next(e for e in self.elders if e.id == elder_id)

    def volunteer(self, volunteer_id: str) -> Volunteer:
        return next(v for v in self.volunteers if v.id == volunteer_id)

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
