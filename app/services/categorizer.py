# app/services/categorizer.py
from sqlalchemy.orm import Session
from app.models.core import AppCatalog, AppCategory

# 1. Sabit Kurallar (Heuristic) - Fallback mekanizması
KEYWORD_RULES = {
    "game": ["supercell", "roblox", "minecraft", "pubg", "unity", "epicgames", "ea.gp", "activision", "zynga", "game", "playrix", "king."],
    "social": ["instagram", "facebook", "twitter", "tiktok", "snapchat", "discord", "whatsapp", "telegram", "messenger", "wechat"],
    "video": ["youtube", "netflix", "twitch", "primevideo", "disney", "exxen", "blutv", "hulu"],
    "education": ["duolingo", "udemy", "coursera", "zoom", "eba", "classroom", "khanacademy", "quizlet"]
}

def ensure_categories_exist(db: Session):
    """Kategorilerin DB'de olduğundan emin ol"""
    defaults = ["game", "social", "video", "education", "other"]
    for key in defaults:
        if not db.query(AppCategory).filter_by(key=key).first():
            db.add(AppCategory(key=key, display_name=key.capitalize()))
    db.commit()

def guess_category_by_keywords(package_name: str) -> str:
    """Paket isminden tahmin yürütür (En son çare)"""
    pkg = package_name.lower()
    for category, keywords in KEYWORD_RULES.items():
        for kw in keywords:
            if kw in pkg:
                return category
    return "other"

def get_or_create_app_entry(db: Session, package_name: str, app_name: str = None) -> AppCatalog:

    # 1. Veritabanı Kontrolü (Senin 50k data buraya import edilmiş olacak)
    catalog_entry = db.query(AppCatalog).filter_by(package_name=package_name).first()
    if catalog_entry:
        # Eğer daha önce "other" olarak kaydedilmişse ve şimdi bir isim geldiyse güncellemeyi deneyebiliriz
        # ama şimdilik sadece var olanı döndürelim.
        return catalog_entry

    # 2. Kayıt Yok, Yeni Oluşturuyoruz
    ensure_categories_exist(db) 
    
    # Tahmin mekanizması (Keyword)
    predicted_key = guess_category_by_keywords(package_name)
    category = db.query(AppCategory).filter_by(key=predicted_key).first()
    
    new_entry = AppCatalog(
        package_name=package_name,
        app_name=app_name or package_name,
        category_id=category.id if category else None
    )
    
    try:
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
    except Exception:
        db.rollback()
        return db.query(AppCatalog).filter_by(package_name=package_name).first()
        
    return new_entry