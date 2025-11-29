# app/main.py
from fastapi import FastAPI
from app.routers import auth, usage, policy

app = FastAPI(
    title="Digital Health Kids API",
    version="0.1.0"
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(policy.router, prefix="/api/policy", tags=["policy"])