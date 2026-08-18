
# Logbook Photo Finder — Web 1.0

Полноценный локальный веб-MVP.

## Запуск
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Открой http://localhost:8501

## Как работает
Загружается Excel, читаются Date / Reg / DepPlace / ArrPlace. Сервер ищет фотографии самолета по registration через публичный endpoint Planespotters и показывает ссылки на JetPhotos для более точного поиска.

JetPhotos позволяет фильтровать фотографии по aircraft, airport, keywords и photo year. Фотографии принадлежат их правообладателям, поэтому сайт показывает превью/ссылки и не копирует коллекцию фотографий к себе.

## Для публичного деплоя
Нужен HTTPS-хостинг (например, Render/Railway/Fly.io/VPS) и production WSGI-сервер. Для большой летной книжки следует добавить кэш, очередь запросов и rate limiting.
