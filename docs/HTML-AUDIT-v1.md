# Аудит HTML и карта переноса

Исходник сохранён без изменений. Все id перечислены ниже; полная структура и тексты: html-inventory.json.

| HTML id | Android Compose | Назначение/состояние |
|---|---|---|
| `app` (DIV, app) | App / shell | Cloud Torrent ClientЗагрузки               Google Cloud     Не подключён      2Активные260 ГБОб |
| `title` (H1, ) | App / shell | Загрузки |
| `cloudTop` (BUTTON, round) | App / navigate cloud |  |
| `v-downloads` (SECTION, view on) | App / downloads branch | Google Cloud     Не подключён      2Активные260 ГБОбъём торрентов   Активные загрузки2        G |
| `gcRow` (BUTTON, cloud-row) | App / downloads branch | Google Cloud     Не подключён |
| `gcStatus` (SPAN, status off) | App / downloads branch | Не подключён |
| `stA` (B, ) | App / downloads branch | 2 |
| `stS` (B, ) | App / downloads branch | 260 ГБ |
| `count` (SPAN, badge) | App / downloads branch | 2 |
| `dls` (DIV, ) | App / downloads branch | Game_Archive.isoCloud68%          218 ГБ · ещё ~2 мин85 МБ/с     Project_Assets.zipОчередь34%   |
| `addBtn` (BUTTON, add) | App / downloads branch | Добавить торрентMagnet / .torrent / URL |
| `v-files` (SECTION, view) | FilesScreen / SearchField | 120 ГБ6 файлов в облаке        Видео67 ГБАрхивы46 ГБОбразы6 ГБАудио1,4 ГБ      ВсеОбразыАрхивыВ |
| `fSum` (DIV, fsum) | FilesScreen / SearchField | 120 ГБ6 файлов в облаке        Видео67 ГБАрхивы46 ГБОбразы6 ГБАудио1,4 ГБ |
| `fQ` (INPUT, ) | FilesScreen / SearchField |  |
| `fChips` (DIV, chips) | FilesScreen / SearchField | ВсеОбразыАрхивыВидеоАудио |
| `fList` (DIV, ) | FilesScreen / SearchField | СегодняBackup_2026.zip12 ГБCloudSoundtrack.flac1,4 ГБCloudВчераDocumentary_4K.mkv58 ГБCloudUbun |
| `v-cloud` (SECTION, view) | App / cloud branch / ServerToggle | Google CloudНе подключён     Хранилище60%1,2 ТБ из 2 ТБсвободно 800 ГБ     Автоматизация     Ав |
| `gcToggle` (BUTTON, row-btn) | App / cloud branch / ServerToggle | Google CloudНе подключён |
| `gcSub` (SMALL, ) | App / cloud branch / ServerToggle | Не подключён |
| `gcSw` (SPAN, sw) | App / cloud branch / ServerToggle |  |
| `quota` (DIV, st) | App / cloud branch / ServerToggle | Хранилище60%1,2 ТБ из 2 ТБсвободно 800 ГБ |
| `qPct` (SPAN, pill b) | App / cloud branch / ServerToggle | 60% |
| `qBar` (I, ) | App / cloud branch / ServerToggle |  |
| `qTxt` (SPAN, ) | App / cloud branch / ServerToggle | 1,2 ТБ из 2 ТБ |
| `qFree` (SPAN, ) | App / cloud branch / ServerToggle | свободно 800 ГБ |
| `sync` (BUTTON, row-btn) | App / cloud branch / ServerToggle | АвтосинхронизацияЗагружать завершённые в облако |
| `optAuto` (BUTTON, row-btn) | App / cloud branch / ServerToggle | Автопередача на AndroidСразу после загрузки в облако |
| `optDel` (BUTTON, row-btn) | App / cloud branch / ServerToggle | Автоудаление из облакаОсвобождать место после передачи |
| `limRow` (BUTTON, row-btn) | App / cloud branch / ServerToggle | Одновременные загрузкиОстальные ждут в очереди1 |
| `limVal` (SPAN, val) | App / cloud branch / ServerToggle | 1 |
| `cleanCloud` (BUTTON, row-btn act-row) | App / cloud branch / ServerToggle | Очистить облакоУдалить завершённые загрузки |
| `v-settings` (SECTION, view) | App / settings branch / Setting / Toggle | Google Cloud     Подключение по APIНе подключён     Подписка     ТарифБесплатно, с ограничениям |
| `gcApiRow` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | Подключение по APIНе подключён |
| `gcApiSub` (SMALL, ) | App / settings branch / Setting / Toggle | Не подключён |
| `planRow` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | ТарифБесплатно, с ограничениямиFree |
| `planSub` (SMALL, ) | App / settings branch / Setting / Toggle | Бесплатно, с ограничениями |
| `planVal` (SPAN, val) | App / settings branch / Setting / Toggle | Free |
| `optSpeed` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | Ограничить скорость |
| `spdRow` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | Лимит скоростиДействует при включённом ограничении10 МБ/с |
| `spdVal` (SPAN, val) | App / settings branch / Setting / Toggle | 10 МБ/с |
| `optChg` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | Только при зарядкеПриостанавливать при разрядке |
| `optStart` (BUTTON, row-btn) | App / settings branch / Setting / Toggle | Автозапуск новыхНачинать сразу после добавления |
| `pauseAll` (BUTTON, row-btn act-row) | App / settings branch / Setting / Toggle | Приостановить всеДля всех активных загрузок |
| `pauseTxt` (SPAN, ) | App / settings branch / Setting / Toggle | Приостановить всеДля всех активных загрузок |
| `v-detail` (SECTION, view) | DetailScreen / Navigation Compose | Назад |
| `back` (BUTTON, back) | DetailScreen / Navigation Compose | Назад |
| `detailBody` (DIV, ) | DetailScreen / Navigation Compose |  |
| `modal` (DIV, modal) | App / add overlay / Choice / Input / Action / Cancel | Добавить торрент       ФайломВыбрать .torrent       СсылкойMagnet или URL       Отмена          |
| `stepChoice` (DIV, step on) | App / add overlay / Choice / Input / Action / Cancel | Добавить торрент       ФайломВыбрать .torrent       СсылкойMagnet или URL       Отмена |
| `pickFile` (BUTTON, choice) | App / add overlay / Choice / Input / Action / Cancel | ФайломВыбрать .torrent |
| `pickLink` (BUTTON, choice) | App / add overlay / Choice / Input / Action / Cancel | СсылкойMagnet или URL |
| `cancel` (BUTTON, cancel-full) | App / add overlay / Choice / Input / Action / Cancel | Отмена |
| `stepLink` (DIV, step) | App / add overlay / Choice / Input / Action / Cancel | Добавить по ссылке              НазадДобавить |
| `src` (INPUT, ) | App / add overlay / Choice / Input / Action / Cancel |  |
| `linkBack` (BUTTON, ) | App / add overlay / Choice / Input / Action / Cancel | Назад |
| `ok` (BUTTON, ok) | App / add overlay / Choice / Input / Action / Cancel | Добавить |
| `fileIn` (INPUT, ) | ActivityResultContracts.OpenDocument / ClientViewModel.metadata |  |
| `gcModal` (DIV, modal) | App / API overlay / encrypted DataStore | Google Cloud API         Ключ создаётся в Google Cloud Console: API и сервисы → Учётные данные. |
| `gcProj` (INPUT, ) | App / API overlay / encrypted DataStore |  |
| `gcKey` (INPUT, ) | App / API overlay / encrypted DataStore |  |
| `gcCancel` (BUTTON, ) | App / API overlay / encrypted DataStore | Отмена |
| `gcOk` (BUTTON, ok) | App / API overlay / encrypted DataStore | Подключить |
| `gcOff` (BUTTON, cancel-full) | App / API overlay / encrypted DataStore | Отключить |
| `planModal` (DIV, modal) | App / plans overlay / server subscription model | FREE$0Бесплатно навсегда1 активный торрентДо 20 ГБ на задачуGoogle DriveБазовая очередьРекламаО |
| `plFree` (DIV, plan cur) | App / plans overlay / server subscription model | FREE$0Бесплатно навсегда1 активный торрентДо 20 ГБ на задачуGoogle DriveБазовая очередьРекламаО |
| `stay` (BUTTON, pb) | App / plans overlay / server subscription model | Остаться |
| `plPrem` (DIV, plan) | App / plans overlay / server subscription model | PREMIUM$4.99 / мес.Расширенные возможностиДо 5 торрентовДо 500 ГБ на задачуGoogle Drive + телеф |
| `buy` (BUTTON, pb ok) | App / plans overlay / server subscription model | Подписаться |
| `fileModal` (DIV, modal) | App / file overlay / FileAction |  |
| `fileSheet` (DIV, sheet) | App / file overlay / FileAction |  |
| `toast` (DIV, toast) | App / toast overlay / UiState.message |  |

## Геометрия
Внешний фон #000; body: 16px по горизонтали, 12px по вертикали; app: max 430×860px, радиус 26px, padding 32/20/14px. На viewport 430×900 app 398×860. Header 14px/29px; row 17px; torrent title 19px; muted #9aa3b2. Все CSS и SVG сохраняются в reference.

## Поведение
Навигация: downloads/files/cloud/settings + detail, Cloud/Android segmented control. Модальные: добавление (choice/link/file), API, тарифы, файл. Toast 1800ms, press scale .97/.98, bar transition 400ms, switch 200ms, toast 250ms, fs-bar grow 800ms с шагом 80ms, fade scroll 36px.

## Замена демонстраций
Math.random размеров и скоростей, setInterval роста прогресса, fStatic, 940ГБ базового расхода, 2ТБ ёмкости, копирование ссылки toast, ph=100 и plan=prem заменяются API/реальными локальными передачами. Подключение Google Cloud/Project ID/key заменяется BotHost HTTPS URL/администраторским API token. Drive требует отдельный OAuth.

## Тарифы и конфликт требований
HTML: Free 1 задача/20GB/без телефона; Premium 5/500GB/телефон, $4.99. Требование принимать 150GB+ независимо от размера конфликтует с Free 20GB. В backend размер метаданных не отклоняется; квота применяется к выбранным файлам при старте. Это явно возвращается ошибкой quota_exceeded.

## Статус соответствия
Карта — план соответствия, а не подтверждение реализации каждого id. Окончательная проверка требует Android screenshots, состояния с теми же данными и сравнения.
## Проверка существующего проекта

В /workspace не было исходников бота. Поиск подключённых GitHub-репозиториев по `torrent` вернул пустой список. Пользователь подтвердил хост bothost.ru, но URL приложения и репозиторий не предоставлены. Создан aiogram API-клиент общей очереди; миграция существующего бота не заявляется.

## Соответствие компонентов без id

| HTML/CSS | Kotlin Compose | Состояние переноса |
|---|---|---|
| body, .app | App: outer Box + capped Column | Предел 430×860, margin/padding и radius 26 |
| .top, .eyebrow, h1, .round | App header / Txt / IconSvg | Исходные SVG, размер 40, 14/29sp; font weight и letter spacing уточнены по первому native screenshot |
| .view, .view.on | Navigation Compose destinations | Четыре раздела + detail, scroll; оригинальный mask fade ещё нужен |
| .cloud-row, .l, .status, .status.off | App downloads connection Row | BotHost, настоящий API state; status SVG восстановлен после сравнения |
| .stats, .stat | App downloads Card / PaddingValues | 2 колонки, 10dp gap, 14/16/15 padding, 28sp line-height 1 |
| .sec, h2, .badge | App downloads section / Box | Badge 26×26 восстановлен после сравнения |
| .dl, .h, .n, .pl, .pc, .bar, .f, .eta, .spd | TorrentCard / Bar | Размеры и прогресс API; нет случайных значений; полная проверка карточек с одинаковыми backend данными ещё нужна |
| .note | Txt | Серверная ошибка/инструкция вместо вымышленного прогресса |
| .add, .ic, .tx, .chev | App downloads bottom Row | Оригинальные plus/chevron SVG и два текста |
| nav, nav button.on | App navigation Row | Оригинальные 4 SVG, 25dp, gap 5dp, 14sp |
| .list, .grp, .row-btn, .val, .act-row | Settings routes / Setting | Отдельные настройки Android и server; часть управление лимитом движка ограничена безопасным parallelism=1 |
| .sw, .sw.on | Toggle / ServerToggle | Собственный 42×24 switch, шар 18; DataStore или server API |
| .back, .seg, .st, .nm, .pill, .act, .act2 | DetailScreen | Серверный и локальный прогресс; полный визуальный приёмочный тест не завершён |
| .modal, .sheet, .step, .acts, .cancel-full | App overlay / Column / Input / Action / Cancel | Область overlay приведена к bounds .app; Android file picker вместо file input |
| .choice, .choice .tx, .choice .chev | Choice | 78dp row, radius22, file/link SVG |
| .plans, .plan, .cur, .pr, .d, .dv, .pb | App plans sheet | Free/Premium и $4.99; кнопка не активирует подписку; тонкие отступы/анимации требуют проверки |
| .ad | Серверная модель ads / plans copy | Рекламный SDK не подключён; демонстрационный ad не заменён фиктивной рекламой |
| .fsum, .big, .sub, .fs-bar, .fs-leg | FilesScreen summary | Сумма настоящих файлов, группы категорий; анимация fsgrow не завершена |
| .fsearch, .chips, button.on | Input / horizontal chips | Поиск и фильтр всех 5 типов; исходный search SVG перенесён, native проверка ещё нужна |
| .fgh, .fgrp, .fr, .ft, .nm2, .lc, .pi, .sz | FilesScreen grouped Column / file Row | Цвета/категории/исходные SVG; группировка по датам и единая индикация Android реализованы; native проверка ещё нужна |
| .fempty | FilesScreen empty state | Нет вымышленных файлов; исходный empty layout ещё требует точной доводки |
| .fhead, .fa, .fa.ph, .fa.del, .fa.dis | App file sheet | Реальные download/link/delete/Drive действия; полная геометрия sheet ещё требует доводки |
| .toast, .toast.on | UiState.message | Toast overlay на 1800ms реализован; точная animation ещё требует сравнения |
| SVG path/rect/circle | Assets icon0…39 + AndroidSVG Canvas | Геометрия сохраняется; template FT развёрнут в 5 отдельных SVG |
| input[type=file] | ActivityResultContracts.OpenDocument | SAF, ограниченное чтение .torrent до 4 МиБ |
| env(safe-area-inset-*) | systemBarsPadding | Техническая Android адаптация; проверяется по native кадру |

Инвентарь `full-dom-inventory.json` содержит каждый исходный узел, включая вложенные span/path без id. Полный JS-инвентарь — `javascript-inventory.json`. Таблицы здесь показывают реализацию и явно отмечают незавершённые части, а не утверждают, что интерфейс уже принят 1:1.
