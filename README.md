# Cloud Torrent Client

Android Kotlin/Compose + единый FastAPI/libtorrent backend + aiogram 3. Исходный утверждённый HTML и логотип: `reference/`. Это проверяемая инженерная версия; готовность production и визуальное 1:1 не заявлены. Точный статус испытаний и ограничения — `docs/TEST-REPORT.md`.

Дизайн Android обновлён до эталона от 30.10.2026, версия APK 0.2.0. Детали переноса, скриншоты и ограничения новых пунктов: `docs/REDESIGN.md`. Прежние снимки вне `artifacts/redesign/` относятся к 0.1.0.

## Административная версия 0.3.0

Тарифные ограничения размера выбранных файлов и количества задач сняты; передача на Android разрешена. Админ-режим backend включён по умолчанию даже при прежнем ACCOUNT_PLAN=free. После обновления кода на BotHost требуется пересборка проекта/контейнера. Полная инструкция и физические ограничения: `docs/ADMIN.md`.

Одиночный файл больше доступного рабочего диска всё ещё не поддерживается: потоковый режим не реализован. Это ограничение нельзя устранить снятием коммерческих квот.

## Состав

- `android/`: minSdk 26, compile/target SDK 36, MVVM, Hilt, Retrofit/OkHttp, StateFlow, DataStore+Keystore, Room, WorkManager, SAF.
- `backend/`: авторизованное API, SQLite, один libtorrent scheduler, Google Drive OAuth/resumable uploads, aiogram-клиент того же API.
- `docs/HTML-AUDIT.md`, `html-inventory.json`, `css-tokens.json`, `svg-inventory.json`: аудит HTML и план переноса, не подтверждение реализации всех элементов.
- `docs/openapi.json`: статическая OpenAPI схема; живые `/docs` и `/openapi.json`.
- `artifacts/`: APK, эталоны, результаты сборки и тестов, если соответствующий этап завершился.
- `Dockerfile`, `.env.example`, `docs/BOTHOST.md`: подготовка к BotHost. Развёртывание в аккаунте пользователя не выполнялось.

## Backend локально

Linux, Python 3.12, `python -m pip install -r backend/requirements.txt`. Задать секрет ADMIN_API_TOKEN длиной не меньше 32 символов через окружение. Затем `python scripts/start.py`. Один worker обязателен. DATA_DIR по умолчанию `./data`, на BotHost `/app/data`. Для публичного доступа нужен TLS reverse proxy; Android запрещает cleartext. /health публичен, бизнес API — Bearer token приложения. Это начальный режим одного администратора; публичная многопользовательская регистрация не реализована.

Google Drive: `docs/GOOGLE-DRIVE.md`. Без настроенного Drive движок не начинает заполнять диск. Серверная загрузка не зависит от Android. Polling 5с при соединении, 15с при недоступности. Прогресс не генерируется клиентом.

## Android

JDK 17, Android SDK 36, build-tools 36.0.0. Создать локальный `local.properties` с `sdk.dir`. `./gradlew :app:assembleDebug`. Установить `app/build/outputs/apk/debug/app-debug.apk`. В Настройки → Подключение по API указать HTTPS URL backend и ADMIN_API_TOKEN. Пароль BotHost, Telegram token и Google secret в APK не используются. Клиентский токен зашифрован ключом Android Keystore; backup выключен.

Для передачи на телефон выбрать папку через SAF, затем готовый файл → Скачать на Android. Ограничения Wi-Fi/зарядки и скорости относятся к телефону. WorkManager ведёт foreground notification и состояние Room. Отмена уведомлением останавливает работу; возобновление — через Файлы. SAF provider должен поддерживать seek, statvfs и persistable grant; при отсутствии поддержки задача выдаёт ошибку, а не повреждает файл. Android ограничивает время foreground dataSync: передача не гарантирована бесконечно при закрытом приложении.

Release ключ отсутствует. Не генерировать и не коммитить пользовательский ключ автоматически; debug APK подписывается стандартным локальным debug key за пределами проекта. Для Play Billing и публикации нужна отдельная настройка.

## Планировщик

`MAX_WORKSPACE_BYTES=10*1024**3`, отдельный резерв 256 МиБ плюс две длины piece на каждый выбранный файл. Пакет максимизирует число файлов сортировкой по размеру, из файлов всех задач одновременно активен один пакет. Учитываются statvfs, фактические st_blocks и оставшееся место. `.torrent` 150ГБ+ принимается для метаданных; В текущем административном режиме тарифного ограничения выбранного объёма нет. Только при явном ADMIN_MODE=false действует прежняя модель Free 20GB / Premium 500GB. Права берутся с сервера. Одиночный файл, не помещающийся с резервом, не поддерживается, ошибка `workspace_or_single_file_limit`; потокового режима пока нет.

DiscoveryWorker периодически (от 15 минут, с ограничениями ОС) ставит готовые Drive-файлы на Android при включённой автопередаче.

Общие граничные pieces сохраняются до завершения всего пакета, сброса кэша, проверки всех Drive файлов и удаления handle. При ошибке upload локальные данные остаются. При перезапуске сохранённый журнал восстанавливает состав пакета и резерв, libtorrent перепроверяет оставшиеся данные; подтверждённые Drive IDs остаются в SQLite. Native fast-resume не реализован. Загрузка Drive возобновляется по зашифрованной resumable session; appProperties помогают найти завершённый upload после сбоя. Реальные внешние испытания этого восстановления ещё нужны.

## Telegram

Опциональные TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, BACKEND_URL в окружении сервера. `scripts/start.py` запускает модуль вместе с API. Команды `/tasks`, `/files`, `/starttask metadata_id 0,1`, `/pause id`, `/resume id`, `/delete id`; Magnet/.torrent/HTTPS → метаданные. Доступ только одному разрешённому Telegram user. Второго движка нет.

## Проверки

Установить `python -m pip install -r requirements-dev.txt`. Затем `python -m pytest backend/tests -q`, `python scripts/local_transfer.py`, `python -m scripts.scheduler_transfer`, `python scripts/audit.py`. Последний требует Playwright и Chromium. Для передачи проверочного текста используются собственные легальные данные. Локальный libtorrent-тест не подтверждает работоспособность внешнего BitTorrent на BotHost или Google Drive.
