# app/services/categorizer.py
import os
import pandas as pd
from sqlalchemy.orm import Session
from app.models.core import AppCatalog, AppCategory

# Singleton Data Loader
class CategoryDataset:
    _instance = None
    _data_map = {} # { "com.instagram.android": "SOCIAL", ... }
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CategoryDataset, cls).__new__(cls)
        return cls._instance

    def load_data(self, csv_path="app/assets/app_data.csv"):
        """
        CSV dosyasını okur ve RAM'e {package_name: category} sözlüğü olarak atar.
        """
        if self._loaded:
            return

        if not os.path.exists(csv_path):
            print(f"⚠️ UYARI: Dataset bulunamadı: {csv_path}. Otomatik kategorizasyon çalışacak.")
            return

        try:
            # CSV okuma - Kolon isimlerini kendi datasetine göre güncellemen gerekebilir
            # Örnek CSV kolonları: 'App', 'Category', 'Package Name'
            # Biz burada 'App' isminden veya varsa 'Package Name'den eşleşme arayacağız.
            
            # Senaryo 1: Dataset'te package_name varsa (En Temizi)
            # df = pd.read_csv(csv_path, usecols=['Package Name', 'Category'])
            # self._data_map = pd.Series(df.Category.values, index=df['Package Name']).to_dict()

            # Senaryo 2: Sadece App Name varsa (Hack yöntemi)
            # Dataset büyük olduğu için sadece gerekli kolonları alıyoruz
            df = pd.read_csv(csv_path, usecols=['App', 'Category']) 
            
            # Basit temizlik
            df['Category'] = df['Category'].astype(str).str.upper().str.replace('_', ' ')
            
            # Hızlı erişim için sözlüğe çevir (App Name -> Category)
            # Not: Package name'den App Name çıkarmak zor olduğu için 
            # burayı "contains" mantığıyla aşağıda yöneteceğiz veya 
            # dataseti "lowercase" yapıp saklayacağız.
            self._data_map = pd.Series(df.Category.values, index=df['App'].str.lower()).to_dict()
            
            self._loaded = True
            print(f"✅ Dataset yüklendi: {len(self._data_map)} uygulama.")
            
        except Exception as e:
            print(f"❌ Dataset yüklenirken hata: {e}")

    def lookup_category(self, package_name: str) -> str:
        """
        Paket isminden kategori bulmaya çalışır.
        """
        if not self._loaded:
            self.load_data()

        pkg_lower = package_name.lower()

        # 1. Tam eşleşme (Eğer dataset package_name içeriyorsa)
        if pkg_lower in self._data_map:
            return self._data_map[pkg_lower]

        # 2. İsimden tahmin (Eğer dataset App Name içeriyorsa)
        # Örn: "com.supercell.brawlstars" -> "brawl stars" dataset'te var mı?
        # Bu işlem 50k satırda yavaş olabilir, o yüzden sadece map'te var mı diye bakıyoruz.
        
        # Basit heuristic: paketin son parçasını al (brawlstars)
        parts = pkg_lower.split('.')
        if len(parts) >= 3:
            likely_name = parts[-1] # "brawlstars"
            # Sözlükte "brawl stars" gibi geçiyor olabilir, fuzzy match zor.
            # Şimdilik basit logic:
            if likely_name in self._data_map:
                return self._data_map[likely_name]

        return None

# Global instance
dataset_loader = CategoryDataset()

def get_or_create_app_entry(db: Session, package_name: str) -> AppCatalog:
    """
    Uygulamayı katalogda bulur, yoksa oluşturur ve kategorisini tahmin eder.
    """
    entry = db.query(AppCatalog).filter_by(package_name=package_name).first()
    if entry:
        return entry

    # 1. Datasetten Kategori Bak
    predicted_category_key = dataset_loader.lookup_category(package_name)
    
    # 2. Bulunamazsa Kural Tabanlı (Fallback) Tahmin Yap
    if not predicted_category_key:
        predicted_category_key = _predict_category_fallback(package_name)

    # 3. Kategoriyi DB'den çek veya yarat
    category_obj = None
    if predicted_category_key:
        # Kategori ismini temizle (GAME_ACTION -> Game)
        clean_name = predicted_category_key.replace('_', ' ').title()
        
        category_obj = db.query(AppCategory).filter_by(key=predicted_category_key).first()
        if not category_obj:
            category_obj = AppCategory(key=predicted_category_key, display_name=clean_name)
            db.add(category_obj)
            db.flush() # ID oluşsun diye

    # 4. Kataloğa Kaydet
    # App Name'i paket isminden uyduruyoruz (com.google.android.youtube -> Youtube)
    app_name_guess = package_name.split('.')[-1].capitalize()
    
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
    
    if "game" in p or "android.play" in p:
        return "GAME"
    if "social" in p or "instagram" in p or "facebook" in p or "twitter" in p or "tiktok" in p:
        return "SOCIAL"
    if "video" in p or "youtube" in p or "netflix" in p:
        return "VIDEO"
    if "learn" in p or "edu" in p or "kids" in p:
        return "EDUCATION"
    if "map" in p or "nav" in p:
        return "MAPS"
    
    return "OTHER"