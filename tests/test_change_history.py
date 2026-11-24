import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed

client = TestClient(app)
HOD = {"X-User-Id": "1"}


@pytest.fixture(autouse=True)
def fresh_db():
    seed(reset=True)


def history():
    return client.get("/api/history").json()["history"]


def test_manual_assign_is_recorded_with_user():
    client.post(
        "/api/assignments/manual",
        headers=HOD,
        json={"ta_id": 2, "course_id": 2, "weekly_hours": 4},
    )
    entry = history()[0]
    assert entry["action"] == "create"
    assert entry["user_id"] == 1
    assert entry["ta_id"] == 2
    assert entry["created_at"] != ""


def test_edit_and_remove_are_recorded():
    client.patch("/api/assignments/1", headers=HOD, json={"weekly_hours": 10})
    client.delete("/api/assignments/1", headers=HOD)
    entries = history()
    assert entries[0]["action"] == "remove"
    assert entries[1]["action"] == "edit"
    assert entries[1]["note"] == "from 18 to 10 hours"


def test_confirm_of_second_ta_is_recorded_as_override():
    s = client.post(
        "/api/assignments/suggest",
        headers=HOD,
        json={"course_id": 2, "weekly_hours": 2, "mode": "experience_first"},
    ).json()
    second = s["ranked"][1]["ta_id"]
    client.post(
        "/api/assignments/confirm",
        headers=HOD,
        json={"suggestion_id": s["suggestion_id"], "ta_id": second},
    )
    entry = history()[0]
    assert entry["action"] == "confirm"
    assert entry["ta_id"] == second
    assert "override" in entry["note"]


def test_refused_change_is_not_recorded():
    client.post(
        "/api/assignments/manual",
        headers=HOD,
        json={"ta_id": 1, "course_id": 1, "weekly_hours": 5},
    )
    assert history() == []
