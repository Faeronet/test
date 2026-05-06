FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY common /app/common
RUN pip install /app/common
COPY segmentation-service/pyproject.toml /app/svc/pyproject.toml
COPY segmentation-service/app /app/svc/app
RUN pip install /app/svc
ENV SERVICE_NAME=segmentation-service
WORKDIR /app/svc
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
