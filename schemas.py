"""Pydantic schemas for request validation and response serialization."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class RoleEnum(str, Enum):
    employee = "employee"
    manager = "manager"


class LeaveStatus(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    name: str
    role: RoleEnum


class EmployeeOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: RoleEnum

    class Config:
        from_attributes = True


class LeaveCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reason cannot be empty or just whitespace.")
        return value.strip()

    @model_validator(mode="after")
    def end_date_after_start_date(self) -> "LeaveCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date.")
        return self


class LeaveOut(BaseModel):
    id: int
    employee_id: int
    start_date: date
    end_date: date
    reason: str
    status: LeaveStatus

    class Config:
        from_attributes = True


class LeaveStatusUpdate(BaseModel):
    status: LeaveStatus
