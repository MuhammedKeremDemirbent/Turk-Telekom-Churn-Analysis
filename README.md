# Türk Telekom Capstone Project (Churn Analytics & RAG Chatbot)

Bu proje, müşteri kaybı (churn) tahmini, müşteri davranışı analizi ve RAG (Retrieval-Augmented Generation) tabanlı bir akıllı asistan (chatbot) içeren uçtan uca bir sistemdir.

## 🚀 Öne Çıkan Özellikler

- **Müşteri Churn Tahmini & Analiz Dashboard'u**: Müşteri harcama, şikayet ve demografik verileri üzerinden churn riski hesaplama ve görselleştirme.
- **RAG Tabanlı Asistan Chatbot**: Müşteri sorgularını yanıtlayan, kampanya ve destek bilgisi sunan entegre vektör arama destekli chatbot.
- **Modern Python Altyapısı**: Astral `uv` ile hızlı bağımlılık yönetimi ve modern paket düzeni.
- **Konteyner Desteği**: Docker ve Docker Compose ile kolay dağıtım.

## 🛠️ Kurulum ve Çalıştırma

### 1. Yerel Geliştirme (Local Setup)

```bash
# Bağımlılıkları yükleyin (uv kullanarak)
uv sync

# Çevre değişkenlerini ayarlayın
cp .env.example .env

# Veritabanı migrasyonlarını çalıştırın
uv run python manage.py migrate

# Sunucuyu başlatın
uv run uvicorn config.asgi:application --reload --port 8000
```

### 2. Docker Compose ile Çalıştırma

```bash
docker-compose up --build
```

Uygulama `http://localhost:8000` adresinde çalışacaktır.   

## 📁 Proje Yapısı

- `chatbot/`: Django chatbot uygulaması (views, service, templates).
- `config/`: Django projesi ana yapılandırmaları.
- `customers/` & `dashboard/`: Müşteri ve analitik veri yönetimi modelleri.
- `src/`: Notebook'lar (churn tahmini, NLP analizi, RAG eğitimi) ve RAG modülleri.
- `scripts/`: Veri işleme, skorlama ve analitik üretim betikleri.
- `DataVis/`: Görselleştirme çıktıları ve grafikler.
