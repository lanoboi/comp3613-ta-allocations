"""TA allocations scenario JSON API (OpenAPI /docs)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services import allocation_auth as auth
from app.services import allocations
from app.services.allocations import MODES

router = APIRouter(tags=["ta-allocations"])


class LoginBody(BaseModel):
    email: str
    password: str


class ManualAssignBody(BaseModel):
    ta_id: int
    course_id: int
    weekly_hours: int


class AutoAssignBody(BaseModel):
    course_id: int
    weekly_hours: int
    mode: str = Field(description=" | ".join(MODES))


class SuggestBody(BaseModel):
    course_id: int
    weekly_hours: int
    mode: str = Field(description=" | ".join(MODES))


class ConfirmBody(BaseModel):
    suggestion_id: int
    ta_id: int


class EditBody(BaseModel):
    weekly_hours: int


def _actor_id(x_user_id: str | None) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    try:
        return int(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-User-Id must be int") from exc


@router.post("/auth/login")
def login(body: LoginBody) -> dict[str, Any]:
    user = auth.login(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"user": user}


@router.get("/tas")
def tas() -> dict[str, Any]:
    return {"tas": allocations.list_tas()}


@router.get("/courses")
def courses() -> dict[str, Any]:
    return {"courses": allocations.list_courses()}


@router.get("/courses/{course_id}/candidates")
def candidates(course_id: int) -> dict[str, Any]:
    return {"candidates": allocations.highlight_candidates(course_id)}


@router.get("/assignments")
def assignments() -> dict[str, Any]:
    return {"assignments": allocations.list_assignments()}


@router.get("/review")
def review() -> dict[str, Any]:
    return allocations.review_board()


@router.post("/assignments/manual")
def manual(
    body: ManualAssignBody, x_user_id: str | None = Header(default=None)
) -> dict[str, Any]:
    result = allocations.assign_manual(
        _actor_id(x_user_id),
        ta_id=body.ta_id,
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/auto")
def auto(
    body: AutoAssignBody, x_user_id: str | None = Header(default=None)
) -> dict[str, Any]:
    result = allocations.assign_auto(
        _actor_id(x_user_id),
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
        mode=body.mode,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/suggest")
def suggest(body: SuggestBody, x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
    result = allocations.suggest(
        _actor_id(x_user_id),
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
        mode=body.mode,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/confirm")
def confirm(body: ConfirmBody, x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
    result = allocations.confirm(
        _actor_id(x_user_id), suggestion_id=body.suggestion_id, ta_id=body.ta_id
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/suggestions/{suggestion_id}")
def suggestion(suggestion_id: int) -> dict[str, Any]:
    row = allocations.get_suggestion(suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="suggestion not found")
    return {"suggestion": row}


@router.patch("/assignments/{assignment_id}")
def edit(
    assignment_id: int, body: EditBody, x_user_id: str | None = Header(default=None)
) -> dict[str, Any]:
    result = allocations.edit_assignment(
        _actor_id(x_user_id), assignment_id=assignment_id, weekly_hours=body.weekly_hours
    )
    if not result.get("ok"):
        status = 404 if result.get("error") == "assignment not found" else 400
        raise HTTPException(status_code=status, detail=result.get("error"))
    return result


@router.delete("/assignments/{assignment_id}")
def remove(assignment_id: int, x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
    result = allocations.remove_assignment(_actor_id(x_user_id), assignment_id=assignment_id)
    if not result.get("ok"):
        status = 404 if result.get("error") == "assignment not found" else 400
        raise HTTPException(status_code=status, detail=result.get("error"))
    return result


@router.get("/history")
def change_history() -> dict[str, Any]:
    return {"history": allocations.history()}
