# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import secrets
from datetime import datetime # <-- Eklendi

from app.db import get_db
from app.models.core import User, Device # <-- Device Eklendi
from app.schemas.auth import ParentLoginRequest, ParentLoginResponse

router = APIRouter()

@router.post("/login", response_model=ParentLoginResponse)
def parent_login(
    payload: ParentLoginRequest,
    db: Session = Depends(get_db),
) -> ParentLoginResponse:
    # 1) Kullanıcıyı bul
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2) CİHAZ KONTROLÜ (GÜNCELLEME BURADA)
    # Kullanıcının daha önce kayıtlı bir Android cihazı var mı?
    existing_device = (
        db.query(Device)
        .filter(Device.user_id == user.id)
        .filter(Device.platform == "android")
        .first()
    )

    if existing_device:
        # Varsa onu kullan
        target_device = existing_device
    else:
        # Yoksa yeni oluştur
        new_device = Device(
            user_id=user.id,
            platform="android",
            model="User Device (Auto)",
            os_version="13.0",
            enrolled_at=datetime.utcnow()
        )
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        target_device = new_device

    # 3) Token üret
    token = secrets.token_hex(32)

    return ParentLoginResponse(
        token=token,
        refreshToken=None,
        deviceId=str(target_device.id)  # <-- Artık sabit cihaz ID'si dönecek
    )