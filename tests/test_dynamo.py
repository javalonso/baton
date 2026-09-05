"""The same contract as `test_store_writes.py`, against the real table.

Opt-in, because it costs money and needs credentials:

    BATON_INTEGRATION=1 AWS_PROFILE=ninja pytest tests/test_dynamo.py

Everything is written under a throwaway organization id and deleted afterwards, so running
this never touches the demo data.

The test that matters is `test_only_one_volunteer_wins_the_race`. Every other write in Baton
can be retried; that one cannot, because the losing volunteer has to be shown a different
screen. It is the reason claiming is a conditional update rather than a read and a write.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from core.dynamo import DynamoStore, elder_pk, org_pk, shifts_pk, table
from core.models import Elder, Shift, Visit, Volunteer
from core.store import ShiftAlreadyClaimed

pytestmark = pytest.mark.skipif(
    not os.environ.get("BATON_INTEGRATION"),
    reason="set BATON_INTEGRATION=1 to run against DynamoDB",
)

ORG = "org-integration-test"


def _clear(store: DynamoStore) -> None:
    from boto3.dynamodb.conditions import Key

    handle = table()
    for pk in (org_pk(ORG), shifts_pk(ORG), elder_pk("elder-t1")):
        items = handle.query(KeyConditionExpression=Key("PK").eq(pk)).get("Items", [])
        with handle.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})


@pytest.fixture
def store() -> DynamoStore:
    store = DynamoStore(org_id=ORG)
    _clear(store)
    store.save_organization({"id": ORG, "name": "Test", "timezone": "UTC"}, "2026-09-14")
    store.save_elder(Elder(id="elder-t1", org_id=ORG, name="Test Elder"))
    for i in range(1, 4):
        store.save_volunteer(Volunteer(id=f"vol-t{i}", org_id=ORG, name=f"Volunteer {i}"))
    yield store
    _clear(store)


def _shift(shift_id: str, volunteer_id: str | None = None, status: str = "open") -> Shift:
    return Shift(
        id=shift_id,
        org_id=ORG,
        elder_id="elder-t1",
        volunteer_id=volunteer_id,
        scheduled_at=datetime(2026, 9, 16, 9, 0),
        status=status,
    )


def test_the_org_loads_in_one_query(store: DynamoStore):
    assert store.organization["name"] == "Test"
    assert store.generated_for == "2026-09-14"
    assert [e.id for e in store.elders] == ["elder-t1"]
    assert len(store.volunteers) == 3


def test_a_visit_round_trips_with_its_observations(store: DynamoStore):
    from core.models import Observation

    visit = Visit(
        id="visit-t1",
        elder_id="elder-t1",
        volunteer_id="vol-t1",
        started_at=datetime(2026, 9, 14, 10, 30),
        transcript="Se veia bien, comio completo.",
        source_lang="es",
        observations=[
            Observation(
                category="food",
                summary="ate a full meal",
                trend="usual",
                confidence="clear",
                quote="comio completo",
            )
        ],
    )
    store.add_visit(visit)
    read = DynamoStore(org_id=ORG).visits_for("elder-t1")
    assert [v.id for v in read] == ["visit-t1"]
    assert read[0].observations[0].quote == "comio completo"
    assert read[0].started_at == visit.started_at
    assert read[0].source_lang == "es"


def test_logging_a_visit_closes_its_shift_in_one_transaction(store: DynamoStore):
    store.save_shift(_shift("shift-t1"))
    store.add_visit(
        Visit(
            id="visit-t2",
            shift_id="shift-t1",
            elder_id="elder-t1",
            volunteer_id="vol-t2",
            started_at=datetime(2026, 9, 14, 11, 0),
        )
    )
    fresh = DynamoStore(org_id=ORG)
    shift = fresh.shift("shift-t1")
    assert shift.status == "logged"
    assert shift.volunteer_id == "vol-t2"
    assert [v.id for v in fresh.visits_for("elder-t1")] == ["visit-t2"]


def test_an_unclaimed_shift_can_be_claimed(store: DynamoStore):
    store.save_shift(_shift("shift-t2"))
    claimed = store.claim_shift("shift-t2", "vol-t1")
    assert claimed.volunteer_id == "vol-t1"
    assert claimed.status == "claimed"


def test_a_claimed_shift_refuses_a_second_volunteer(store: DynamoStore):
    store.save_shift(_shift("shift-t3"))
    store.claim_shift("shift-t3", "vol-t1")
    with pytest.raises(ShiftAlreadyClaimed):
        store.claim_shift("shift-t3", "vol-t2")
    assert DynamoStore(org_id=ORG).shift("shift-t3").volunteer_id == "vol-t1"


def test_only_one_volunteer_wins_the_race(store: DynamoStore):
    """Eight clients, one shift, one winner. Anything else double-books a doorstep."""
    store.save_shift(_shift("shift-t4"))

    def claim(n: int) -> str | None:
        try:
            return DynamoStore(org_id=ORG).claim_shift("shift-t4", f"vol-t{n % 3 + 1}").volunteer_id
        except ShiftAlreadyClaimed:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(8)))

    winners = [r for r in results if r]
    assert len(winners) == 1
    assert DynamoStore(org_id=ORG).shift("shift-t4").volunteer_id == winners[0]


def test_an_alert_moves_between_status_buckets(store: DynamoStore):
    from core.models import Alert, AlertEvidence

    alert = Alert(
        id="alert-t1",
        elder_id="elder-t1",
        severity="attention",
        days_off_pattern=3,
        categories=["food"],
        evidence=[
            AlertEvidence(
                quote="no quiso cenar",
                volunteer_name="Volunteer 1",
                observed_at=datetime(2026, 9, 12, 18, 0),
                category="food",
            )
        ],
        opened_at=datetime(2026, 9, 13, 20, 0),
    )
    store.save_alert(alert)
    assert [a.id for a in DynamoStore(org_id=ORG).alerts] == ["alert-t1"]

    store.set_alert_status("alert-t1", "acknowledged", by="coordinator")
    reread = DynamoStore(org_id=ORG).alerts[0]
    assert reread.status == "acknowledged"
    assert reread.acknowledged_by == "coordinator"
    assert reread.evidence[0].quote == "no quiso cenar"
