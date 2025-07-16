# PostgreSQL Backup & Restore Tool 哥哥们帮我点颗🌟呗

一个功能强大的PostgreSQL数据库备份和恢复工具，提供Web界面管理，支持多种恢复策略和自动化备份。

## 🚀 功能特性

### 核心功能
- **📦 智能备份**：支持压缩备份，自动管理备份文件
- **🔄 多种恢复策略**：
  - **增量恢复**（推荐）：只恢复缺失数据，最安全
  - **普通恢复**：使用备份文件默认策略
  - **完全恢复**：清空数据库完全恢复（危险操作）
- **⏰ 定时备份**：支持自动定时备份，可配置间隔时间
- **🧹 自动清理**：自动清理过期备份文件
- **📊 实时监控**：数据库状态、备份状态实时监控

### 高级功能
- **🔍 备份描述**：为每个备份添加描述信息
- **📋 数据库信息**：查看表结构、数据统计
- **⚙️ 配置管理**：Web界面配置数据库连接和备份参数
- **🔒 版本兼容性检查**：恢复前检查数据库版本兼容性
- **📱 响应式界面**：支持桌面和移动设备访问

## 🛠️ 技术栈

- **后端**：Python 3.11 + FastAPI
- **前端**：Bootstrap 5 + JavaScript
- **数据库**：PostgreSQL 17
- **容器化**：Docker + Docker Compose
- **备份工具**：pg_dump + psql

## 📋 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 10GB 可用磁盘空间

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd postgres-backup-tool
```

### 2. 配置数据库连接

编辑 `config.json` 文件，配置你的PostgreSQL数据库连接信息：

```json
{
  "database": {
    "host": "your-database-host",
    "port": 5432,
    "database": "your-database-name",
    "username": "your-username",
    "password": "your-password"
  },
  "backup": {
    "path": "./backups",
    "interval": 12,
    "max_backups": 30,
    "compression": true,
    "cleanup": {
      "enabled": true,
      "interval": 7,
      "keep_days": 30
    }
  }
}
```

### 3. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backup-tool
```

### 4. 访问Web界面

打开浏览器访问：`http://localhost:8888`

## 📖 使用指南

### 创建备份

1. 点击左侧面板的 **"创建备份"** 按钮
2. 可选择添加备份描述
3. 选择是否启用压缩
4. 点击确认开始备份

### 恢复备份

1. 在备份列表中找到要恢复的备份
2. 点击 **"恢复"** 按钮
3. 选择恢复类型：
   - **增量恢复**（推荐）：最安全，只恢复缺失数据
   - **普通恢复**：使用默认策略
   - **完全恢复**：清空数据库完全恢复（⚠️ 危险）
4. 确认恢复操作

### 配置定时备份

1. 点击 **"设置"** 按钮
2. 在备份配置标签页中设置：
   - 备份间隔（小时）
   - 最大备份数量
   - 是否启用压缩
   - 自动清理设置
3. 保存配置
4. 点击 **"启动"** 开始定时备份

### 管理备份

- **查看备份列表**：显示所有备份文件及其状态
- **删除备份**：删除不需要的备份文件
- **下载备份**：下载备份文件到本地
- **查看备份详情**：查看备份的详细信息

## ⚙️ 配置说明

### 数据库配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `host` | 数据库主机地址 | localhost |
| `port` | 数据库端口 | 5432 |
| `database` | 数据库名称 | - |
| `username` | 用户名 | - |
| `password` | 密码 | - |

### 备份配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `path` | 备份文件存储路径 | ./backups |
| `interval` | 定时备份间隔（小时） | 12 |
| `max_backups` | 最大备份文件数量 | 30 |
| `compression` | 是否启用压缩 | true |
| `cleanup.enabled` | 是否启用自动清理 | true |
| `cleanup.interval` | 清理检查间隔（天） | 7 |
| `cleanup.keep_days` | 保留备份天数 | 30 |

## 🔧 高级配置

### 自定义端口

编辑 `docker-compose.yml` 文件，修改端口映射：

```yaml
ports:
  - "8888:8000"  # 修改8888为你想要的端口
```

### 外部数据库

如果要连接外部PostgreSQL数据库，修改 `config.json` 中的数据库配置：

```json
{
  "database": {
    "host": "your-external-db-host",
    "port": 5432,
    "database": "your-database",
    "username": "your-username",
    "password": "your-password"
  }
}
```

### 备份存储路径

修改备份存储路径到外部目录：

```yaml
volumes:
  - ./backups:/app/backups  # 映射到外部目录
```

## 🐛 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 查看详细日志
   docker-compose logs backup-tool
   
   # 检查端口占用
   netstat -tulpn | grep 8888
   ```

2. **数据库连接失败**
   - 检查数据库配置是否正确
   - 确认数据库服务是否运行
   - 检查网络连接

3. **备份失败**
   - 检查数据库用户权限
   - 确认备份目录权限
   - 查看磁盘空间是否充足

4. **恢复失败**
   - 检查备份文件完整性
   - 确认数据库版本兼容性
   - 查看详细错误日志

### 日志查看

```bash
# 查看应用日志
docker-compose logs -f backup-tool

# 查看数据库日志
docker-compose logs -f postgres

# 查看pgAdmin日志
docker-compose logs -f pgadmin
```

## 🔒 安全建议

1. **修改默认密码**：部署后立即修改数据库密码
2. **限制访问**：配置防火墙，只允许必要IP访问
3. **定期备份**：定期备份配置文件和数据
4. **监控日志**：定期检查应用日志，发现异常及时处理
5. **更新维护**：定期更新Docker镜像和依赖包

## 📝 开发说明

### 项目结构

```
postgres-backup-tool/
├── app/                    # 后端应用代码
│   ├── main.py            # FastAPI主应用
│   ├── backup.py          # 备份管理
│   ├── restore.py         # 恢复管理
│   ├── models.py          # 数据模型
│   └── config.py          # 配置管理
├── templates/             # HTML模板
│   └── index.html         # 主页面
├── static/                # 静态文件
│   └── app.js            # 前端JavaScript
├── config.json           # 配置文件
├── requirements.txt      # Python依赖
├── Dockerfile           # Docker镜像配置
├── docker-compose.yml   # Docker Compose配置
└── README.md           # 项目说明
```

### 本地开发

```bash
# 安装Python依赖
pip install -r requirements.txt

# 启动开发服务器
python -m app.main

# 访问开发环境
http://localhost:8000
```

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

如有问题，请通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件至：[1900098962@qq.com]

---

**注意**：使用完全恢复功能前请务必备份重要数据，该操作会清空整个数据库！ 