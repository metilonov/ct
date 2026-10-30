import os, subprocess, sys, signal

api = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        os.getenv("PORT", "8000"),
        "--workers",
        "1",
        "--no-access-log",
    ]
)
bot = (
    subprocess.Popen([sys.executable, "-m", "backend.bot"])
    if os.getenv("TELEGRAM_BOT_TOKEN")
    else None
)


def stop(*args):
    if bot:
        bot.terminate()
    api.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
code = api.wait()
if bot:
    bot.terminate()
    bot.wait()
sys.exit(code)
