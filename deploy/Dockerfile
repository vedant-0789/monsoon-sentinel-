# Monsoon Sentinel API container (Render free tier: 512 MB RAM). Build context = repo root.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # keep memory low: system allocator for Arrow, fewer glibc arenas
    ARROW_DEFAULT_MEMORY_POOL=system \
    MALLOC_ARENA_MAX=2 \
    MS_DB=/tmp/reports.sqlite \
    PORT=10000

RUN useradd -m -u 1000 app
WORKDIR /home/app/srv

COPY --chown=app requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY --chown=app configs/ configs/
COPY --chown=app src/ src/
COPY --chown=app api/ api/
COPY --chown=app deploy/artifacts/models/ models/
COPY --chown=app deploy/artifacts/data/ data/

USER app
EXPOSE 10000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
