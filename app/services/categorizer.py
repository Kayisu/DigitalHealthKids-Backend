# app/services/categorizer.py
import os
import pandas as pd
from sqlalchemy.orm import Session
from app.models.core import AppCatalog, AppCategory
from app.services.category_constants import (
    CATEGORY_KEYS,
    CATEGORY_LABELS_TR,
    DEFAULT_CATEGORY_KEY,
    canonicalize_category_key,
    display_label_for,
)

class CategoryDataset:
    _instance = None
    _data_map = {} 
    _name_map = {}
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CategoryDataset, cls).__new__(cls)
        return cls._instance

    def load_data(self, csv_path=None):
 
        if self._loaded:
            return

        if csv_path is None:
            # Resolve relative to project root (this file lives in app/services)
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            csv_path = os.path.join(base_dir, "assets", "myapps.csv")

        if not os.path.exists(csv_path):
            print(f" Categorizer: Dataset bulunamadı ({csv_path}). Sadece isimden tahmin modu çalışacak.")
            return

        try:
            print(f" Categorizer verisi yükleniyor: {csv_path}...")
            # Sadece ihtiyacımız olan kolonları al
            # CSV başlıkları: package_name, app_name, category, rating, installs, free
            df = pd.read_csv(csv_path, usecols=['package_name', 'category', 'app_name'])

            # Temizlik: kategorileri normalize et, app adlarını strip et
            df['category'] = df['category'].astype(str).apply(canonicalize_category_key)
            df['app_name'] = df['app_name'].astype(str).str.strip()

            # category ve app name map'lerini hazırla
            self._data_map = pd.Series(df.category.values, index=df.package_name).to_dict()
            self._name_map = pd.Series(df.app_name.values, index=df.package_name).to_dict()
            
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

        match = self._data_map.get(package_name)
        if match:
            return match.lower()
        return None

    def lookup_app_name(self, package_name: str) -> str | None:
        if not self._loaded:
            self.load_data()
        name = self._name_map.get(package_name)
        if name and not _is_generic_name(name):
            return name
        return None

# Global erişim nesnesi
dataset_loader = CategoryDataset()

def get_or_create_app_entry(db: Session, package_name: str) -> AppCatalog:
    """
    Uygulamayı katalogda bulur. Yoksa:
    1. Dataset'e bakar.
    2. Bulamazsa tahmin eder.
    3. DB'ye kaydeder ve döner.
    """
    # Dataset verisini baştan hazırla (varsa kullanırız)
    dataset_category = dataset_loader.lookup_category(package_name)
    predicted_category_key = canonicalize_category_key(dataset_category) if dataset_category else None
    dataset_app_name = dataset_loader.lookup_app_name(package_name)

    # 1. Önce DB'ye bak (En hızlısı)
    entry = db.query(AppCatalog).filter_by(package_name=package_name).first()
    if entry:
        updated = False

        # Eğer isim generic ise dataset veya tahminle düzelt
        if _is_generic_name(entry.app_name):
            candidate = dataset_app_name or _guess_app_name(package_name)
            if candidate and not _is_generic_name(candidate):
                entry.app_name = candidate
                updated = True

        # Mevcut kategori canonical mı? Değilse eşle
        if entry.category is not None:
            current_key = canonicalize_category_key(entry.category.key)
            if current_key != entry.category.key:
                target_obj = db.query(AppCategory).filter_by(key=current_key).first()
                if not target_obj:
                    clean_name = display_label_for(current_key)
                    target_obj = AppCategory(key=current_key, display_name=clean_name)
                    db.add(target_obj)
                    db.flush()
                entry.category_id = target_obj.id
                updated = True

        # Kategorisi boşsa dataset tahminini yaz
        if entry.category_id is None and predicted_category_key:
            category_obj = db.query(AppCategory).filter_by(key=predicted_category_key).first()
            if not category_obj:
                clean_name = display_label_for(predicted_category_key)
                category_obj = AppCategory(key=predicted_category_key, display_name=clean_name)
                db.add(category_obj)
                db.flush()
            else:
                desired_label = display_label_for(predicted_category_key)
                if category_obj.display_name != desired_label:
                    category_obj.display_name = desired_label
                    db.flush()
            entry.category_id = category_obj.id
            updated = True

        if updated:
            db.commit()
            db.refresh(entry)

        return entry
    
    # 3. Dataset'te de yoksa, isminden tahmin et (Fallback)
    if not predicted_category_key:
        predicted_category_key = _predict_category_fallback(package_name)

    if predicted_category_key:
        predicted_category_key = canonicalize_category_key(predicted_category_key)

    # 4. Kategori Objesini DB'den çek veya yarat
    category_obj = None
    if predicted_category_key:
        # Normalize et (lowercase) ve kullanıcıya güzel isim ver (game_action -> Game Action)
        predicted_category_key = canonicalize_category_key(predicted_category_key)
        clean_name = display_label_for(predicted_category_key)
        
        category_obj = db.query(AppCategory).filter_by(key=predicted_category_key).first()
        if not category_obj:
            category_obj = AppCategory(key=predicted_category_key, display_name=clean_name)
            db.add(category_obj)
            db.flush() # ID oluşsun diye
        elif category_obj.display_name != clean_name:
            category_obj.display_name = clean_name
            db.flush()

    # 5. Uygulama ismini belirle: dataset'te varsa onu kullan, yoksa tahmin et
    if dataset_app_name:
        app_name_guess = dataset_app_name
    else:
        app_name_guess = _guess_app_name(package_name)
    
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
    if "game" in p or "play" in p:
        return "games"
    if "social" in p or "gram" in p or "book" in p or "twitter" in p or "tiktok" in p or "chat" in p:
        return "social"
    if "music" in p or "audio" in p or "spotify" in p or "band" in p or "tune" in p:
        return "music"
    if "video" in p or "tube" in p or "stream" in p or "netflix" in p:
        return "video"
    if "learn" in p or "edu" in p or "kids" in p or "school" in p:
        return "education"
    if "shop" in p or "store" in p or "market" in p or "amazon" in p or "trendyol" in p or "vending" in p:
        return "shopping"
    if "map" in p or "nav" in p or "gps" in p or "ulas" in p or "travel" in p:
        return "travel_&_transportation"
    if "messag" in p or "whatsapp" in p or "telegram" in p:
        return "social"
    if "health" in p or "fit" in p or "workout" in p:
        return "health_&_fitness"
    if "bank" in p or "pay" in p or "wallet" in p or "finan" in p or "coin" in p:
        return "finance"
    if "note" in p or "doc" in p or "office" in p or "task" in p or "todo" in p:
        return "productivity"
    if "design" in p or "photo" in p or "camera" in p:
        return "design"
    if "ai" in p or "gpt" in p or "gemini" in p or "claude" in p:
        return "artificial_intelligence"
    if "hobby" in p or "entertainment" in p or "manga" in p or "book" in p:
        return "hobby_entertainment"

    return DEFAULT_CATEGORY_KEY


def _guess_app_name(package_name: str) -> str:
    """Paketten insan-okur app adı tahmini. Sık görülen son ekleri (android, app) temizler."""
    parts = package_name.split('.') if package_name else []
    if not parts:
        return package_name

    # Tersten ilerle, anlamlı ilk parçayı seç
    blacklist = {"android", "app", "mshop", "mobile", "client"}
    for part in reversed(parts):
        clean = part.strip().replace('_', ' ').replace('-', ' ')
        if not clean:
            continue
        low = clean.lower()
        if low in blacklist:
            continue
        return clean.title()

    return parts[-1].title()


def _is_generic_name(name: str | None) -> bool:
    if not name:
        return True
    low = name.strip().lower()
    if len(low) <= 2:
        return True
    generic = {"app", "android", "application", "mobile", "client"}
    return low in generic