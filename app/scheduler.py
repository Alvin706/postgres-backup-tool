import asyncio
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .models import DatabaseConfig, BackupConfig, ScheduleStatus
from .backup import BackupManager


class BackupScheduler:
    def __init__(self, db_config: DatabaseConfig, backup_config: BackupConfig):
        self.db_config = db_config
        self.backup_config = backup_config
        self.backup_manager = BackupManager(db_config, backup_config)
        self.scheduler = AsyncIOScheduler()
        self.job_id = "auto_backup"
        self.cleanup_job_id = "auto_cleanup"
        self.last_run: Optional[datetime] = None
        self.last_cleanup_run: Optional[datetime] = None
        self.is_running = False
    
    async def start(self):
        """启动定时任务调度器"""
        if self.is_running:
            return
        
        # 添加定时备份任务
        self.scheduler.add_job(
            func=self.perform_backup,
            trigger=IntervalTrigger(hours=self.backup_config.interval_hours),
            id=self.job_id,
            name="自动备份任务",
            replace_existing=True
        )
        
        # 添加定时清理任务
        if self.backup_config.cleanup_enabled:
            self.scheduler.add_job(
                func=self.perform_cleanup,
                trigger=IntervalTrigger(days=self.backup_config.cleanup_interval_days),
                id=self.cleanup_job_id,
                name="自动清理任务",
                replace_existing=True
            )
        
        self.scheduler.start()
        self.is_running = True
        print(f"定时备份任务已启动，每 {self.backup_config.interval_hours} 小时执行一次")
        if self.backup_config.cleanup_enabled:
            print(f"定时清理任务已启动，每 {self.backup_config.cleanup_interval_days} 天执行一次")
    
    async def stop(self):
        """停止定时任务调度器"""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        print("定时备份任务已停止")
    
    async def perform_backup(self):
        """执行备份任务"""
        try:
            print(f"开始执行定时备份任务: {datetime.now()}")
            backup_info = await self.backup_manager.create_backup(
                description="自动备份"
            )
            self.last_run = datetime.now()
            print(f"自动备份完成: {backup_info.filename}")
            
        except Exception as e:
            print(f"自动备份失败: {e}")

    async def perform_cleanup(self):
        """执行清理任务"""
        try:
            print(f"开始执行定时清理任务: {datetime.now()}")
            deleted_count, deleted_files = self.backup_manager.cleanup_old_backups_by_date()
            self.last_cleanup_run = datetime.now()
            print(f"自动清理完成: 删除了 {deleted_count} 个备份文件")
            if deleted_files:
                print(f"删除的文件: {', '.join(deleted_files)}")
            
        except Exception as e:
            print(f"自动清理失败: {e}")
    
    async def trigger_backup(self):
        """手动触发备份任务"""
        await self.perform_backup()
    
    def get_status(self) -> ScheduleStatus:
        """获取调度器状态"""
        next_run = None
        if self.is_running:
            job = self.scheduler.get_job(self.job_id)
            if job:
                next_run = job.next_run_time
        
        return ScheduleStatus(
            enabled=self.is_running,
            next_run=next_run,
            last_run=self.last_run,
            interval_hours=self.backup_config.interval_hours
        )
    
    async def update_schedule(self, interval_hours: int):
        """更新调度间隔"""
        self.backup_config.interval_hours = interval_hours
        
        if self.is_running:
            # 删除旧任务
            self.scheduler.remove_job(self.job_id)
            
            # 添加新任务
            self.scheduler.add_job(
                func=self.perform_backup,
                trigger=IntervalTrigger(hours=interval_hours),
                id=self.job_id,
                name="自动备份任务",
                replace_existing=True
            )
            
            print(f"调度间隔已更新为 {interval_hours} 小时")
    
    async def pause_schedule(self):
        """暂停调度任务"""
        if self.is_running:
            self.scheduler.pause_job(self.job_id)
            print("定时备份任务已暂停")
    
    async def resume_schedule(self):
        """恢复调度任务"""
        if self.is_running:
            self.scheduler.resume_job(self.job_id)
            print("定时备份任务已恢复") 