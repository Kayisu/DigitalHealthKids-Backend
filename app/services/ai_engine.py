# app/services/ai_engine.py
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from uuid import UUID

class AIEngine:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        # TODO: Kullanıcının ayarlarını (UserSettings) çek. (Limitler, uyku saati vs.)
        # TODO: Kullanıcının son 14 günlük FeatureDaily verisini çek.
        #       Eğer veri yoksa self.has_data = False olarak işaretle.

    def _get_mock_data_if_needed(self):
        """
        Geliştirme aşamasında frontend'i beslemek için kullanılacak.
        Prod ortamında bu fonksiyon devre dışı bırakılacak.
        """
        # TODO: Eğer self.has_data False ise ve DEBUG modundaysak;
        #       Rastgele FeatureDaily objeleri (High risk, Low risk vb.) üretip self.history'ye ata.
        pass

    def calculate_risk_score(self) -> Dict:
        """
        Kullanıcının dijital bağımlılık riskini hesaplar.
        Çıktı: 0-100 arası skor ve 'Düşük/Orta/Yüksek' etiketi.
        """
        # TODO: 1. Adım: Gece kullanım süresini (night_minutes) normalize et. 
        #       (Örn: 60dk üstü = 100 puan, 0dk = 0 puan). Ağırlık: %50
        
        # TODO: 2. Adım: Günlük toplam süre limit aşımını kontrol et.
        #       (Limit - Kullanım farkı). Ağırlık: %30
        
        # TODO: 3. Adım: Kategori dağılımına bak.
        #       (Oyun + Sosyal Medya oranı %50'yi geçiyor mu?). Ağırlık: %20
        
        # TODO: 4. Adım: Hafta içi / Hafta sonu varyansına bak (Opsiyonel - İleri aşama).
        
        # Return şimdilik dummy
        return {"score": 0, "level": "Hesaplanmadı", "details": {}}

    def determine_profile(self) -> str:
        """
        Kullanıcıyı bir persona ile eşleştirir.
        Örn: Gece Kuşu, Oyuncu, Sosyal Kelebek.
        """
        # TODO: Veri setindeki ağırlıklı kategoriye bak.
        #       if gaming_ratio > 0.4 -> "Sıkı Oyuncu"
        #       if night_minutes_avg > 45 -> "Gece Kuşu"
        #       if social_ratio > 0.4 -> "Sosyal Medya Tutkunu"
        #       else -> "Dengeli Kullanıcı"
        
        return "Profil Belirleniyor..."

    def predict_next_week(self) -> Dict:
        """
        Gelecek haftaki tahmini ekran süresi.
        """
        # TODO: Basit Hareketli Ortalama (Simple Moving Average - SMA) kullan.
        #       Son 7 günün ortalamasını alıp 7 ile çarp.
        # TODO: (İleri Seviye) Trend analizi yap (Artış eğiliminde mi?).
        
        return {"daily_avg": 0, "weekly_total": 0}

    def get_smart_recommendations(self, risk_level: str, profile: str) -> List[str]:
        """
        Risk ve Profile göre ebeveyne aksiyon önerileri sunar.
        """
        recommendations = []
        
        # TODO: Risk yüksekse -> "Süre limitini düşür" önerisi ekle.
        # TODO: Profil 'Gece Kuşu' ise -> "Gece kısıtlamasını 1 saat öne çek" önerisi ekle.
        # TODO: Profil 'Oyuncu' ise -> "Oyun kategorisine özel süre sınırı koy" önerisi ekle.
        
        return recommendations