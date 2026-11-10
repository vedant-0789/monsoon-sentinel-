# Monsoon Sentinel API — container for Hugging Face Spaces (Docker SDK, port 7860).
# The GitHub Action assembles the build context; see .github/workflows/deploy-api.yml.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MS_DB=/tmp/reports.sqlite

# Spaces run containers as uid 1000
RUN useradd -m -u 1000 app
WORKDIR /home/app/srv

COPY --chown=app requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY --chown=app configs/ configs/
COPY --chown=app src/ src/
COPY --chown=app api/ api/
COPY --chown=app models/ models/
COPY --chown=app data/ data/

USER app
EXPOSE 7860
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/api/health')" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
