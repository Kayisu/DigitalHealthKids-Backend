# Backend API Dokümantasyonu (Kotlin Entegrasyonu İçin)

Bu doküman, Android (Kotlin) tarafının backend ile haberleşmesi için gerekli olan API uçlarını (endpoints), veri modellerini ve genel akışı içerir.

## Genel Bilgiler
- **Base URL**: `/api`
- **Tarih Formatları**: Genellikle ISO 8601 veya timestamp (milisaniye) kullanılır.
- **Saat Dilimi**: Backend tarafında Türkiye saati (UTC+3) dikkate alınarak raporlama yapılır, ancak veri gönderirken UTC veya timestamp kullanılması önerilir.

---

## 1. Kimlik Doğrulama (Auth)

Ebeveyn girişi ve cihaz kaydı için kullanılır.

### Login
**POST** `/api/auth/login`

Ebeveyn email ve şifresi ile giriş yapar. Başarılı olursa bir `token` ve `deviceId` döner. Bu `deviceId` sonraki raporlama isteklerinde kullanılmalıdır.

**Request Body (`ParentLoginRequest`):**
```json
{
  "email": "veli@example.com",
  "password": "gizlisifre123"
}
```

**Response (`ParentLoginResponse`):**
```json
{
  "token": "a1b2c3d4...",       // API Token (Bearer token olarak kullanılabilir)
  "refreshToken": null,
  "deviceId": "uuid-string",    // Cihaz ID'si (Saklanmalı)
  "userId": "uuid-string"       // Kullanıcı ID'si
}
```

---

## 2. Kullanım Raporlama (Usage)

Android cihazdan toplanan uygulama kullanım verilerini sunucuya göndermek için kullanılır.

### Rapor Gönder
**POST** `/api/usage/report`

Cihazdaki `UsageStats` verilerini periyodik olarak bu uca gönderin.

**Request Body (`UsageReportRequest`):**
```json
{
  "user_id": "uuid-string",
  "device_id": "uuid-string",
  "events": [
    {
      "package_name": "com.instagram.android",
      "app_name": "Instagram",
      "timestamp_start": 1702980000000, // Milisaniye cinsinden
      "timestamp_end": 1702980060000,   // Milisaniye cinsinden
      "duration_seconds": 60
    },
    {
      "package_name": "com.whatsapp",
      "timestamp_start": 1702980100000,
      "timestamp_end": 1702980200000,
      "duration_seconds": 100
    }
  ]
}
```

**Response (`UsageReportResponse`):**
```json
{
  "status": "ok",
  "inserted": 2 // Eklenen kayıt sayısı
}
```

### Dashboard Verisi
**GET** `/api/usage/dashboard?user_id={uuid}`

Ebeveyn uygulamasında gösterilecek özet verileri çeker.

**Response (`DashboardResponse`):**
```json
{
  "user_name": "Ali Veli",
  "today_total_minutes": 120,
  "weekly_breakdown": [
    {
      "date": "2023-12-19",
      "total_minutes": 45,
      "apps": [
        {
          "app_name": "YouTube",
          "package_name": "com.google.android.youtube",
          "minutes": 30,
          "category": "Video"
        }
      ]
    }
  ],
  "bedtime_start": "22:00",
  "bedtime_end": "08:00"
}
```

---

## 3. Kurallar ve Ayarlar (Policy)

Ebeveynin koyduğu kuralları (süre limiti, yasaklı uygulamalar, uyku saati) yönetir.

### Mevcut Kuralları Getir
**GET** `/api/policy/current?user_id={uuid}`

Çocuğun cihazında uygulanacak kuralları çeker. Bu endpoint periyodik olarak veya push notification geldiğinde çağrılmalıdır.

**Response (`PolicyResponse`):**
```json
{
  "user_id": "uuid-string",
  "daily_limit_minutes": 120,       // Günlük toplam süre limiti (dk)
  "blocked_apps": [                 // Yasaklı paket isimleri
    "com.tiktok.android",
    "com.facebook.katana"
  ],
  "bedtime": {                      // Uyku saati (varsa)
    "start": "22:00",
    "end": "07:00"
  },
  "weekend_extra_minutes": 0
}
```

### Ayarları Güncelle
**PUT** `/api/policy/settings?user_id={uuid}`

Ebeveynin ayarları değiştirmesi için kullanılır.

**Request Body (`PolicySettingsRequest`):**
```json
{
  "daily_limit_minutes": 150,       // Opsiyonel
  "bedtime_start": "23:00",         // Opsiyonel (HH:MM)
  "bedtime_end": "08:00",           // Opsiyonel (HH:MM)
  "weekend_relax_pct": 10,          // Hafta sonu esneklik yüzdesi
  "blocked_packages": [             // Tam liste gönderilir
    "com.tiktok.android"
  ]
}
```

### Uygulama Yasakla / Yasağı Kaldır (Tekil İşlemler)

**POST** `/api/policy/block?user_id={uuid}`
**POST** `/api/policy/unblock?user_id={uuid}`

Tek bir uygulamayı yasaklamak veya yasağını kaldırmak için.

**Request Body (`BlockAppRequest`):**
```json
{
  "package_name": "com.example.game"
}
```

### Yasak Durumunu Değiştir (Toggle)
**POST** `/api/policy/toggle-block`

Bir uygulamanın yasak durumunu tersine çevirir (Yasaklıysa açar, açıksa yasaklar).

**Request Body (`ToggleBlockRequest`):**
```json
{
  "user_id": "uuid-string",
  "package_name": "com.example.game"
}
```

---

## Veri Modelleri (Özet)

### User
- `id`: UUID
- `email`: String
- `full_name`: String

### Device
- `id`: UUID
- `platform`: "android"
- `model`: String

### PolicyRule
- `target_package`: String (Paket adı)
- `action`: "block" veya "limit"
- `active`: Boolean

### DailyUsageLog
- `usage_date`: Date
- `package_name`: String
- `total_seconds`: Integer
