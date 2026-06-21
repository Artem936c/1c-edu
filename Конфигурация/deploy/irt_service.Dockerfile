# Образ микросервиса IRT (FastAPI).
# Контекст сборки — каталог Микросервис_IRT (см. docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Зависимости среды выполнения (синхронизированы с pyproject.toml).
RUN pip install --upgrade pip && pip install \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.7" \
    "numpy>=1.26" \
    "scipy>=1.13" \
    "httpx>=0.27"

# Код приложения.
COPY app ./app

EXPOSE 8001

# Проба доступности — эндпоинт /health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8001/health').status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
