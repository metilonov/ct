FROM python:3.12-slim
WORKDIR /usr/src/cloud-torrent
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend ./backend
COPY scripts/start.py ./start.py
ENV DATA_DIR=/app/data PORT=8000 PYTHONUNBUFFERED=1
# BotHost persists /app/data. One worker is required: one scheduler, one set of handles.
CMD ["python", "start.py"]
