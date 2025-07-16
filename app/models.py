from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackupInfo(BaseModel):
    id: str
    filename: str
    created_at: datetime
    size: int
    status: BackupStatus
    alembic_version: Optional[str] = None
    compressed: bool = True
    error_message: Optional[str] = None
    description: Optional[str] = None


class BackupRequest(BaseModel):
    description: Optional[str] = None
    compress: bool = True


class RestoreRequest(BaseModel):
    backup_id: str
    restore_type: str = "normal"  # "normal", "full" 或 "incremental"
    force: bool = False


class BatchDeleteRequest(BaseModel):
    backup_ids: List[str]


class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    database: str
    username: str
    password: str


class BackupConfig(BaseModel):
    storage_path: str = "./backups"
    interval_hours: int = 12
    max_backups: int = 30
    compression: bool = True
    cleanup_enabled: bool = True
    cleanup_interval_days: int = 7
    cleanup_keep_days: int = 30


class AppConfig(BaseModel):
    title: str = "PostgreSQL Backup & Restore Tool"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class Config(BaseModel):
    database: DatabaseConfig
    backup: BackupConfig
    app: AppConfig


class BackupResponse(BaseModel):
    success: bool
    message: str
    backup_id: Optional[str] = None
    data: Optional[BackupInfo] = None


class RestoreResponse(BaseModel):
    success: bool
    message: str
    backup_id: str
    restored_at: datetime


class ScheduleStatus(BaseModel):
    enabled: bool
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    interval_hours: int


# 新增：配置管理相关模型
class DatabaseConfigUpdate(BaseModel):
    host: str = Field(..., min_length=1, description="数据库主机地址")
    port: int = Field(..., ge=1, le=65535, description="数据库端口")
    database: str = Field(..., min_length=1, description="数据库名称")
    username: str = Field(..., min_length=1, description="数据库用户名")
    password: str = Field(..., description="数据库密码")


class BackupConfigUpdate(BaseModel):
    storage_path: str = Field(..., min_length=1, description="备份存储路径")
    interval_hours: int = Field(..., ge=1, le=8760, description="备份间隔(小时)")
    max_backups: int = Field(..., ge=1, le=1000, description="最大备份数量")
    compression: bool = Field(..., description="是否压缩备份文件")
    cleanup_enabled: bool = Field(..., description="是否启用自动清理")
    cleanup_interval_days: int = Field(..., ge=1, le=365, description="清理间隔(天)")
    cleanup_keep_days: int = Field(..., ge=1, le=3650, description="保留天数")


class AppConfigUpdate(BaseModel):
    title: str = Field(..., min_length=1, description="应用标题")
    debug: bool = Field(..., description="调试模式")


class ConfigTestRequest(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str


class ConfigTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None


class ConfigUpdateResponse(BaseModel):
    success: bool
    message: str
    config: Optional[Config] = None


class CleanupResponse(BaseModel):
    success: bool
    message: str
    deleted_count: int
    deleted_files: List[str] 