"""The DynamoDB backend.

One table, because the questions this product asks are few and known. The layout:

| item       | PK                  | SK                            | GSI1PK               | GSI1SK               |
|------------|---------------------|-------------------------------|----------------------|----------------------|
| org        | `ORG#<org>`         | `META`                        |                      |                      |
| elder      | `ORG#<org>`         | `ELDER#<id>`                  |                      |                      |
| volunteer  | `ORG#<org>`         | `VOL#<id>`                    |                      |                      |
| alert      | `ORG#<org>`         | `ALERT#<id>`                  | `ORG#<org>#ALERT#<status>` | `<opened_at>`  |
| shift      | `ORG#<org>#SHIFTS`  | `SHIFT#<id>`                  | `ORG#<org>#SHIFT`    | `<scheduled_at>`     |
| visit      | `ELDER#<elder_id>`  | `VISIT#<started_at>#<id>`     | `ORG#<org>#VISIT`    | `<started_at>#<id>`  |
| brief      | `ELDER#<elder_id>`  | `BRIEF#<date>#<locale>`       |                      |                      |

Two deliberate choices worth defending.

The org partition holds everyone and every alert, so opening the coordinator's screen is a
single query rather than four. This is a hot partition by design: a neighborhood is dozens
of people, not millions, and the write rate is a handful of visits a day. Shifts sit in
their own partition only because there are ten times as many of them and they would
otherwise dominate that one query.

Visits are keyed under the person, sorted by time. `visits_for` -- the read every agent
starts from -- is therefore one query returning exactly the rows it needs, already in order.
That is the access pattern the whole product is built on, so it gets the primary key.

Nulls are dropped on write rather than stored (empty strings are kept -- DynamoDB has
allowed them since 2020, and dropping them would lose the difference between "nobody wrote
an address" and "the address is unknown"). An unclaimed shift is one with no
`volunteer_id` attribute at all, which is what makes the claim condition
`attribute_not_exists(volunteer_id)` both correct and atomic.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from core.aws import session
from core.models import Alert, Brief, Elder, Shift, Visit, Volunteer
from core.store import ShiftAlreadyClaimed, Store, brief_key

TABLE = os.environ.get("BATON_TABLE", "baton")
ORG_ID = os.environ.get("BATON_ORG", "org-san-miguel")


def table(name: str | None = None):
    return session().resource("dynamodb").Table(name or TABLE)


def client():
    """The low-level client, for transactions only.

    Deliberately not `table.meta.client`. That one is the resource's client and silently
    applies the same type transformation the resource does, so hand-serialized attribute
    values get serialized a second time and DynamoDB rejects the key as a map.
    """
    return session().client("dynamodb")


# -- item conversion ---------------------------------------------------------

_KEYS = ("PK", "SK", "GSI1PK", "GSI1SK", "entity")


def to_item(model, **keys) -> dict:
    """Pydantic model to DynamoDB item: JSON-safe, floats as Decimal, no nulls."""
    body = json.loads(model.model_dump_json(), parse_float=Decimal, parse_int=int)
    return _drop_nulls({**body, **keys})


def _drop_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value]
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def from_item(model_cls, item: dict):
    body = {k: v for k, v in item.items() if k not in _KEYS}
    return model_cls.model_validate(_undecimal(body))


def _undecimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value) if value % 1 else int(value)
    if isinstance(value, dict):
        return {k: _undecimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_undecimal(v) for v in value]
    return value


# -- key builders ------------------------------------------------------------


def org_pk(org_id: str) -> str:
    return f"ORG#{org_id}"


def shifts_pk(org_id: str) -> str:
    return f"ORG#{org_id}#SHIFTS"


def elder_pk(elder_id: str) -> str:
    return f"ELDER#{elder_id}"


def visit_sk(visit: Visit) -> str:
    return f"VISIT#{visit.started_at.isoformat()}#{visit.id}"


class DynamoStore(Store):
    """One instance per request. Collections are fetched once and cached for that request.

    Caching for the life of the instance rather than the process is the point. A Lambda
    container is reused across invocations, and a store that remembered yesterday's alerts
    would serve them as today's.
    """

    def __init__(self, org_id: str = ORG_ID, table_name: str | None = None) -> None:
        self.org_id_value = org_id
        self.table = table(table_name)
        self._org: dict | None = None
        self._by_entity: dict[str, list] | None = None
        self._shifts: list[Shift] | None = None
        self._visits: list[Visit] | None = None
        self._visits_by_elder: dict[str, list[Visit]] = {}

    # -- loading -------------------------------------------------------------

    def _query(self, **kwargs) -> list[dict]:
        items: list[dict] = []
        while True:
            page = self.table.query(**kwargs)
            items.extend(page.get("Items", []))
            token = page.get("LastEvaluatedKey")
            if not token:
                return items
            kwargs = {**kwargs, "ExclusiveStartKey": token}

    def _load_org_partition(self) -> dict[str, list]:
        """Org metadata, elders, volunteers and alerts, in one query."""
        if self._by_entity is not None:
            return self._by_entity
        from boto3.dynamodb.conditions import Key

        items = self._query(KeyConditionExpression=Key("PK").eq(org_pk(self.org_id_value)))
        grouped: dict[str, list] = {"elder": [], "volunteer": [], "alert": []}
        for item in items:
            kind = item.get("entity")
            if kind == "org":
                self._org = _undecimal({k: v for k, v in item.items() if k not in _KEYS})
            elif kind in grouped:
                grouped[kind].append(item)
        if self._org is None:
            raise LookupError(
                f"organization {self.org_id_value!r} is not in table {self.table.name!r}; "
                "run scripts/load_seed.py first"
            )
        self._by_entity = grouped
        return grouped

    # -- identity ------------------------------------------------------------

    @property
    def organization(self) -> dict:
        self._load_org_partition()
        assert self._org is not None
        return self._org["organization"]

    @property
    def generated_for(self) -> str:
        self._load_org_partition()
        assert self._org is not None
        return self._org["generated_for"]

    @property
    def org_id(self) -> str:
        return self.org_id_value

    # -- collections ---------------------------------------------------------

    @property
    def elders(self) -> list[Elder]:
        return [from_item(Elder, i) for i in self._load_org_partition()["elder"]]

    @property
    def volunteers(self) -> list[Volunteer]:
        return [from_item(Volunteer, i) for i in self._load_org_partition()["volunteer"]]

    @property
    def alerts(self) -> list[Alert]:
        return [from_item(Alert, i) for i in self._load_org_partition()["alert"]]

    @property
    def shifts(self) -> list[Shift]:
        if self._shifts is None:
            from boto3.dynamodb.conditions import Key

            items = self._query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq(f"ORG#{self.org_id_value}#SHIFT"),
            )
            self._shifts = [from_item(Shift, i) for i in items]
        return self._shifts

    @property
    def visits(self) -> list[Visit]:
        """Every visit in the organization. Used by the nightly sweep, not by a screen."""
        if self._visits is None:
            from boto3.dynamodb.conditions import Key

            items = self._query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq(f"ORG#{self.org_id_value}#VISIT"),
            )
            self._visits = [from_item(Visit, i) for i in items]
        return self._visits

    def visits_for(self, elder_id: str) -> list[Visit]:
        """One query, already sorted. This is why visits are keyed under the person."""
        if elder_id not in self._visits_by_elder:
            from boto3.dynamodb.conditions import Key

            items = self._query(
                KeyConditionExpression=Key("PK").eq(elder_pk(elder_id))
                & Key("SK").begins_with("VISIT#")
            )
            self._visits_by_elder[elder_id] = [from_item(Visit, i) for i in items]
        return self._visits_by_elder[elder_id]

    # -- writes --------------------------------------------------------------

    def add_visit(self, visit: Visit) -> Visit:
        item = to_item(
            visit,
            PK=elder_pk(visit.elder_id),
            SK=visit_sk(visit),
            GSI1PK=f"ORG#{self.org_id_value}#VISIT",
            GSI1SK=f"{visit.started_at.isoformat()}#{visit.id}",
            entity="visit",
        )
        if not visit.shift_id:
            self.table.put_item(Item=item)
        else:
            # The visit and the shift it closes land together or not at all. A logged visit
            # against a shift still showing as open is what makes a coordinator chase
            # somebody who already went.
            client().transact_write_items(
                TransactItems=[
                    {"Put": {"TableName": self.table.name, "Item": _serialize(item)}},
                    {
                        "Update": {
                            "TableName": self.table.name,
                            "Key": _serialize(
                                {
                                    "PK": shifts_pk(self.org_id_value),
                                    "SK": f"SHIFT#{visit.shift_id}",
                                }
                            ),
                            "UpdateExpression": (
                                "SET #s = :logged, volunteer_id = "
                                "if_not_exists(volunteer_id, :vol)"
                            ),
                            "ExpressionAttributeNames": {"#s": "status"},
                            "ExpressionAttributeValues": _serialize(
                                {":logged": "logged", ":vol": visit.volunteer_id}
                            ),
                        }
                    },
                ]
            )
        self._visits = None
        self._visits_by_elder.pop(visit.elder_id, None)
        self._shifts = None
        return visit

    def claim_shift(self, shift_id: str, volunteer_id: str) -> Shift:
        try:
            result = self.table.update_item(
                Key={"PK": shifts_pk(self.org_id_value), "SK": f"SHIFT#{shift_id}"},
                UpdateExpression="SET volunteer_id = :vol, #s = :claimed",
                ConditionExpression="attribute_exists(SK) AND attribute_not_exists(volunteer_id)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":vol": volunteer_id, ":claimed": "claimed"},
                ReturnValues="ALL_NEW",
                ReturnValuesOnConditionCheckFailure="ALL_OLD",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # The same condition covers "already taken" and "never existed". The caller
                # needs to tell them apart: one is a message, the other is a bug.
                if not exc.response.get("Item"):
                    raise StopIteration(shift_id) from exc
                raise ShiftAlreadyClaimed(shift_id) from exc
            raise
        self._shifts = None
        return from_item(Shift, result["Attributes"])

    def save_alert(self, alert: Alert) -> Alert:
        self.table.put_item(
            Item=to_item(
                alert,
                PK=org_pk(self.org_id_value),
                SK=f"ALERT#{alert.id}",
                GSI1PK=f"ORG#{self.org_id_value}#ALERT#{alert.status}",
                GSI1SK=alert.opened_at.isoformat(),
                entity="alert",
            )
        )
        self._by_entity = None
        return alert

    def set_alert_status(self, alert_id: str, status: str, by: str | None = None) -> Alert:
        values: dict[str, Any] = {
            ":s": status,
            ":g": f"ORG#{self.org_id_value}#ALERT#{status}",
            ":by": by or "",
        }
        result = self.table.update_item(
            Key={"PK": org_pk(self.org_id_value), "SK": f"ALERT#{alert_id}"},
            UpdateExpression="SET #s = :s, GSI1PK = :g, acknowledged_by = :by",
            ConditionExpression="attribute_exists(SK)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        self._by_entity = None
        return from_item(Alert, result["Attributes"])

    def save_elder(self, elder: Elder) -> Elder:
        self.table.put_item(
            Item=to_item(
                elder, PK=org_pk(self.org_id_value), SK=f"ELDER#{elder.id}", entity="elder"
            )
        )
        self._by_entity = None
        return elder

    def save_volunteer(self, volunteer: Volunteer) -> Volunteer:
        self.table.put_item(
            Item=to_item(
                volunteer,
                PK=org_pk(self.org_id_value),
                SK=f"VOL#{volunteer.id}",
                entity="volunteer",
            )
        )
        self._by_entity = None
        return volunteer

    def save_shift(self, shift: Shift) -> Shift:
        self.table.put_item(
            Item=to_item(
                shift,
                PK=shifts_pk(self.org_id_value),
                SK=f"SHIFT#{shift.id}",
                GSI1PK=f"ORG#{self.org_id_value}#SHIFT",
                GSI1SK=shift.scheduled_at.isoformat(),
                entity="shift",
            )
        )
        self._shifts = None
        return shift

    # -- generated prose -----------------------------------------------------

    def get_brief(self, elder_id: str, as_of: date, locale: str) -> Brief | None:
        item = self.table.get_item(
            Key={"PK": elder_pk(elder_id), "SK": f"BRIEF#{as_of.isoformat()}#{locale}"}
        ).get("Item")
        return from_item(Brief, item) if item else None

    def save_brief(self, brief: Brief, as_of: date) -> Brief:
        item = to_item(
            brief,
            PK=elder_pk(brief.elder_id),
            SK=f"BRIEF#{as_of.isoformat()}#{brief.locale}",
            entity="brief",
        )
        # Two days, not one. A brief written at eleven at night is still the right brief for
        # the volunteer knocking at eight the next morning.
        item["expires_at"] = int(time.time()) + 2 * 86400
        self.table.put_item(Item=item)
        return brief

    def save_organization(self, organization: dict, generated_for: str) -> None:
        self.table.put_item(
            Item={
                "PK": org_pk(self.org_id_value),
                "SK": "META",
                "entity": "org",
                "organization": organization,
                "generated_for": generated_for,
            }
        )
        self._by_entity = None


def _serialize(value: dict) -> dict:
    """Resource-level dicts to client-level AttributeValues, for transactions only.

    `transact_write_items` is a client call and does not accept the plain Python the resource
    interface takes everywhere else, so this bridges exactly at that seam.
    """
    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in value.items()}
