# app/schemas/auth.py
from datetime import date, datetime
from pydantic import BaseModel, validator


def _parse_birth_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            raise ValueError("Doğum tarihi GG-AA-YYYY formatında olmalı")
    raise ValueError("Geçersiz doğum tarihi")

class ParentLoginRequest(BaseModel):
    email: str
    password: str

class ParentLoginResponse(BaseModel):
    token: str
    refreshToken: str | None = None
    deviceId: str | None = None
    userId: str 


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    birth_date: date | None = None

    _normalize_birth_date = validator("birth_date", pre=True, allow_reuse=True)(_parse_birth_date)

    class Config:
        json_encoders = {date: lambda v: v.strftime("%d-%m-%Y")}


class RegisterResponse(BaseModel):
    userId: str
    deviceId: str | None = None


class ProfileResponse(BaseModel):
    userId: str
    email: str
    full_name: str | None = None
    birth_date: date | None = None

    class Config:
        json_encoders = {date: lambda v: v.strftime("%d-%m-%Y")}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    birth_date: date | None = None

    _normalize_birth_date = validator("birth_date", pre=True, allow_reuse=True)(_parse_birth_date)

    class Config:
        json_encoders = {date: lambda v: v.strftime("%d-%m-%Y")}


class ResendVerificationRequest(BaseModel):
    email: str