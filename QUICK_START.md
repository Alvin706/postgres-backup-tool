# 快速开始指南

## 🚀 1分钟快速部署

### 方法1：Docker一键部署（推荐）

```bash
# 1. 克隆项目
git clone <repository-url>
cd postgres-backup-tool

# 2. 启动服务（包含测试数据库）
docker-compose up -d

# 3. 访问应用
# Web界面: http://localhost:8000
# API文档: http://localhost:8000/docs
# pgAdmin: http://localhost:8080 (admin@example.com / admin)
```

### 方法2：本地部署

```bash
# 1. 进入项目目录
cd postgres-backup-tool

# 2. 配置数据库连接
cp config.json.example config.json
# 编辑config.json，设置正确的数据库连接信息

# 3. 快速启动
./start.sh
```

## 🎯 主要功能演示

### 1. 创建备份
- 点击"创建备份"按钮
- 输入备份描述（可选）
- 选择是否压缩
- 点击确认创建

### 2. 恢复备份
- 在备份列表中选择要恢复的备份
- 点击恢复按钮
- 确认恢复操作

### 3. 定时备份
- 在"定时备份"面板中点击"启动"
- 系统将每12小时自动备份
- 可以点击"立即备份"手动触发

### 4. 监控状态
- 查看数据库信息
- 监控备份任务状态
- 查看定时任务运行情况

## 🔧 配置说明

### 数据库配置
```json
{
    "database": {
        "host": "localhost",      // 数据库主机
        "port": 5432,            // 数据库端口
        "database": "mydb",      // 数据库名
        "username": "user",      // 用户名
        "password": "password"   // 密码
    }
}
```

### 备份配置
```json
{
    "backup": {
        "storage_path": "./backups",  // 备份文件存储路径
        "interval_hours": 12,         // 备份间隔（小时）
        "max_backups": 30,           // 最大备份数量
        "compression": true          // 是否压缩
    }
}
```

## 🛠️ 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查数据库是否运行
   - 验证连接信息是否正确
   - 确认防火墙设置

2. **备份失败**
   - 确认`pg_dump`已安装
   - 检查数据库权限
   - 验证存储路径可写

3. **恢复失败**
   - 确认`psql`已安装
   - 检查备份文件完整性
   - 验证目标数据库存在

### 系统要求

- Python 3.11+
- PostgreSQL 12+
- pg_dump/psql 工具
- 足够的存储空间

## 📈 性能优化

1. **存储优化**
   - 启用压缩减少空间占用
   - 定期清理旧备份
   - 使用SSD存储提升性能

2. **网络优化**
   - 本地部署减少网络延迟
   - 使用专用网络连接

3. **系统优化**
   - 充足的内存配置
   - 快速的CPU处理能力

## 🔐 安全建议

1. **访问控制**
   - 限制Web界面访问IP
   - 使用反向代理添加认证
   - 定期更新密码

2. **数据安全**
   - 加密备份文件
   - 安全的存储位置
   - 定期备份验证

3. **监控告警**
   - 备份失败告警
   - 存储空间监控
   - 系统资源监控

## 🌟 高级用法

### API调用示例

```python
import requests

# 创建备份
response = requests.post('http://localhost:8000/api/backups', 
                        json={'description': '手动备份', 'compress': True})

# 获取备份列表
backups = requests.get('http://localhost:8000/api/backups').json()

# 恢复备份
requests.post('http://localhost:8000/api/restore', 
             json={'backup_id': 'backup_id', 'force': False})
```

### 自定义脚本

```bash
#!/bin/bash
# 自定义备份脚本
curl -X POST http://localhost:8000/api/backups \
  -H "Content-Type: application/json" \
  -d '{"description": "定时脚本备份", "compress": true}'
```

## 📞 获取帮助

- 📖 查看完整文档：[README.md](README.md)
- 🐛 报告问题：创建GitHub Issue
- 💡 功能建议：提交Pull Request
- 📧 联系开发者：[your-email@example.com]

---

🎉 **恭喜！您的PostgreSQL备份工具已准备就绪！** 