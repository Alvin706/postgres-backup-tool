import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from typing import List, Optional
from datetime import datetime

from .models import (
    Config, BackupInfo, BackupRequest, BackupResponse, 
    RestoreRequest, RestoreResponse, ScheduleStatus,
    DatabaseConfigUpdate, BackupConfigUpdate, AppConfigUpdate,
    ConfigTestRequest, ConfigTestResponse, ConfigUpdateResponse,
    CleanupResponse, BatchDeleteRequest
)
from .backup import BackupManager
from .restore import RestoreManager
from .scheduler import BackupScheduler
from .config_manager import ConfigManager


# 全局变量
config_manager: Optional[ConfigManager] = None
backup_manager: Optional[BackupManager] = None
restore_manager: Optional[RestoreManager] = None
scheduler: Optional[BackupScheduler] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    if config_manager is None:
        raise HTTPException(status_code=500, detail="配置管理器未初始化")
    return config_manager


def get_backup_manager() -> BackupManager:
    """获取备份管理器实例"""
    if backup_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="备份服务不可用，请先配置数据库连接"
        )
    return backup_manager


def get_restore_manager() -> RestoreManager:
    """获取恢复管理器实例"""
    if restore_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="恢复服务不可用，请先配置数据库连接"
        )
    return restore_manager


def get_scheduler() -> BackupScheduler:
    """获取调度器实例"""
    if scheduler is None:
        raise HTTPException(
            status_code=503, 
            detail="调度服务不可用，请先配置数据库连接"
        )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global config_manager, backup_manager, restore_manager, scheduler
    
    # 启动时初始化
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # 检查数据库是否可用
    if config and config_manager.is_database_available():
        try:
            backup_manager = BackupManager(config.database, config.backup)
            restore_manager = RestoreManager(config.database, config.backup)
            scheduler = BackupScheduler(config.database, config.backup)
            
            # 启动定时任务
            await scheduler.start()
            print("✅ 数据库连接正常，所有服务已启动")
        except Exception as e:
            print(f"⚠️ 数据库连接失败，但应用仍可正常启动: {e}")
            print("💡 请通过Web界面重新配置数据库连接")
    else:
        print("⚠️ 数据库配置不可用，应用将以配置模式启动")
        print("💡 请通过Web界面配置数据库连接")
    
    yield
    
    # 关闭时清理
    if scheduler:
        await scheduler.stop()


# 创建FastAPI应用
app = FastAPI(
    title="PostgreSQL Backup & Restore Tool",
    description="用于PostgreSQL数据库备份、恢复和版本管理的工具",
    version="1.0.0",
    lifespan=lifespan
)

# 静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# API路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/test-close-confirm", response_class=HTMLResponse)
async def test_close_confirm():
    """测试页面关闭确认功能"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>页面关闭确认测试</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .container { max-width: 800px; margin-top: 50px; }
            .status { margin: 20px 0; padding: 15px; border-radius: 8px; font-weight: bold; }
            .enabled { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .disabled { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="card-header">
                    <h1 class="card-title text-center">页面关闭确认功能测试</h1>
                </div>
                <div class="card-body">
                    <div class="status" id="status">
                        <span id="statusText">正在初始化...</span>
                    </div>
                    
                    <div class="alert alert-info">
                        <h5>测试说明：</h5>
                        <ol>
                            <li>页面加载1秒后，关闭确认功能将自动启用</li>
                            <li>点击任何按钮后，页面将被标记为有未保存更改</li>
                            <li>尝试关闭浏览器标签页，应该会看到确认对话框</li>
                            <li>使用键盘快捷键 Ctrl+W (Windows) 或 Cmd+W (Mac) 也会触发确认</li>
                        </ol>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <button class="btn btn-primary w-100 mb-2" onclick="enableCloseConfirm()">启用关闭确认</button>
                            <button class="btn btn-secondary w-100 mb-2" onclick="disableCloseConfirm()">禁用关闭确认</button>
                        </div>
                        <div class="col-md-6">
                            <button class="btn btn-warning w-100 mb-2" onclick="simulateUnsavedChanges()">模拟未保存更改</button>
                            <button class="btn btn-success w-100 mb-2" onclick="clearUnsavedChanges()">清除未保存更改</button>
                        </div>
                    </div>
                    
                    <div class="mt-4">
                        <h5>当前状态：</h5>
                        <p><strong>关闭确认：</strong><span id="confirmStatus" class="badge bg-success ms-2">启用</span></p>
                        <p><strong>未保存更改：</strong><span id="unsavedStatus" class="badge bg-secondary ms-2">无</span></p>
                    </div>
                    
                    <div class="mt-4">
                        <a href="/" class="btn btn-outline-primary">返回主应用</a>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // 页面关闭确认相关变量
            let shouldConfirmClose = true;
            let hasUnsavedChanges = false;
            let allowClose = false;

            // 更新状态显示
            function updateStatus() {
                const statusDiv = document.getElementById('status');
                const statusText = document.getElementById('statusText');
                const confirmStatus = document.getElementById('confirmStatus');
                const unsavedStatus = document.getElementById('unsavedStatus');
                
                if (shouldConfirmClose && hasUnsavedChanges) {
                    statusDiv.className = 'status enabled';
                    statusText.textContent = '✅ 关闭确认已启用 - 尝试关闭标签页将显示确认对话框';
                } else {
                    statusDiv.className = 'status disabled';
                    statusText.textContent = '❌ 关闭确认已禁用 - 可以直接关闭标签页';
                }
                
                confirmStatus.textContent = shouldConfirmClose ? '启用' : '禁用';
                confirmStatus.className = shouldConfirmClose ? 'badge bg-success ms-2' : 'badge bg-danger ms-2';
                
                unsavedStatus.textContent = hasUnsavedChanges ? '有' : '无';
                unsavedStatus.className = hasUnsavedChanges ? 'badge bg-warning ms-2' : 'badge bg-secondary ms-2';
            }

            // 启用关闭确认
            function enableCloseConfirm() {
                shouldConfirmClose = true;
                updateStatus();
            }

            // 禁用关闭确认
            function disableCloseConfirm() {
                shouldConfirmClose = false;
                updateStatus();
            }

            // 模拟未保存更改
            function simulateUnsavedChanges() {
                hasUnsavedChanges = true;
                updateStatus();
            }

            // 清除未保存更改
            function clearUnsavedChanges() {
                hasUnsavedChanges = false;
                updateStatus();
            }

            // 初始化
            document.addEventListener('DOMContentLoaded', function() {
                // 1秒后自动启用未保存更改状态
                setTimeout(() => {
                    hasUnsavedChanges = true;
                    updateStatus();
                }, 1000);
                
                // 监听页面关闭事件
                window.addEventListener('beforeunload', function(e) {
                    if (shouldConfirmClose && !allowClose && hasUnsavedChanges) {
                        e.preventDefault();
                        return (e.returnValue = '确定要关闭页面吗？未保存的操作可能会丢失。');
                    }
                });
                
                // 监听键盘事件
                document.addEventListener('keydown', function(e) {
                    if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
                        if (shouldConfirmClose && !allowClose && hasUnsavedChanges) {
                            e.preventDefault();
                            alert('检测到关闭快捷键！在实际应用中这里会显示自定义确认对话框。');
                        }
                    }
                });
                
                // 监听点击事件以设置未保存状态
                document.addEventListener('click', function(e) {
                    if (e.target.tagName === 'BUTTON' && !e.target.textContent.includes('清除')) {
                        hasUnsavedChanges = true;
                        updateStatus();
                    }
                });
                
                // 初始状态更新
                updateStatus();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/backups", response_model=List[BackupInfo])
async def get_backups(manager: BackupManager = Depends(get_backup_manager)):
    """获取备份列表"""
    return manager.get_backup_list()


@app.post("/api/backups", response_model=BackupResponse)
async def create_backup(
    request: BackupRequest,
    background_tasks: BackgroundTasks,
    manager: BackupManager = Depends(get_backup_manager)
):
    """创建备份"""
    try:
        # 在后台任务中执行备份
        backup_info = await manager.create_backup(request.description, request.compress)
        
        return BackupResponse(
            success=True,
            message="备份创建成功",
            backup_id=backup_info.id,
            data=backup_info
        )
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"备份创建失败: {str(e)}",
            backup_id=None
        )


@app.get("/api/backups/{backup_id}", response_model=BackupInfo)
async def get_backup(
    backup_id: str,
    manager: BackupManager = Depends(get_backup_manager)
):
    """获取指定备份信息"""
    backup_info = manager.load_backup_info(backup_id)
    if not backup_info:
        raise HTTPException(status_code=404, detail="备份不存在")
    return backup_info


@app.delete("/api/backups/{backup_id}")
async def delete_backup(
    backup_id: str,
    manager: BackupManager = Depends(get_backup_manager)
):
    """删除指定备份"""
    backup_info = manager.load_backup_info(backup_id)
    if not backup_info:
        raise HTTPException(status_code=404, detail="备份不存在")
    
    manager.delete_backup(backup_id)
    return {"success": True, "message": f"备份 {backup_id} 已删除"}


@app.post("/api/backups/batch-delete")
async def batch_delete_backups(
    request: BatchDeleteRequest,
    manager: BackupManager = Depends(get_backup_manager)
):
    """批量删除备份"""
    if not request.backup_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的备份")
    
    result = manager.delete_backups_batch(request.backup_ids)
    
    if result["failed_count"] > 0:
        return {
            "success": False,
            "message": f"删除完成：成功 {result['successful_count']} 个，失败 {result['failed_count']} 个",
            "data": result
        }
    else:
        return {
            "success": True,
            "message": f"成功删除 {result['successful_count']} 个备份",
            "data": result
        }


@app.post("/api/restore", response_model=RestoreResponse)
async def restore_backup(
    request: RestoreRequest,
    manager: RestoreManager = Depends(get_restore_manager)
):
    """恢复备份"""
    try:
        result = await manager.restore_backup(
            request.backup_id, 
            request.restore_type, 
            request.force
        )
        return result
    except Exception as e:
        return RestoreResponse(
            success=False,
            message=f"恢复失败: {str(e)}",
            backup_id=request.backup_id,
            restored_at=datetime.now()
        )


@app.get("/api/restore/latest")
async def get_latest_backup(
    manager: RestoreManager = Depends(get_restore_manager)
):
    """获取最新备份"""
    latest_backup = manager.get_latest_backup()
    if not latest_backup:
        raise HTTPException(status_code=404, detail="没有可用的备份")
    return latest_backup


@app.get("/api/database/info")
async def get_database_info(
    manager: RestoreManager = Depends(get_restore_manager)
):
    """获取数据库信息"""
    return await manager.get_database_info()


@app.get("/api/database/test")
async def test_database_connection(
    manager: RestoreManager = Depends(get_restore_manager)
):
    """测试数据库连接"""
    is_connected = await manager.test_connection()
    return {
        "connected": is_connected,
        "message": "数据库连接正常" if is_connected else "数据库连接失败"
    }


@app.get("/api/schedule/status", response_model=ScheduleStatus)
async def get_schedule_status(
    scheduler: BackupScheduler = Depends(get_scheduler)
):
    """获取调度状态"""
    return scheduler.get_status()


@app.post("/api/schedule/start")
async def start_schedule(
    scheduler: BackupScheduler = Depends(get_scheduler)
):
    """启动调度任务"""
    await scheduler.start()
    return {"success": True, "message": "调度任务已启动"}


@app.post("/api/schedule/stop")
async def stop_schedule(
    scheduler: BackupScheduler = Depends(get_scheduler)
):
    """停止调度任务"""
    await scheduler.stop()
    return {"success": True, "message": "调度任务已停止"}


@app.post("/api/schedule/trigger")
async def trigger_backup(
    scheduler: BackupScheduler = Depends(get_scheduler)
):
    """手动触发备份"""
    await scheduler.trigger_backup()
    return {"success": True, "message": "备份任务已触发"}


@app.post("/api/schedule/update")
async def update_schedule(
    interval_hours: int,
    scheduler: BackupScheduler = Depends(get_scheduler)
):
    """更新调度间隔"""
    await scheduler.update_schedule(interval_hours)
    return {"success": True, "message": f"调度间隔已更新为 {interval_hours} 小时"}


# 配置管理API
@app.get("/api/config")
async def get_config(config_mgr: ConfigManager = Depends(get_config_manager)):
    """获取当前配置"""
    config = config_mgr.get_config()
    if config:
        return config
    else:
        raise HTTPException(status_code=404, detail="配置未找到")


@app.post("/api/config/test", response_model=ConfigTestResponse)
async def test_database_config(
    request: ConfigTestRequest,
    config_mgr: ConfigManager = Depends(get_config_manager)
):
    """测试数据库连接"""
    try:
        from .models import DatabaseConfig
        db_config = DatabaseConfig(
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password
        )
        
        # 测试连接
        success = config_mgr.test_database_connection(db_config)
        
        if success:
            return ConfigTestResponse(
                success=True,
                message="数据库连接测试成功",
                details={"host": request.host, "port": request.port, "database": request.database}
            )
        else:
            return ConfigTestResponse(
                success=False,
                message="数据库连接测试失败，请检查连接参数"
            )
    except Exception as e:
        return ConfigTestResponse(
            success=False,
            message=f"连接测试出错: {str(e)}"
        )


@app.post("/api/config/database", response_model=ConfigUpdateResponse)
async def update_database_config(
    request: DatabaseConfigUpdate,
    config_mgr: ConfigManager = Depends(get_config_manager)
):
    """更新数据库配置"""
    try:
        from .models import DatabaseConfig
        db_config = DatabaseConfig(
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password
        )
        
        # 先测试连接
        if not config_mgr.test_database_connection(db_config):
            return ConfigUpdateResponse(
                success=False,
                message="数据库连接失败，请检查配置参数"
            )
        
        # 更新配置
        success = config_mgr.update_database_config(db_config)
        
        if success:
            # 重新初始化管理器
            await reinitialize_managers()
            
            return ConfigUpdateResponse(
                success=True,
                message="数据库配置更新成功",
                config=config_mgr.get_config()
            )
        else:
            return ConfigUpdateResponse(
                success=False,
                message="配置保存失败"
            )
    except Exception as e:
        return ConfigUpdateResponse(
            success=False,
            message=f"配置更新失败: {str(e)}"
        )


@app.post("/api/config/backup", response_model=ConfigUpdateResponse)
async def update_backup_config(
    request: BackupConfigUpdate,
    config_mgr: ConfigManager = Depends(get_config_manager)
):
    """更新备份配置"""
    try:
        from .models import BackupConfig
        backup_config = BackupConfig(
            storage_path=request.storage_path,
            interval_hours=request.interval_hours,
            max_backups=request.max_backups,
            compression=request.compression,
            cleanup_enabled=request.cleanup_enabled,
            cleanup_interval_days=request.cleanup_interval_days,
            cleanup_keep_days=request.cleanup_keep_days
        )
        
        success = config_mgr.update_backup_config(backup_config)
        
        if success:
            # 重新初始化管理器
            await reinitialize_managers()
            
            return ConfigUpdateResponse(
                success=True,
                message="备份配置更新成功",
                config=config_mgr.get_config()
            )
        else:
            return ConfigUpdateResponse(
                success=False,
                message="配置保存失败"
            )
    except Exception as e:
        return ConfigUpdateResponse(
            success=False,
            message=f"配置更新失败: {str(e)}"
        )


async def reinitialize_managers():
    """重新初始化管理器"""
    global backup_manager, restore_manager, scheduler
    
    if config_manager:
        config = config_manager.get_config()
        if config:
            # 停止旧的调度器
            if scheduler:
                await scheduler.stop()
            
            # 重新创建管理器
            backup_manager = BackupManager(config.database, config.backup)
            restore_manager = RestoreManager(config.database, config.backup)
            scheduler = BackupScheduler(config.database, config.backup)
            
            # 重新启动调度器
            await scheduler.start()


@app.post("/api/cleanup", response_model=CleanupResponse)
async def manual_cleanup(
    manager: BackupManager = Depends(get_backup_manager)
):
    """手动清理旧备份"""
    try:
        deleted_count, deleted_files = manager.cleanup_old_backups_by_date()
        return CleanupResponse(
            success=True,
            message=f"清理完成，删除了 {deleted_count} 个备份文件",
            deleted_count=deleted_count,
            deleted_files=deleted_files
        )
    except Exception as e:
        return CleanupResponse(
            success=False,
            message=f"清理失败: {str(e)}",
            deleted_count=0,
            deleted_files=[]
        )


@app.get("/api/health")
async def health_check():
    """健康检查"""
    config_mgr = get_config_manager()
    db_available = config_mgr.is_database_available()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "database_available": db_available,
        "services_ready": backup_manager is not None and restore_manager is not None
    }


if __name__ == "__main__":
    import uvicorn
    
    config_mgr = ConfigManager()
    config = config_mgr.get_config()
    
    if config:
        uvicorn.run(
            "app.main:app",
            host=config.app.host,
            port=config.app.port,
            reload=config.app.debug
        )
    else:
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000) 