# API

Базовый адрес — HTTPS-домен приложения, назначенный в BotHost. `https://bothost.ru` является сайтом провайдера и не заменяет этот адрес. Версия инженерного API: 0.3.0. Схема: openapi.json; после запуска доступны /docs и /openapi.json.

Авторизация: `Authorization: Bearer <ADMIN_API_TOKEN>`. Это токен вашего приложения, не пароль панели BotHost. Начальная модель — один администратор; Telegram-бот использует тот же токен. Health публичен. Лимит — 120 запросов в минуту. Polling Android: 5 секунд при соединении, 15 секунд при ошибке.

| Маршруты | Назначение |
|---|---|
| GET /health, /server/status, /server/storage | Доступность API, реальный Drive status, диск |
| GET/PUT /server/settings | Серверная автоматизация, parallelism |
| POST /server/cleanup | Очистка завершённых локальных пакетов |
| POST /torrents/metadata | `{"source":"magnet:…"}` / HTTPS URL либо `{"torrent_base64":"…"}`; возвращает id, размер и список файлов |
| POST /torrents | `{"metadata_id":"…","selected":[0,2],"start":true}`; выбранные индексы, проверка квоты |
| GET /torrents, /torrents/{id}, /torrents/{id}/files | Общие задачи и реальный прогресс |
| POST /torrents/{id}/pause, /resume | Управление общей очередью |
| DELETE /torrents/{id} | Отмена задачи и очистка её локальных данных |
| GET /files, /files/{id} | Файлы и фактические locations |
| GET /files/{id}/download | Авторизованная передача; Range/If-Range, 206/416, ETag |
| POST /files/{id}/link | Подписанный URL download, действует 5 минут; сам URL даёт доступ, не публикуйте его |
| DELETE /files/{id} | Удаление доступной администратору копии; активные данные защищены |
| GET /account, /account/limits, /account/subscription | Тариф, лимиты и entitlement |
| POST /drive/authorize, GET /drive/callback | OAuth через браузер, одноразовый state |
| GET/POST /drive/folders, PUT /drive/folder | Перечислить/создать/выбрать папку |
| DELETE /drive | Отключить Google Drive |

Точные request/response поля смотрите в исходном OpenAPI и request models backend/main.py; схема пока не типизирует все динамические ответы. Успешный /health не подтверждает разрешение P2P или работоспособность Google Drive.

Ошибка бизнес-операции: JSON `{"error":{"code":"quota_exceeded"}}` либо иной код причины. Ошибки проверки структуры запроса FastAPI возвращают стандартный JSON 422 с `detail`. Проверяйте HTTP status и тело. HTTP URL, private IP и перенаправления при импорте .torrent отклоняются.

Состояния: metadata, queued, downloading, uploading, checking, ready, paused, error; внутренние cancel_requested/cancelled используются при отмене. Большой общий размер не блокирует metadata; В административном режиме quota выбранных файлов отсутствует (tasks/selected_bytes/drive_destination_bytes=null, phone_downloads=true). `large_single_file_streaming=false` означает отсутствие потокового режима для файла больше доступного дискового пакета.

Серверная загрузка не зависит от открытого Android. Настройки Wi-Fi/зарядки телефона не изменяют торрент-очередь.

Административный режим включён по умолчанию, в том числе при старом ACCOUNT_PLAN=free. Инструкция обновления сервера и физические ограничения: ADMIN.md.
