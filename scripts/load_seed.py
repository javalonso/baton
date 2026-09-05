"""Load the seed dataset into DynamoDB.

Idempotent: every row is a `PutItem` on a deterministic key, so running it twice leaves the
table exactly as running it once did. That matters because this is the script somebody runs
when the demo looks wrong five minutes before recording.

    python scripts/load_seed.py                 # into the default table
    python scripts/load_seed.py --table baton-dev --wipe
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.dynamo import (  # noqa: E402
    DynamoStore,
    elder_pk,
    org_pk,
    shifts_pk,
    table,
    to_item,
    visit_sk,
)
from core.store import DEFAULT_PATH, JsonStore  # noqa: E402


def wipe(table_name: str, org_id: str) -> int:
    """Delete every row this organization owns. Leaves other organizations alone."""
    from boto3.dynamodb.conditions import Key

    handle = table(table_name)
    removed = 0
    partitions = [org_pk(org_id), shifts_pk(org_id)]
    source = JsonStore(DEFAULT_PATH)
    partitions += [elder_pk(e.id) for e in source.elders]
    for pk in partitions:
        start = None
        while True:
            kwargs = {"KeyConditionExpression": Key("PK").eq(pk)}
            if start:
                kwargs["ExclusiveStartKey"] = start
            page = handle.query(**kwargs)
            with handle.batch_writer() as batch:
                for item in page.get("Items", []):
                    batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                    removed += 1
            start = page.get("LastEvaluatedKey")
            if not start:
                break
    return removed


def load(table_name: str, path: Path) -> dict[str, int]:
    source = JsonStore(path)
    org_id = source.organization["id"]
    store = DynamoStore(org_id=org_id, table_name=table_name)
    store.save_organization(source.organization, source.generated_for)

    handle = table(table_name)
    counts = {"elders": 0, "volunteers": 0, "visits": 0, "shifts": 0, "alerts": 0}
    with handle.batch_writer() as batch:
        for elder in source.elders:
            batch.put_item(
                Item=to_item(elder, PK=org_pk(org_id), SK=f"ELDER#{elder.id}", entity="elder")
            )
            counts["elders"] += 1
        for volunteer in source.volunteers:
            batch.put_item(
                Item=to_item(
                    volunteer, PK=org_pk(org_id), SK=f"VOL#{volunteer.id}", entity="volunteer"
                )
            )
            counts["volunteers"] += 1
        for visit in source.visits:
            batch.put_item(
                Item=to_item(
                    visit,
                    PK=elder_pk(visit.elder_id),
                    SK=visit_sk(visit),
                    GSI1PK=f"ORG#{org_id}#VISIT",
                    GSI1SK=f"{visit.started_at.isoformat()}#{visit.id}",
                    entity="visit",
                )
            )
            counts["visits"] += 1
        for shift in source.shifts:
            batch.put_item(
                Item=to_item(
                    shift,
                    PK=shifts_pk(org_id),
                    SK=f"SHIFT#{shift.id}",
                    GSI1PK=f"ORG#{org_id}#SHIFT",
                    GSI1SK=shift.scheduled_at.isoformat(),
                    entity="shift",
                )
            )
            counts["shifts"] += 1
        for alert in source.alerts:
            batch.put_item(
                Item=to_item(
                    alert,
                    PK=org_pk(org_id),
                    SK=f"ALERT#{alert.id}",
                    GSI1PK=f"ORG#{org_id}#ALERT#{alert.status}",
                    GSI1SK=alert.opened_at.isoformat(),
                    entity="alert",
                )
            )
            counts["alerts"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=None, help="table name (default: $BATON_TABLE or baton)")
    parser.add_argument("--data", default=DEFAULT_PATH, type=Path)
    parser.add_argument("--wipe", action="store_true", help="delete this org's rows first")
    args = parser.parse_args()

    source = JsonStore(args.data)
    org_id = source.organization["id"]
    if args.wipe:
        print(f"wiped {wipe(args.table, org_id)} rows")
    counts = load(args.table, args.data)
    print(f"loaded into {args.table or 'baton'}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))

    check = DynamoStore(org_id=org_id, table_name=args.table)
    print(
        f"verified: {len(check.elders)} elders, {len(check.volunteers)} volunteers, "
        f"{len(check.visits)} visits, {len(check.shifts)} shifts, as of {check.generated_for}"
    )


if __name__ == "__main__":
    main()
