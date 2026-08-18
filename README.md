
# Logbook Photo Finder 2.0

Автоматическая обработка всей летной книжки.

- Один клик после загрузки Excel.
- Поиск выполняется по уникальным registration, поэтому один и тот же борт не запрашивается заново для каждого сектора.
- Фотографии автоматически показываются для всех строк.
- Приоритет отдается фото, в метаданных которых встречается аэропорт вылета/прилета.
- Для каждой строки есть навигационные ссылки на JetPhotos, Airliners.net и PlaneSpotters.
- Excel не хранится на сервере после обработки.

JetPhotos имеет отдельные поля для aircraft registration, photo location/airport и photo year. Фотографии остаются на исходных сайтах; приложение показывает превью/ссылки и не републикует коллекцию фотографий.


## Registration formatting

The app keeps a normalized registration internally but formats six-character registrations for web searches and display with the hyphen used by aviation photo databases, e.g. `A9CDHW` → `A9C-DHW`. Other registration formats are left unchanged.
