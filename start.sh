#!/bin/bash

# PostgreSQL Backup & Restore Tool 启动脚本

echo "🚀 PostgreSQL Backup & Restore Tool"
echo "=================================="

# 检查Python版本
if ! python3 --version &> /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "❌ config.json 配置文件不存在"
    echo "请根据 config.json.example 创建配置文件"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt

# 检查PostgreSQL客户端工具
if ! command -v pg_dump &> /dev/null; then
    echo "⚠️  警告: pg_dump 未找到，请安装 postgresql-client"
    echo "Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "macOS: brew install postgresql"
fi

# 创建备份目录
mkdir -p backups

# 启动应用
echo "🌟 启动应用..."
echo "访问地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止应用"
echo ""

python -m app.main 