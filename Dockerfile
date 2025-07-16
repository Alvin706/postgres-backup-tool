FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖和PostgreSQL 17客户端
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    lsb-release \
    gcc \
    curl \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY config.json ./

# 创建备份目录
RUN mkdir -p /app/backups

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "app.main"] 