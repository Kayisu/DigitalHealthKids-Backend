# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import secrets

from app.db import get_db
from app.models.core import User
from app.schemas.auth import ParentLoginRequest, ParentLoginResponse

router = APIRouter()


@router.post("/login", response_model=ParentLoginResponse)
def parent_login(
    payload: ParentLoginRequest,
    db: Session = Depends(get_db),
) -> ParentLoginResponse:
    """
    Şimdilik:
    - Email ile USER tablosundan parent buluyoruz
    - Parola kontrolü yok (MVP)
    - childId olarak parent.id döndürüyoruz
      (ileri aşamada gerçek child tablosuna geçeceğiz)
    """
    # 1) Kullanıcıyı email ile bul
    user = (
        db.query(User)
        .filter(User.email == payload.email)
        .first()
    )

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2) Şimdilik parolayı kontrol etmiyoruz (MVP'de dummy)
    # İstersen burada payload.password == "123456" check'i koyarsın.

    # 3) Dummy token üret
    token = secrets.token_hex(32)

    return ParentLoginResponse(
        token=token,
        refreshToken=None,
        childId=str(user.id),  # 🔑 Şimdilik childId = users.id
    )
