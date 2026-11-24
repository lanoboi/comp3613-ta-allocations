from typing import Optional

from sqlmodel import Field, SQLModel


class ChangeLog(SQLModel, table=True):
    __tablename__ = "change_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    action: str
    assignment_id: int
    ta_id: int
    course_id: int
    weekly_hours: int
    note: str = ""
    created_at: str
