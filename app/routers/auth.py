# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import secrets
from datetime import datetime
from uuid import UUID

from app.db import get_db
from app.models.core import User, Device
from app.schemas.auth import (
    ParentLoginRequest,
    ParentLoginResponse,
    RegisterRequest,
    RegisterResponse,
    ProfileResponse,
    UpdateProfileRequest,
)
import hashlib

router = APIRouter()


def _hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post("/register", response_model=RegisterResponse)
def register_parent(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        birth_date=payload.birth_date,
        password_hash=_hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # cihaz oluştur
    device = Device(
        user_id=user.id,
        platform="android",
        model="User Device (Auto)",
        os_version="13.0",
        enrolled_at=datetime.utcnow()
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    return RegisterResponse(userId=str(user.id), deviceId=str(device.id))


@router.get("/profile/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)) -> ProfileResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse(
        userId=str(user.id),
        email=user.email,
        full_name=user.full_name,
        birth_date=user.birth_date,
    )


@router.put("/profile/{user_id}", response_model=ProfileResponse)
def update_profile(user_id: UUID, payload: UpdateProfileRequest, db: Session = Depends(get_db)) -> ProfileResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.birth_date is not None:
        user.birth_date = payload.birth_date

    db.add(user)
    db.commit()
    db.refresh(user)

    return ProfileResponse(
        userId=str(user.id),
        email=user.email,
        full_name=user.full_name,
        birth_date=user.birth_date,
    )

@router.post("/login", response_model=ParentLoginResponse)
def parent_login(
    payload: ParentLoginRequest,
    db: Session = Depends(get_db),
) -> ParentLoginResponse:
    # 1) Kullanıcıyı bul
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.password_hash != _hash_password(payload.password):
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
        deviceId=str(target_device.id),  # <-- Artık sabit cihaz ID'si dönecek
        userId=str(user.id)
    )


# Email verification disabled: verify/resend endpoints removed