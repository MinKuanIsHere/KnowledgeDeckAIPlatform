FROM python:3.12-slim

WORKDIR /app

# Install runtime + dev deps from explicit lock-style files so the build is
# reproducible from the txt files alone.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app ./app
COPY alembic.ini ./alembic.ini

EXPOSE 8080

# `exec` makes uvicorn replace the wrapping `sh` as PID 1 so SIGTERM from
# `docker stop` reaches uvicorn directly instead of being swallowed by dash
# (which doesn't forward signals by default).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8080"]
