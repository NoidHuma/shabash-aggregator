FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# По умолчанию — локальный супервизор всех воркеров. В docker compose каждый
# воркер запускается своим сервисом с собственной командой.
CMD ["python", "-m", "app.run_all"]
