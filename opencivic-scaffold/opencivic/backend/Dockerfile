# OpenCivic — Backend Dockerfile
# Multi-stage: builder reduces final image size
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
# Non-root user for security
RUN useradd --create-home --shell /bin/bash opencivic
COPY --from=builder /root/.local /home/opencivic/.local
COPY --chown=opencivic:opencivic . .
USER opencivic
ENV PATH=/home/opencivic/.local/bin:$PATH
ENV PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health/live || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
