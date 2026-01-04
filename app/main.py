# app/main.py
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from app.routers import auth, usage, policy, ai
from app.services.categorizer import dataset_loader

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("Digital Health Kids Backend Başlatılıyor...")
    
    # 1. 50k'lık App Dataset'ini belleğe yükle
    # Bu işlem sadece bir kere yapılır ve uygulama ayakta kaldığı sürece RAM'den okunur.
    dataset_loader.load_data() 
    
    yield # Uygulama burada çalışmaya devam eder
    
    # --- SHUTDOWN ---
    print("Digital Health Kids Backend Kapatılıyor...")
    # Gerekirse DB bağlantılarını kapatma vs. burada yapılabilir

app = FastAPI(
    title="Digital Health Kids API",
    version="0.1.0",
    lifespan=lifespan # Yeni lifespan parametresi
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(policy.router, prefix="/api/policy", tags=["policy"])
app.include_router(ai.router, prefix="/api", tags=["ai"])