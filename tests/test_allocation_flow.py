import random

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.database import engine
from app.main import app
from app.models.assignment import Assignment
from app.models.department import Department
from app.seed import seed

client = TestClient(app)
HOD = {"X-User-Id": "1"}
# seed data: Alex already has 18 hours on COMP3613, budget starts at 62
ALEX, BLAIR, CASEY = 1, 2, 3
COMP3613, COMP2602, COMP1601 = 1, 2, 3


@pytest.fixture(autouse=True)
def fresh_db():
    seed(reset=True)


def assignment_count():
    with Session(engine) as s:
        return s.exec(select(func.count()).select_from(Assignment)).one()


def budget():
    with Session(engine) as s:
        return s.get(Department, 1).budget_hours_remaining


def set_budget(hours):
    with Session(engine) as s:
        d = s.get(Department, 1)
        d.budget_hours_remaining = hours
        s.add(d)
        s.commit()


def manual(ta_id, course_id, hours):
    return client.post(
        "/api/assignments/manual",
        headers=HOD,
        json={"ta_id": ta_id, "course_id": course_id, "weekly_hours": hours},
    )


def suggest(course_id, hours, mode):
    return client.post(
        "/api/assignments/suggest",
        headers=HOD,
        json={"course_id": course_id, "weekly_hours": hours, "mode": mode},
    )


def confirm(suggestion_id, ta_id):
    return client.post(
        "/api/assignments/confirm",
        headers=HOD,
        json={"suggestion_id": suggestion_id, "ta_id": ta_id},
    )


def ranked_ids(resp):
    return [c["ta_id"] for c in resp.json()["ranked"]]



def test_manual_assign_within_limits_saves_and_lowers_budget():
    r = manual(ALEX, COMP3613, 2)
    assert r.status_code == 200
    assert budget() == 60


def test_manual_assign_over_weekly_cap_is_refused():
    before = assignment_count()
    r = manual(ALEX, COMP3613, 3)
    assert r.status_code == 400
    assert assignment_count() == before
    assert budget() == 62


def test_manual_assign_over_budget_is_refused():
    set_budget(5)
    r = manual(BLAIR, COMP2602, 6)
    assert r.status_code == 400
    assert budget() == 5



def test_suggest_leaves_out_ta_who_would_go_over_cap():
    r = suggest(COMP3613, 3, "least_loaded")
    assert r.status_code == 200
    assert ALEX not in ranked_ids(r)


def test_suggest_leaves_out_everyone_when_budget_cannot_cover_hours():
    set_budget(2)
    r = suggest(COMP2602, 3, "least_loaded")
    assert r.status_code == 400


def test_suggest_saves_no_assignment():
    before = assignment_count()
    assert suggest(COMP2602, 4, "experience_first").status_code == 200
    assert assignment_count() == before
    assert budget() == 62


def test_experience_first_ranks_experienced_ta_first_but_keeps_others():
    r = suggest(COMP2602, 2, "experience_first")
    assert ranked_ids(r)[0] == BLAIR
    assert set(ranked_ids(r)) == {ALEX, BLAIR, CASEY}


def test_unknown_mode_is_rejected():
    r = suggest(COMP3613, 2, "cheapest")
    assert r.status_code == 400
    assert "unknown mode" in r.json()["detail"]



def test_confirm_top_ta_saves_only_that_ta_and_is_not_an_override():
    s = suggest(COMP2602, 4, "experience_first")
    sid, top = s.json()["suggestion_id"], ranked_ids(s)[0]
    before = assignment_count()
    r = confirm(sid, top)
    assert r.status_code == 200
    assert r.json()["assignment"]["ta_id"] == top
    assert r.json()["override"] is False
    assert assignment_count() == before + 1
    assert budget() == 58


def test_confirm_second_ta_is_recorded_as_override():
    s = suggest(COMP2602, 4, "experience_first")
    sid, second = s.json()["suggestion_id"], ranked_ids(s)[1]
    r = confirm(sid, second)
    assert r.status_code == 200
    assert r.json()["assignment"]["ta_id"] == second
    assert r.json()["override"] is True
    saved = client.get(f"/api/suggestions/{sid}").json()["suggestion"]
    assert saved["override"] is True
    assert saved["confirmed_ta_id"] == second


def test_confirm_refused_when_ta_hours_changed_after_suggest():
    s = suggest(COMP1601, 5, "least_loaded")
    sid = s.json()["suggestion_id"]
    assert CASEY in ranked_ids(s)
    assert manual(CASEY, COMP2602, 16).status_code == 200
    before = assignment_count()
    r = confirm(sid, CASEY)
    assert r.status_code == 400
    assert "limits changed" in r.json()["detail"]
    assert assignment_count() == before


def test_confirm_refused_when_budget_changed_after_suggest():
    s = suggest(COMP1601, 5, "least_loaded")
    sid, top = s.json()["suggestion_id"], ranked_ids(s)[0]
    set_budget(3)
    r = confirm(sid, top)
    assert r.status_code == 400
    assert budget() == 3


def test_confirm_rejects_ta_not_in_suggestion():
    s = suggest(COMP3613, 3, "least_loaded")
    r = confirm(s.json()["suggestion_id"], ALEX)
    assert r.status_code == 400


def test_suggestion_can_only_be_confirmed_once():
    s = suggest(COMP2602, 2, "least_loaded")
    sid, top = s.json()["suggestion_id"], ranked_ids(s)[0]
    assert confirm(sid, top).status_code == 200
    assert confirm(sid, top).status_code == 400



def test_auto_endpoint_never_picks_ta_over_cap():
    r = client.post(
        "/api/assignments/auto",
        headers=HOD,
        json={"course_id": COMP3613, "weekly_hours": 3, "mode": "experience_first"},
    )
    assert r.status_code == 200
    assert r.json()["assignment"]["ta_id"] != ALEX



def test_cap_and_budget_hold_after_many_random_actions():
    rng = random.Random(3613)
    modes = ["experience_first", "least_loaded", "round_robin"]
    for _ in range(60):
        course = rng.choice([COMP3613, COMP2602, COMP1601])
        hours = rng.randint(1, 8)
        if rng.random() < 0.5:
            manual(rng.choice([ALEX, BLAIR, CASEY]), course, hours)
        else:
            s = suggest(course, hours, rng.choice(modes))
            if s.status_code == 200:
                confirm(s.json()["suggestion_id"], rng.choice(ranked_ids(s)))

    board = client.get("/api/review").json()
    assert all(t["weekly_hours_used"] <= 20 for t in board["tas"])
    assert board["budget_hours_remaining"] >= 0
