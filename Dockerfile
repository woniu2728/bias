FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create media and static directories
RUN mkdir -p media static

# 创建容器内日志目录（非 root 用户可写）
RUN mkdir -p /var/log/bias && chown -R 1000:1000 /var/log/bias

# 创建非 root 用户运行应用（遵循最小权限原则）
RUN useradd -m -u 1000 -s /bin/bash bias && \
    chown -R bias:bias /app

USER bias

EXPOSE 8000

CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2"]
