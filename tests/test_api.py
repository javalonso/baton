"""The API, end to end, without touching Bedrock or AWS.

The store is a writable copy of the seed and the two model calls are stubbed, so these tests
say something about routing, authorization and shape rather than about the models. The
models have their own tests.

The authorization tests are the point of this file. Everything else here would be caught by
opening the app; a volunteer who can read the coordinator's screen would not be.
"""

from __future__ import annotations

import shutil
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from core.models import Brief, Extraction, Observation
from core.store import DEFAULT_PATH, JsonStore


@pytest.fixture
def store(tmp_path) -> JsonStore:
    path = tmp_path / "world.json"
    shutil.copy(DEFAULT_PATH, path)
    return JsonStore(path, writable=True)


@pytest.fixture
def client(store, monkeypatch) -> TestClient:
    from api.deps import get_store
    from api.main import app

    app.dependency_overrides[get_store] = lambda: store

    def fake_extract(transcript: str, agent=None) -> Extraction:
        return Extraction(
            source_lang="es",
            observations=[
                Observation(
                    category="food",
                    summary="ate less than usual",
                    trend="worse",
                    confidence="clear",
                    quote="casi no comio",
                )
            ],
            followups=["buy milk"],
        )

    monkeypatch.setattr("agents.intake.extract", fake_extract)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _as_of(store: JsonStore) -> date:
    return date.fromisoformat(store.generated_for)


def _volunteer_with_work(store: JsonStore):
    """A volunteer who has a shift on the dataset's today. The demo depends on one existing."""
    as_of = _as_of(store)
    shift = next(
        s for s in store.shifts if s.volunteer_id and s.scheduled_at.date() == as_of
    )
    return store.volunteer(shift.volunteer_id), shift


def _login(client: TestClient, code: str) -> dict:
    response = client.post("/auth/login", json={"code": code})
    assert response.status_code == 200, response.text
    return response.json()


def _volunteer_session(client: TestClient, store: JsonStore):
    from api.auth import code_for

    volunteer, shift = _volunteer_with_work(store)
    session = _login(client, code_for(volunteer.id))
    return session, volunteer, shift


def _coordinator_session(client: TestClient, store: JsonStore):
    from api.auth import coordinator_code

    return _login(client, coordinator_code(store.org_id))


def _auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['token']}"}


# -- getting in --------------------------------------------------------------


def test_a_wrong_code_says_nothing_useful(client: TestClient):
    response = client.post("/auth/login", json={"code": "000000"})
    assert response.status_code == 401
    assert "volunteer" not in response.json()["detail"].lower()


def test_a_volunteer_code_returns_that_volunteer(client: TestClient, store: JsonStore):
    session, volunteer, _ = _volunteer_session(client, store)
    assert session["role"] == "volunteer"
    assert session["name"] == volunteer.name
    assert session["org"] == store.organization["name"]


def test_a_token_survives_into_the_next_request(client: TestClient, store: JsonStore):
    session, volunteer, _ = _volunteer_session(client, store)
    me = client.get("/auth/me", headers=_auth(session))
    assert me.status_code == 200
    assert me.json()["id"] == volunteer.id


def test_a_forged_token_is_simply_not_a_token(client: TestClient):
    assert client.get("/auth/me", headers={"Authorization": "Bearer nonsense.nonsense"}).status_code == 401


# -- the volunteer's four screens --------------------------------------------


def test_today_shows_only_my_own_rounds(client: TestClient, store: JsonStore):
    session, volunteer, _ = _volunteer_session(client, store)
    body = client.get("/me/today", headers=_auth(session)).json()
    assert body["volunteer"] == volunteer.name
    assert body["shifts"]
    assert all(s["volunteer_id"] == volunteer.id for s in body["shifts"])
    assert [s["scheduled_at"] for s in body["shifts"]] == sorted(
        s["scheduled_at"] for s in body["shifts"]
    )


def test_a_card_carries_the_name_not_an_id(client: TestClient, store: JsonStore):
    session, _, _ = _volunteer_session(client, store)
    body = client.get("/me/today", headers=_auth(session)).json()
    person = body["people"][0]
    assert person["name"] and not person["name"].startswith("elder-")
    assert person["last_visit_by"] == "" or not person["last_visit_by"].startswith("vol-")


def test_recording_a_note_returns_chips_to_correct(client: TestClient, store: JsonStore):
    session, _, shift = _volunteer_session(client, store)
    response = client.post(
        "/me/visits",
        headers=_auth(session),
        json={"elder_id": shift.elder_id, "shift_id": shift.id, "transcript": "casi no comio"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["observations"][0]["quote"] == "casi no comio"
    assert body["followups"] == ["buy milk"]
    assert store.shift(shift.id).status == "logged"


def test_the_volunteers_correction_is_what_the_record_keeps(client: TestClient, store: JsonStore):
    session, _, shift = _volunteer_session(client, store)
    created = client.post(
        "/me/visits",
        headers=_auth(session),
        json={"elder_id": shift.elder_id, "shift_id": shift.id, "transcript": "casi no comio"},
    ).json()

    corrected = {
        "category": "mood",
        "summary": "quieter than usual",
        "trend": "worse",
        "confidence": "clear",
        "quote": "casi no comio",
    }
    response = client.patch(
        f"/me/visits/{created['visit_id']}",
        headers=_auth(session),
        json={"observations": [corrected], "followups": []},
    )
    assert response.status_code == 200, response.text
    stored = next(v for v in store.visits if v.id == created["visit_id"])
    assert stored.confirmed is True
    assert [o.category.value for o in stored.observations] == ["mood"]


def test_a_volunteer_cannot_record_against_somebody_elses_person(
    client: TestClient, store: JsonStore
):
    session, volunteer, _ = _volunteer_session(client, store)
    strangers = [
        e.id
        for e in store.elders
        if not any(s.elder_id == e.id and s.volunteer_id == volunteer.id for s in store.shifts)
        and not any(v.volunteer_id == volunteer.id for v in store.visits_for(e.id))
    ]
    if not strangers:
        pytest.skip("this volunteer has been everywhere")
    response = client.post(
        "/me/visits",
        headers=_auth(session),
        json={"elder_id": strangers[0], "transcript": "todo bien"},
    )
    assert response.status_code == 403


def test_open_shifts_are_soonest_first_and_within_the_week(client: TestClient, store: JsonStore):
    session, _, _ = _volunteer_session(client, store)
    body = client.get("/me/shifts/open", headers=_auth(session)).json()
    times = [s["scheduled_at"] for s in body]
    assert times == sorted(times)
    assert all(s["volunteer_id"] is None for s in body)


def test_claiming_is_one_tap_and_the_second_tap_is_told_no(client: TestClient, store: JsonStore):
    from api.auth import code_for

    session, _, _ = _volunteer_session(client, store)
    gaps = client.get("/me/shifts/open", headers=_auth(session)).json()
    if not gaps:
        pytest.skip("no open shifts in the seed window")

    first = client.post(f"/me/shifts/{gaps[0]['id']}/claim", headers=_auth(session))
    assert first.status_code == 200, first.text

    other = next(v for v in store.volunteers if v.id != session["id"] and v.active)
    second_session = _login(client, code_for(other.id))
    second = client.post(f"/me/shifts/{gaps[0]['id']}/claim", headers=_auth(second_session))
    assert second.status_code == 409
    assert store.shift(gaps[0]["id"]).volunteer_id == session["id"]


def test_the_brief_is_the_agents_prose_with_the_facts_beside_it(
    client: TestClient, store: JsonStore, monkeypatch
):
    session, _, shift = _volunteer_session(client, store)
    monkeypatch.setattr(
        "agents.brief.write",
        lambda elder_id, store=None, as_of=None, locale="es": Brief(
            elder_id=elder_id,
            locale=locale,
            since_last_visit="Ha comido menos.",
            watch_for="Si sigue sin comer.",
            how_to_be_with_them="Hablar despacio.",
            generated_at=datetime(2026, 9, 14, 8, 0),
        ),
    )
    body = client.get(f"/me/elders/{shift.elder_id}/brief", headers=_auth(session)).json()
    assert body["brief"]["since_last_visit"] == "Ha comido menos."
    assert body["elder_name"] == store.elder(shift.elder_id).name


# -- the coordinator's five screens ------------------------------------------


def test_c1_shows_the_people_off_pattern(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    body = client.get("/coordinator/today", headers=_auth(session)).json()
    assert body["organization"] == store.organization["name"]
    assert body["people_checked"] == len(store.elders)
    assert {a["elder_id"] for a in body["alerts"]} == {"elder-01", "elder-02"}
    assert body["quiet"] is False


def test_an_alert_carries_the_quotes_that_produced_it(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    today = client.get("/coordinator/today", headers=_auth(session)).json()
    alert_id = today["alerts"][0]["id"]
    detail = client.get(f"/coordinator/alerts/{alert_id}", headers=_auth(session)).json()
    assert detail["alert"]["evidence"]
    assert all(e["quote"] for e in detail["alert"]["evidence"])
    assert detail["timeline"]


def test_acknowledging_an_alert_takes_it_off_the_landing_screen(
    client: TestClient, store: JsonStore
):
    session = _coordinator_session(client, store)
    first = client.get("/coordinator/today", headers=_auth(session)).json()
    alert_id = first["alerts"][0]["id"]

    decided = client.post(f"/coordinator/alerts/{alert_id}/acknowledge", headers=_auth(session))
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "acknowledged"

    again = client.get("/coordinator/today", headers=_auth(session)).json()
    assert alert_id not in {a["id"] for a in again["alerts"]}


def test_a_dismissed_alert_does_not_come_back_tomorrow(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    alert_id = client.get("/coordinator/today", headers=_auth(session)).json()["alerts"][0]["id"]
    client.post(f"/coordinator/alerts/{alert_id}/dismiss", headers=_auth(session))
    again = client.get("/coordinator/today", headers=_auth(session)).json()
    assert alert_id not in {a["id"] for a in again["alerts"]}


def test_the_person_record_is_the_living_one(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    body = client.get("/coordinator/elders/elder-01", headers=_auth(session)).json()
    assert body["name"]
    assert body["timeline"]
    assert body["visits_counted"] > 0
    assert body["baseline"]


def test_coverage_makes_the_imbalance_countable(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    body = client.get("/coordinator/coverage", headers=_auth(session)).json()
    loads = [row["visits"] for row in body["load"]]
    assert loads == sorted(loads, reverse=True)
    assert body["open_count"] == sum(1 for s in body["shifts"] if s["volunteer_id"] is None)


def test_the_weekly_report_counts_the_week_not_the_dataset(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    body = client.get("/coordinator/report/weekly", headers=_auth(session)).json()
    assert 0 < body["visits_logged"] < len(store.visits)
    assert body["people_seen"] <= len(store.elders)
    assert len(body["busiest"]) <= 5


def test_the_handoff_sheet_comes_back_as_a_pdf(client: TestClient, store: JsonStore, monkeypatch):
    session = _coordinator_session(client, store)
    monkeypatch.setattr(
        "agents.brief.write",
        lambda elder_id, store=None, as_of=None, locale="es": Brief(
            elder_id=elder_id,
            locale=locale,
            since_last_visit="Ha comido menos.",
            watch_for="Si sigue sin comer.",
            how_to_be_with_them="Hablar despacio.",
            generated_at=datetime(2026, 9, 14, 8, 0),
        ),
    )
    response = client.get("/coordinator/elders/elder-01/handoff.pdf", headers=_auth(session))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# -- who is allowed where ----------------------------------------------------


def test_a_volunteer_cannot_open_the_coordinator_portal(client: TestClient, store: JsonStore):
    session, _, _ = _volunteer_session(client, store)
    for path in ("/coordinator/today", "/coordinator/elders/elder-01", "/coordinator/coverage"):
        assert client.get(path, headers=_auth(session)).status_code == 403, path


def test_the_coordinator_is_not_a_volunteer(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    assert client.get("/me/today", headers=_auth(session)).status_code == 403


def test_nothing_is_readable_without_a_token(client: TestClient):
    for path in ("/me/today", "/coordinator/today", "/me/shifts/open"):
        assert client.get(path).status_code == 401, path


def test_the_scheduled_endpoints_refuse_a_browser(client: TestClient, store: JsonStore):
    session = _coordinator_session(client, store)
    assert client.post("/internal/watch", headers=_auth(session)).status_code == 401
    assert client.post("/internal/roster").status_code == 401


def test_the_language_is_resolved_at_the_edge(client: TestClient, store: JsonStore):
    session, _, _ = _volunteer_session(client, store)
    gaps = client.get("/me/shifts/open", headers=_auth(session)).json()
    if not gaps:
        pytest.skip("no open shifts in the seed window")
    english = client.post(
        f"/me/shifts/{gaps[0]['id']}/claim?lang=en", headers=_auth(session)
    ).json()
    assert english["message"] == "Done, it is yours."


def test_a_missing_shift_is_a_404_not_a_conflict(client: TestClient, store: JsonStore):
    session, _, _ = _volunteer_session(client, store)
    assert client.post("/me/shifts/shift-does-not-exist/claim", headers=_auth(session)).status_code == 404
