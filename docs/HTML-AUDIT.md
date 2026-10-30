# Аудит актуального HTML

Текущий эталон: reference/Cloud_Torrent_Client.html, предоставлен пользователем 30.10.2026. Предыдущий эталон: reference/Cloud_Torrent_Client-v1.html.

Изменения DOM, CSS, JS и таблица переноса в Android: [REDESIGN.md](REDESIGN.md). Новый инвентарь DOM и computed styles: artifacts/redesign/full-dom-inventory.json и html-layouts.json. Снимки каждого экрана, sheets и offline-состояний: artifacts/redesign/html-*.png.

Аудит первой версии с полным соответствием исходных id и классов сохранён отдельно: [HTML-AUDIT-v1.md](HTML-AUDIT-v1.md). Новый HTML сохраняет прежние элементы и SVG-геометрии; добавлены optVerify, optUnzip, mobLim/mobLimV, optNight, optLock. Изменены порядок настроек, полноэкранный layout и тема тарифного sheet. Новые JS callbacks только меняют demo-состояния/тосты; имитация функций не переносится в production API.

Это документация реализации и проверки; точность 1:1 определяется native screenshot comparison, а не наличием всех CSS-переменных в коде.
