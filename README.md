# PostgreSQL Backup & Restore Tool
问题找到了！PostgreSQL的pg_hba.conf配置不允许从新的IP地址192.168.35.41连接。我需要更新PostgreSQL配置：
echo "host    all             all             192.168.35.0/24         scram-sha-256" | sudo tee -a /Library/PostgreSQL/17/data/pg_hba.conf


一个现代化的PostgreSQL数据库备份、恢复和版本管理工具，基于FastAPI和Vue.js构建。

## 功能特性

- ✅ **自动备份**: 每12小时自动备份PostgreSQL数据库
- ✅ **压缩存储**: 自动压缩备份文件，节省存储空间
- ✅ **版本管理**: 集成Alembic版本控制系统
- ✅ **可视化界面**: 现代化的Web管理界面
- ✅ **一键恢复**: 支持选择任意备份进行数据库恢复
- ✅ **定时任务**: 灵活的备份调度管理
- ✅ **Docker部署**: 完整的Docker容器化支持

## 技术栈

- **后端**: FastAPI + Python 3.11
- **前端**: Bootstrap 5 + Vanilla JavaScript
- **数据库**: PostgreSQL
- **版本控制**: Alembic
- **定时任务**: APScheduler
- **容器化**: Docker + Docker Compose

## 快速开始

### 1. 使用Docker部署（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd postgres-backup-tool

# 修改配置文件
cp config.json.example config.json
# 编辑config.json，配置数据库连接信息

# 启动服务
docker-compose up -d
```

### 2. 本地部署

```bash
# 安装依赖
pip install -r requirements.txt

# 确保PostgreSQL客户端工具已安装
# Ubuntu/Debian: sudo apt-get install postgresql-client
# macOS: brew install postgresql

# 配置数据库连接
cp config.json.example config.json
# 编辑config.json

# 启动应用
python -m app.main
```

## 配置说明

编辑 `config.json` 文件：

```json
{
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "your_database",
        "username": "your_username",
        "password": "your_password"
    },
    "backup": {
        "storage_path": "./backups",
        "interval_hours": 12,
        "max_backups": 30,
        "compression": true
    },
    "app": {
        "title": "PostgreSQL Backup & Restore Tool",
        "host": "0.0.0.0",
        "port": 8000,
        "debug": false
    }
}
```

## 使用指南

### 访问界面

启动后访问：http://localhost:8000

### 主要功能

1. **备份管理**
   - 手动创建备份
   - 查看备份列表
   - 删除旧备份

2. **恢复操作**
   - 选择备份文件恢复
   - 版本兼容性检查
   - 强制恢复选项

3. **定时任务**
   - 启动/停止自动备份
   - 调整备份间隔
   - 立即触发备份

4. **系统监控**
   - 数据库连接状态
   - 备份任务状态
   - 数据库信息展示

## API文档

启动应用后访问：http://localhost:8000/docs

主要API端点：

- `GET /api/backups` - 获取备份列表
- `POST /api/backups` - 创建新备份
- `POST /api/restore` - 恢复备份
- `GET /api/schedule/status` - 获取调度状态
- `POST /api/schedule/start` - 启动定时任务

## 系统要求

- Python 3.11+
- PostgreSQL 12+
- pg_dump/psql 工具
- Docker（可选）

## 备份文件格式

- **文件名**: `backup_YYYYMMDD_HHMMSS.sql.gz`
- **压缩**: 使用gzip压缩
- **格式**: PostgreSQL dump格式
- **元数据**: 包含Alembic版本信息

## 安全注意事项

1. 确保备份文件存储路径安全
2. 定期清理过期备份
3. 数据库连接信息加密存储
4. 限制Web界面访问权限

## 故障排除

### 常见问题

1. **备份失败**: 检查pg_dump是否安装，数据库连接是否正常
2. **恢复失败**: 确认备份文件完整性，检查psql工具
3. **定时任务不工作**: 检查调度器状态，查看日志输出

### 日志查看

```bash
# Docker环境
docker-compose logs backup-tool

# 本地环境
python -m app.main
```

## 开发指南

### 项目结构

```
postgres-backup-tool/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI应用
│   ├── models.py        # 数据模型
│   ├── backup.py        # 备份逻辑
│   ├── restore.py       # 恢复逻辑
│   └── scheduler.py     # 定时任务
├── templates/
│   └── index.html       # 前端页面
├── static/
│   └── app.js           # 前端逻辑
├── backups/             # 备份文件存储
├── config.json          # 配置文件
├── requirements.txt     # Python依赖
├── docker-compose.yml   # Docker部署
└── Dockerfile          # Docker镜像
```

### 扩展功能

1. 添加更多数据库支持
2. 实现备份文件云存储
3. 集成监控告警系统
4. 支持备份策略配置

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交代码
4. 创建Pull Request

## 许可证

MIT License

## 支持

如有问题请创建Issue或联系开发者。 