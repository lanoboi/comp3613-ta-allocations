import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.main import app
from app.models.department import Department
from app.seed import seed

client = TestClient(app)
HOD = {"X-User-Id": "1"}
ALEX_ASSIGNMENT = 1  # seed: Alex has 18 hours on COMP3613, budget 62


@pytest.fixture(autouse=True)
def fresh_db():
    seed(reset=True)


def budget():
    with Session(engine) as s:
        return s.get(Department, 1).budget_hours_remaining


def edit(assignment_id, hours, headers=HOD):
    return client.patch(
        f"/api/assignments/{assignment_id}", headers=headers, json={"weekly_hours": hours}
    )


def test_edit_up_to_the_cap_is_allowed():
    r = edit(ALEX_ASSIGNMENT, 20)
    assert r.status_code == 200
    assert r.json()["assignment"]["weekly_hours"] == 20
    assert budget() == 60


def test_edit_over_the_cap_is_refused():
    r = edit(ALEX_ASSIGNMENT, 21)
    assert r.status_code == 400
    assert budget() == 62


def test_edit_down_gives_hours_back_to_budget():
    r = edit(ALEX_ASSIGNMENT, 10)
    assert r.status_code == 200
    assert budget() == 70


def test_edit_over_budget_is_refused():
    with Session(engine) as s:
        d = s.get(Department, 1)
        d.budget_hours_remaining = 0
        s.add(d)
        s.commit()
    r = edit(ALEX_ASSIGNMENT, 19)
    assert r.status_code == 400
    assert budget() == 0


def test_edit_missing_assignment_returns_404():
    assert edit(999, 5).status_code == 404


def test_only_hod_can_edit():
    r = edit(ALEX_ASSIGNMENT, 10, headers={"X-User-Id": "999"})
    assert r.status_code == 400
    assert budget() == 62
