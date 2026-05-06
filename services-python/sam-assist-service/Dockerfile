FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY common /app/common
RUN pip install /app/common
COPY sam-assist-service/pyproject.toml /app/svc/pyproject.toml
COPY sam-assist-service/app /app/svc/app
RUN pip install /app/svc
ENV SERVICE_NAME=sam-assist-service
WORKDIR /app/svc
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
