FROM python:3.12-slim

WORKDIR /app

# Install system dependencies（含 gosu，用于 entrypoint 降权；Debian 源自带，避免依赖 GitHub/keyserver）
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && gosu --version

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

# 入口脚本 — 以 root 启动，修复权限后降权到 bias 用户执行 CMD
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8000

CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2"]
