"""aiogram 3 transport: the API is the sole owner of torrent state."""

import os, asyncio, base64, io
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message


async def main():
    bot = Bot(os.environ["TELEGRAM_BOT_TOKEN"])
    dp = Dispatcher()
    allowed = int(os.environ["TELEGRAM_ADMIN_ID"])
    async with httpx.AsyncClient(
        base_url=os.environ["BACKEND_URL"],
        headers={"Authorization": "Bearer " + os.environ["ADMIN_API_TOKEN"]},
        timeout=90,
    ) as api:

        async def request(m, method, path, **kwargs):
            try:
                r = await api.request(method, path, **kwargs)
                if r.is_error:
                    await m.answer(
                        "API: "
                        + str(r.status_code)
                        + " "
                        + str(r.json().get("error", {}).get("code", "request_failed"))
                    )
                    return None
                return r.json()
            except (httpx.HTTPError, ValueError):
                await m.answer("Backend недоступен")
                return None

        async def describe(m, body):
            d = await request(m, "POST", "/torrents/metadata", json=body)
            if not d:
                return
            lines = [
                f"{d['name']}: {len(d['files'])} файлов, {d['total_bytes']} байт",
                "metadata_id: " + d["id"],
            ]
            lines += [
                f"{f['index']}: {f['path']} ({f['size']} Б)" for f in d["files"][:20]
            ]
            lines += [
                "/starttask "
                + d["id"]
                + " 0,1 — выбранные индексы; полный список в Android/API"
            ]
            await m.answer("\n".join(lines)[:4000])

        @dp.message(Command("start", "help"))
        async def help(m: Message):
            if m.from_user.id != allowed:
                return
            await m.answer(
                "Magnet, HTTPS .torrent или файл .torrent → метаданные.\n/tasks /files\n/starttask metadata_id 0,1\n/pause task_id /resume task_id /delete task_id\nВсе данные общие с Android."
            )

        @dp.message(Command("tasks", "files"))
        async def listing(m: Message):
            if m.from_user.id != allowed:
                return
            isfiles = m.text.split()[0].split("@")[0] == "/files"
            data = await request(m, "GET", "/files" if isfiles else "/torrents")
            if data is None:
                return
            await m.answer(
                (
                    "\n".join(
                        x["id"]
                        + " · "
                        + x.get("name", x.get("path", ""))
                        + " — "
                        + x["state"]
                        for x in data
                    )
                    or "Нет данных"
                )[:4000]
            )

        @dp.message(Command("starttask"))
        async def create(m: Message):
            if m.from_user.id != allowed:
                return
            try:
                _, mid, selection = m.text.split(maxsplit=2)
                indices = [int(i) for i in selection.split(",")]
            except ValueError:
                await m.answer("/starttask metadata_id 0,1")
                return
            r = await request(
                m, "POST", "/torrents", json={"metadata_id": mid, "selected": indices}
            )
            if r:
                await m.answer(r["id"] + " — " + r["state"])

        @dp.message(Command("pause", "resume", "delete"))
        async def change(m: Message):
            if m.from_user.id != allowed:
                return
            parts = m.text.split()
            if len(parts) != 2:
                await m.answer("Укажите task_id")
                return
            command = parts[0].split("@")[0][1:]
            tid = parts[1]
            if len(tid) != 32 or not all(c in "0123456789abcdef" for c in tid):
                await m.answer("Неверный task_id")
                return
            r = await request(
                m,
                "DELETE" if command == "delete" else "POST",
                "/torrents/" + tid + ("" if command == "delete" else "/" + command),
            )
            if r:
                await m.answer("Удалено" if command == "delete" else r["state"])

        @dp.message(F.document)
        async def document(m: Message):
            if m.from_user.id != allowed:
                return
            d = m.document
            if (
                not (d.file_name or "").endswith(".torrent")
                or (d.file_size or 0) > 4 * 1024 * 1024
            ):
                await m.answer("Нужен .torrent до 4 МиБ")
                return
            data = io.BytesIO()
            await bot.download(d, destination=data)
            await describe(
                m, {"torrent_base64": base64.b64encode(data.getvalue()).decode()}
            )

        @dp.message(F.text.startswith("magnet:?") | F.text.startswith("https://"))
        async def metadata(m: Message):
            if m.from_user.id != allowed:
                return
            await describe(m, {"source": m.text})

        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
