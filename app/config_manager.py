import json
import os
from typing import Optional
from .models import Config, DatabaseConfig, BackupConfig, AppConfig


class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config: Optional[Config] = None
        self.load_config()
    
    def load_config(self) -> Config:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self.config = Config(**config_data)
            else:
                # 创建默认配置
                self.config = self.create_default_config()
                self.save_config()
            return self.config
        except Exception as e:
            print(f"配置加载失败，使用默认配置: {e}")
            self.config = self.create_default_config()
            return self.config
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            if self.config:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config.model_dump(), f, indent=2, default=str)
                return True
            return False
        except Exception as e:
            print(f"配置保存失败: {e}")
            return False
    
    def create_default_config(self) -> Config:
        """创建默认配置"""
        return Config(
            database=DatabaseConfig(
                host="localhost",
                port=5432,
                database="your_database",
                username="your_username",
                password="your_password"
            ),
            backup=BackupConfig(
                storage_path="./backups",
                interval_hours=12,
                max_backups=30,
                compression=True,
                cleanup_enabled=True,
                cleanup_interval_days=7,
                cleanup_keep_days=30
            ),
            app=AppConfig(
                title="PostgreSQL Backup & Restore Tool",
                host="0.0.0.0",
                port=8000,
                debug=False
            )
        )
    
    def update_database_config(self, db_config: DatabaseConfig) -> bool:
        """更新数据库配置"""
        try:
            if self.config:
                self.config.database = db_config
                return self.save_config()
            return False
        except Exception as e:
            print(f"数据库配置更新失败: {e}")
            return False
    
    def update_backup_config(self, backup_config: BackupConfig) -> bool:
        """更新备份配置"""
        try:
            if self.config:
                self.config.backup = backup_config
                return self.save_config()
            return False
        except Exception as e:
            print(f"备份配置更新失败: {e}")
            return False
    
    def update_app_config(self, app_config: AppConfig) -> bool:
        """更新应用配置"""
        try:
            if self.config:
                self.config.app = app_config
                return self.save_config()
            return False
        except Exception as e:
            print(f"应用配置更新失败: {e}")
            return False
    
    def get_config(self) -> Optional[Config]:
        """获取当前配置"""
        return self.config
    
    def test_database_connection(self, db_config: DatabaseConfig) -> bool:
        """测试数据库连接"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=db_config.host,
                port=db_config.port,
                database=db_config.database,
                user=db_config.username,
                password=db_config.password,
                connect_timeout=5
            )
            conn.close()
            return True
        except Exception as e:
            print(f"数据库连接测试失败: {e}")
            return False
    
    def is_database_available(self) -> bool:
        """检查当前配置的数据库是否可用"""
        if not self.config:
            return False
        return self.test_database_connection(self.config.database)
    
    def validate_config(self, config: Config) -> tuple[bool, str]:
        """验证配置是否有效"""
        try:
            # 验证数据库配置
            if not config.database.host or not config.database.database:
                return False, "数据库主机和数据库名不能为空"
            
            if not config.database.username:
                return False, "数据库用户名不能为空"
            
            # 验证备份配置
            if config.backup.interval_hours <= 0:
                return False, "备份间隔必须大于0"
            
            if config.backup.max_backups <= 0:
                return False, "最大备份数量必须大于0"
            
            # 验证应用配置
            if config.app.port <= 0 or config.app.port > 65535:
                return False, "端口号必须在1-65535之间"
            
            return True, "配置验证成功"
        except Exception as e:
            return False, f"配置验证失败: {e}" 