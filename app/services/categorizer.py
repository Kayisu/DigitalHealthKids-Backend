# app/services/categorizer.py
import os
import pandas as pd
from sqlalchemy.orm import Session
from app.models.core import AppCatalog, AppCategory

class CategoryDataset:
    _instance = None
    _data_map = {} 
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CategoryDataset, cls).__new__(cls)
        return cls._instance

    def load_data(self, csv_path="app/assets/app_data.csv"):
 
        if self._loaded:
            return

        if not os.path.exists(csv_path):
            print(f" Categorizer: Dataset bulunamadı ({csv_path}). Sadece isimden tahmin modu çalışacak.")
            return

        try:
            print(f" Categorizer verisi yükleniyor: {csv_path}...")
            # Sadece ihtiyacımız olan 'package_name' ve 'Category' kolonlarını alıyoruz
            # CSV başlıkları: package_name, App, Category, Rating, Installs
            df = pd.read_csv(csv_path, usecols=['package_name', 'Category'])
            
            # Veri temizliği: Kategorileri büyük harf yap
            df['Category'] = df['Category'].astype(str).str.upper()
            
            # Dataframe'i sözlüğe çevir (Hız için)
            self._data_map = pd.Series(
                df.Category.values, 
                index=df.package_name
            ).to_dict()
            
            self._loaded = True
            print(f" Categorizer Hazır: {len(self._data_map)} uygulama hafızaya alındı.")
            
        except Exception as e:
            print(f" Categorizer veri yükleme hatası: {e}")

    def lookup_category(self, package_name: str) -> str:
        """
        Paket isminden kategori döner.
        """
        if not self._loaded:
            # Eğer main.py'da yüklenmediyse burada yüklemeyi dene (Lazy loading)
            self.load_data()

        # 1. Tam Eşleşme
        return self._data_map.get(package_name)

# Global erişim nesnesi
dataset_loader = CategoryDataset()

def get_or_create_app_entry(db: Session, package_name: str) -> AppCatalog:
    """
    Uygulamayı katalogda bulur. Yoksa:
    1. Dataset'e bakar.
    2. Bulamazsa tahmin eder.
    3. DB'ye kaydeder ve döner.
    """
    # 1. Önce DB'ye bak (En hızlısı)
    entry = db.query(AppCatalog).filter_by(package_name=package_name).first()
    if entry:
        return entry

    # 2. DB'de yoksa, Dataset'ten Kategori Bak
    predicted_category_key = dataset_loader.lookup_category(package_name)
    
    # 3. Dataset'te de yoksa, isminden tahmin et (Fallback)
    if not predicted_category_key:
        predicted_category_key = _predict_category_fallback(package_name)

    # 4. Kategori Objesini DB'den çek veya yarat
    category_obj = None
    if predicted_category_key:
        # Kategori ismini güzelleştir (GAME_ACTION -> Game Action)
        clean_name = predicted_category_key.replace('_', ' ').title()
        
        category_obj = db.query(AppCategory).filter_by(key=predicted_category_key).first()
        if not category_obj:
            category_obj = AppCategory(key=predicted_category_key, display_name=clean_name)
            db.add(category_obj)
            db.flush() # ID oluşsun diye

    # 5. Uygulama ismini tahmin et (com.google.android.youtube -> Youtube)
    # Dataset'te App Name olsa bile basitlik için paketten üretiyoruz, 
    # ama ileride dataset_loader'a app_name map de eklenebilir.
    parts = package_name.split('.')
    app_name_guess = parts[-1].capitalize() if parts else package_name
    
    # 6. Kataloğa Kaydet
    entry = AppCatalog(
        package_name=package_name,
        app_name=app_name_guess,
        category_id=category_obj.id if category_obj else None
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    return entry

def _predict_category_fallback(package_name: str) -> str:
    """
    Dataset'te yoksa string analizi ile basit tahmin.
    """
    p = package_name.lower()
    
    # Öncelikli Anahtar Kelimeler
    if "game" in p or "play" in p: return "GAME"
    if "social" in p or "gram" in p or "book" in p or "twitter" in p or "tiktok" in p: return "SOCIAL"
    if "video" in p or "tube" in p or "stream" in p or "netflix" in p: return "VIDEO_PLAYERS"
    if "learn" in p or "edu" in p or "kids" in p or "school" in p: return "EDUCATION"
    if "shop" in p or "store" in p or "market" in p: return "SHOPPING"
    if "map" in p or "nav" in p or "gps" in p: return "MAPS_AND_NAVIGATION"
    if "messag" in p or "chat" in p or "whatsapp" in p or "telegram" in p: return "COMMUNICATION"
    if "music" in p or "audio" in p or "spotify" in p: return "MUSIC_AND_AUDIO"
    
    return "OTHER"