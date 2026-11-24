import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed

client = TestClient(app)
HOD = {"X-User-Id": "1"}
ALEX_ASSIGNMENT = 1  # seed: Alex has 18 hours on COMP3613, budget 62


@pytest.fixture(autouse=True)
def fresh_db():
    seed(reset=True)


def remove(assignment_id, headers=HOD):
    return client.delete(f"/api/assignments/{assignment_id}", headers=headers)


def alex_hours(board):
    for t in board["tas"]:
        if t["id"] == 1:
            return t["weekly_hours_used"]
    return None


def test_remove_gives_hours_back():
    r = remove(ALEX_ASSIGNMENT)
    assert r.status_code == 200
    board = client.get("/api/review").json()
    assert board["budget_hours_remaining"] == 80
    assert alex_hours(board) == 0
    assert board["assignments"] == []


def test_removed_ta_can_be_assigned_again():
    remove(ALEX_ASSIGNMENT)
    r = client.post(
        "/api/assignments/manual",
        headers=HOD,
        json={"ta_id": 1, "course_id": 1, "weekly_hours": 20},
    )
    assert r.status_code == 200


def test_remove_missing_assignment_returns_404():
    assert remove(999).status_code == 404


def test_only_hod_can_remove():
    r = remove(ALEX_ASSIGNMENT, headers={"X-User-Id": "999"})
    assert r.status_code == 400
    assert len(client.get("/api/review").json()["assignments"]) == 1
