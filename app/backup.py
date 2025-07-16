import os
import subprocess
import gzip
import shutil
from datetime import datetime
from typing import Optional, List
import psycopg2
from alembic import command
from alembic.config import Config as AlembicConfig
from .models import BackupInfo, BackupStatus, DatabaseConfig, BackupConfig
import json
import asyncio


class BackupManager:
    def __init__(self, db_config: DatabaseConfig, backup_config: BackupConfig):
        self.db_config = db_config
        self.backup_config = backup_config
        self.ensure_backup_directory()
    
    def ensure_backup_directory(self):
        """确保备份目录存在"""
        os.makedirs(self.backup_config.storage_path, exist_ok=True)
    
    def get_alembic_version(self) -> Optional[str]:
        """获取当前Alembic版本"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            print(f"获取Alembic版本失败: {e}")
            return None
    
    def generate_backup_filename(self, timestamp: datetime) -> str:
        """生成备份文件名"""
        base_name = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        extension = ".sql.gz" if self.backup_config.compression else ".sql"
        return base_name + extension
    
    def generate_backup_filename_with_compression(self, timestamp: datetime, compress: bool) -> str:
        """生成备份文件名（支持自定义压缩选项）"""
        base_name = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        extension = ".sql.gz" if compress else ".sql"
        return base_name + extension
    
    async def create_backup(self, description: Optional[str] = None, compress: Optional[bool] = None) -> BackupInfo:
        """创建数据库备份"""
        timestamp = datetime.now()
        backup_id = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # 确定是否压缩：优先使用用户选择，否则使用配置默认值
        should_compress = compress if compress is not None else self.backup_config.compression
        
        filename = self.generate_backup_filename_with_compression(timestamp, should_compress)
        filepath = os.path.join(self.backup_config.storage_path, filename)
        
        # 创建备份信息对象
        backup_info = BackupInfo(
            id=backup_id,
            filename=filename,
            created_at=timestamp,
            size=0,
            status=BackupStatus.RUNNING,
            alembic_version=self.get_alembic_version(),
            compressed=should_compress,
            description=description
        )
        
        try:
            # 保存备份状态
            self.save_backup_info(backup_info)
            
            # 执行备份
            await self.execute_backup(filepath, should_compress)
            
            # 更新备份信息
            backup_info.size = os.path.getsize(filepath)
            backup_info.status = BackupStatus.COMPLETED
            self.save_backup_info(backup_info)
            
            # 清理旧备份
            self.cleanup_old_backups()
            
            return backup_info
            
        except Exception as e:
            backup_info.status = BackupStatus.FAILED
            backup_info.error_message = str(e)
            self.save_backup_info(backup_info)
            raise e
    
    def get_database_version(self) -> str:
        """获取数据库版本"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                version_str = result[0]
                # 提取版本号，如 "PostgreSQL 17.5" -> "17"
                import re
                match = re.search(r'PostgreSQL (\d+)\.', version_str)
                return match.group(1) if match else "15"
            else:
                return "15"
        except Exception as e:
            print(f"获取数据库版本失败: {e}")
            return "15"  # 默认返回15
    
    def get_pg_dump_version(self) -> str:
        """获取pg_dump版本"""
        try:
            result = subprocess.run(['pg_dump', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_str = result.stdout.strip()
                # 提取版本号，如 "pg_dump (PostgreSQL) 15.13" -> "15"
                import re
                match = re.search(r'pg_dump \(PostgreSQL\) (\d+)\.', version_str)
                return match.group(1) if match else "15"
            else:
                return "15"
        except Exception as e:
            print(f"获取pg_dump版本失败: {e}")
            return "15"  # 默认返回15
    
    async def execute_backup(self, filepath: str, compress: Optional[bool] = None):
        """执行备份命令"""
        # 获取数据库版本
        db_version = self.get_database_version()
        print(f"检测到数据库版本: {db_version}")
        
        # 获取pg_dump版本
        pg_dump_version = self.get_pg_dump_version()
        print(f"pg_dump版本: {pg_dump_version}")
        
        # 构建pg_dump命令（不加任何兼容参数）
        cmd = [
            'pg_dump',
            f'--host={self.db_config.host}',
            f'--port={self.db_config.port}',
            f'--username={self.db_config.username}',
            f'--dbname={self.db_config.database}',
            '--clean',
            '--if-exists',
            '--create'
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config.password
        
        # 执行pg_dump命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            raise Exception(f"备份失败: {error_msg}")
        
        # 保存备份数据
        backup_data = stdout.decode('utf-8')
        
        # 确定是否压缩：优先使用传入参数，否则使用配置默认值
        should_compress = compress if compress is not None else self.backup_config.compression
        
        if should_compress:
            # 保存为压缩文件
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                f.write(backup_data)
        else:
            # 保存为普通文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(backup_data)
    
    async def execute_backup_fallback(self, filepath: str, compress: Optional[bool] = None):
        """执行备份命令（fallback模式，使用基础参数）"""
        print("使用fallback模式执行备份...")
        
        # 构建基础pg_dump命令，不使用兼容性参数
        cmd = [
            'pg_dump',
            f'--host={self.db_config.host}',
            f'--port={self.db_config.port}',
            f'--username={self.db_config.username}',
            f'--dbname={self.db_config.database}',
            '--clean',
            '--if-exists',
            '--create',
            '--no-sync'  # 添加no-sync参数避免同步问题
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config.password
        
        # 执行pg_dump命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            raise Exception(f"备份失败（fallback模式）: {error_msg}")
        
        # 保存备份数据
        backup_data = stdout.decode('utf-8')
        
        # 确定是否压缩：优先使用传入参数，否则使用配置默认值
        should_compress = compress if compress is not None else self.backup_config.compression
        
        if should_compress:
            # 保存为压缩文件
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                f.write(backup_data)
        else:
            # 保存为普通文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(backup_data)
    
    def save_backup_info(self, backup_info: BackupInfo):
        """保存备份信息到JSON文件"""
        info_file = os.path.join(
            self.backup_config.storage_path, 
            f"{backup_info.id}.json"
        )
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(backup_info.model_dump(), f, indent=2, default=str)
    
    def load_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """从JSON文件加载备份信息"""
        info_file = os.path.join(
            self.backup_config.storage_path, 
            f"{backup_id}.json"
        )
        if os.path.exists(info_file):
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return BackupInfo(**data)
        return None
    
    def get_backup_list(self) -> List[BackupInfo]:
        """获取所有备份列表"""
        backups = []
        for filename in os.listdir(self.backup_config.storage_path):
            if filename.endswith('.json'):
                backup_id = filename[:-5]  # 移除.json后缀
                backup_info = self.load_backup_info(backup_id)
                if backup_info:
                    backups.append(backup_info)
        
        # 按创建时间排序
        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups
    
    def cleanup_old_backups(self):
        """清理旧备份文件（基于数量）"""
        backups = self.get_backup_list()
        if len(backups) > self.backup_config.max_backups:
            # 删除最旧的备份
            for backup in backups[self.backup_config.max_backups:]:
                self.delete_backup(backup.id)

    def cleanup_old_backups_by_date(self) -> tuple[int, List[str]]:
        """根据时间清理旧备份文件"""
        if not self.backup_config.cleanup_enabled:
            return 0, []
        
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=self.backup_config.cleanup_keep_days)
        backups = self.get_backup_list()
        
        deleted_count = 0
        deleted_files = []
        
        for backup in backups:
            if backup.created_at < cutoff_date:
                try:
                    deleted_files.append(backup.filename)
                    self.delete_backup(backup.id)
                    deleted_count += 1
                except Exception as e:
                    print(f"删除备份失败 {backup.id}: {e}")
        
        return deleted_count, deleted_files
    
    def delete_backup(self, backup_id: str):
        """删除指定的备份"""
        backup_info = self.load_backup_info(backup_id)
        if backup_info:
            # 删除备份文件
            backup_file = os.path.join(
                self.backup_config.storage_path, 
                backup_info.filename
            )
            if os.path.exists(backup_file):
                os.remove(backup_file)
            
            # 删除信息文件
            info_file = os.path.join(
                self.backup_config.storage_path, 
                f"{backup_id}.json"
            )
            if os.path.exists(info_file):
                os.remove(info_file) 
    
    def delete_backups_batch(self, backup_ids: List[str]) -> dict:
        """批量删除备份"""
        successful_deletions = []
        failed_deletions = []
        
        for backup_id in backup_ids:
            try:
                backup_info = self.load_backup_info(backup_id)
                if backup_info:
                    self.delete_backup(backup_id)
                    successful_deletions.append(backup_id)
                else:
                    failed_deletions.append({"backup_id": backup_id, "error": "备份不存在"})
            except Exception as e:
                failed_deletions.append({"backup_id": backup_id, "error": str(e)})
        
        return {
            "successful_count": len(successful_deletions),
            "failed_count": len(failed_deletions),
            "successful_deletions": successful_deletions,
            "failed_deletions": failed_deletions
        }