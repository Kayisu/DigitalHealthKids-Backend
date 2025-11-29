# app/schemas/auth.py
from pydantic import BaseModel

class ParentLoginRequest(BaseModel):
    email: str
    password: str

class ParentLoginResponse(BaseModel):
    token: str
    refreshToken: str | None = None
    childId: str | None = None
