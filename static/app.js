class BackupTool {
    constructor() {
        this.currentBackupId = null;
        this.init();
    }

    async init() {
        await this.loadInitialData();
        this.startAutoRefresh();
    }

    async loadInitialData() {
        await Promise.all([
            this.loadBackups(),
            this.loadDatabaseInfo(),
            this.loadScheduleStatus(),
            this.loadConfig()
        ]);
    }

    startAutoRefresh() {
        // 每30秒自动刷新数据
        setInterval(() => {
            this.loadScheduleStatus();
        }, 30000);
    }

    async apiRequest(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            this.showNotification('API请求失败: ' + error.message, 'error');
            throw error;
        }
    }

    async loadBackups() {
        try {
            const backups = await this.apiRequest('/api/backups');
            this.renderBackupList(backups);
        } catch (error) {
            document.getElementById('backupList').innerHTML = 
                '<div class="alert alert-danger">加载备份列表失败</div>';
        }
    }

    renderBackupList(backups) {
        const container = document.getElementById('backupList');
        
        if (backups.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-inbox fa-2x text-muted"></i>
                    <p class="mt-2 text-muted">暂无备份文件</p>
                </div>
            `;
            // 隐藏批量操作控制栏
            document.getElementById('batchControls').style.display = 'none';
            return;
        }

        const html = backups.map(backup => `
            <div class="backup-item card mb-3">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-1">
                            <input type="checkbox" class="form-check-input backup-checkbox" 
                                   value="${backup.id}" onchange="updateSelection()">
                        </div>
                        <div class="col-md-3">
                            <h6 class="mb-1">${backup.id}</h6>
                            <small class="text-muted">${backup.filename}</small>
                        </div>
                        <div class="col-md-2">
                            <span class="badge ${this.getStatusBadgeClass(backup.status)} status-badge">
                                ${this.getStatusText(backup.status)}
                            </span>
                        </div>
                        <div class="col-md-2">
                            <small class="text-muted">${this.formatFileSize(backup.size)}</small>
                        </div>
                        <div class="col-md-2">
                            <small class="text-muted">${this.formatDateTime(backup.created_at)}</small>
                        </div>
                        <div class="col-md-2">
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-success" onclick="app.showRestoreModal('${backup.id}')" 
                                        ${backup.status !== 'completed' ? 'disabled' : ''}>
                                    <i class="fas fa-undo"></i>
                                </button>
                                <button class="btn btn-danger" onclick="app.deleteBackup('${backup.id}')">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                    ${backup.description ? `
                        <div class="row mt-2">
                            <div class="col-12">
                                <small class="text-primary">
                                    * ${backup.description}
                                </small>
                            </div>
                        </div>
                    ` : ''}
                    ${backup.alembic_version ? `
                        <div class="row mt-2">
                            <div class="col-12">
                                <small class="text-info">
                                    <i class="fas fa-code-branch"></i> Alembic版本: ${backup.alembic_version}
                                </small>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
        
        // 显示批量操作控制栏
        document.getElementById('batchControls').style.display = 'flex';
        
        // 重置选择状态
        this.resetSelection();
    }

    async loadDatabaseInfo() {
        try {
            const info = await this.apiRequest('/api/database/info');
            this.renderDatabaseInfo(info);
        } catch (error) {
            console.error('Failed to load database info:', error);
        }
    }

    renderDatabaseInfo(info) {
        if (info.error) {
            document.getElementById('databaseInfo').innerHTML = 
                '<div class="alert alert-danger">获取数据库信息失败</div>';
            return;
        }

        document.getElementById('dbSize').textContent = info.database_size || '-';
        document.getElementById('tableCount').textContent = info.table_count || '-';
        
        // 存储表结构信息以备后用
        this.tablesData = info.tables || {};
    }

    renderTablesInfo(tables) {
        const tablesContainer = document.getElementById('tablesInfo');
        
        if (Object.keys(tables).length === 0) {
            tablesContainer.innerHTML = '<p class="text-muted">无表结构信息</p>';
            return;
        }

        let html = '';
        for (const [tableName, columns] of Object.entries(tables)) {
            html += `
                <div class="table-item mb-3">
                    <h6 class="table-name mb-2">
                        <i class="fas fa-table me-1"></i>
                        ${tableName}
                    </h6>
                    <div class="table-columns">
                        <table class="table table-sm table-striped">
                            <thead>
                                <tr>
                                    <th>列名</th>
                                    <th>数据类型</th>
                                    <th>允许空值</th>
                                    <th>默认值</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            columns.forEach(column => {
                html += `
                    <tr>
                        <td>${column.column_name}</td>
                        <td>${column.data_type}</td>
                        <td>${column.is_nullable === 'YES' ? '是' : '否'}</td>
                        <td>${column.column_default || '-'}</td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }
        
        tablesContainer.innerHTML = html;
    }

    async loadScheduleStatus() {
        try {
            const status = await this.apiRequest('/api/schedule/status');
            this.renderScheduleStatus(status);
        } catch (error) {
            console.error('Failed to load schedule status:', error);
        }
    }

    renderScheduleStatus(status) {
        document.getElementById('scheduleStatus').innerHTML = 
            `<span class="badge ${status.enabled ? 'bg-success' : 'bg-secondary'}">
                ${status.enabled ? '运行中' : '已停止'}
            </span>`;
        
        document.getElementById('scheduleInterval').textContent = status.interval_hours;
        document.getElementById('nextRun').textContent = 
            status.next_run ? this.formatDateTime(status.next_run) : '-';
        document.getElementById('lastRun').textContent = 
            status.last_run ? this.formatDateTime(status.last_run) : '-';
    }

    showBackupModal() {
        const modal = new bootstrap.Modal(document.getElementById('backupModal'));
        modal.show();
    }

    async confirmBackup() {
        const description = document.getElementById('backupDescription').value;
        const compress = document.getElementById('compressBackup').checked;
        
        try {
            this.showProgress(true);
            const result = await this.apiRequest('/api/backups', {
                method: 'POST',
                body: JSON.stringify({
                    description: description || null,
                    compress: compress
                })
            });

            if (result.success) {
                this.showNotification('备份创建成功', 'success');
                // 并行刷新备份列表和数据库信息
                await Promise.all([
                    this.loadBackups(),
                    this.loadDatabaseInfo()
                ]);
                bootstrap.Modal.getInstance(document.getElementById('backupModal')).hide();
            } else {
                this.showNotification('备份创建失败: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('备份创建失败', 'error');
        } finally {
            this.showProgress(false);
        }
    }

    showRestoreModal(backupId) {
        this.currentBackupId = backupId;
        document.getElementById('restoreBackupId').textContent = backupId;
        const modal = new bootstrap.Modal(document.getElementById('restoreModal'));
        modal.show();
    }

    async confirmRestore() {
        if (!this.currentBackupId) return;

        const restoreType = document.querySelector('input[name="restoreType"]:checked').value;
        const force = document.getElementById('forceRestore').checked;
        
        try {
            this.showProgress(true);
            const result = await this.apiRequest('/api/restore', {
                method: 'POST',
                body: JSON.stringify({
                    backup_id: this.currentBackupId,
                    restore_type: restoreType,
                    force: force
                })
            });

            if (result.success) {
                let typeText = '恢复';
                if (restoreType === 'full') {
                    typeText = '完全恢复';
                } else if (restoreType === 'incremental') {
                    typeText = '增量恢复';
                }
                this.showNotification(`${typeText}成功`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('restoreModal')).hide();
                
                // 恢复成功后自动刷新数据库信息和备份列表
                await Promise.all([
                    this.loadDatabaseInfo(),
                    this.loadBackups()
                ]);
            } else {
                this.showNotification('恢复失败: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('恢复失败', 'error');
        } finally {
            this.showProgress(false);
        }
    }

    async deleteBackup(backupId) {
        if (!confirm('确定要删除此备份吗？')) return;

        try {
            await this.apiRequest(`/api/backups/${backupId}`, {
                method: 'DELETE'
            });
            
            this.showNotification('备份删除成功', 'success');
            await this.loadBackups();
        } catch (error) {
            this.showNotification('备份删除失败', 'error');
        }
    }

    async batchDeleteBackups(backupIds) {
        try {
            const response = await this.apiRequest('/api/backups/batch-delete', {
                method: 'POST',
                body: JSON.stringify({ backup_ids: backupIds })
            });
            
            if (response.success) {
                this.showNotification(response.message, 'success');
            } else {
                this.showNotification(response.message, 'warning');
            }
            
            await this.loadBackups();
        } catch (error) {
            this.showNotification('批量删除失败', 'error');
        }
    }

    resetSelection() {
        const selectAllCheckbox = document.getElementById('selectAll');
        const batchDeleteBtn = document.getElementById('batchDeleteBtn');
        
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
        batchDeleteBtn.style.display = 'none';
        
        document.getElementById('selectedCount').textContent = '已选择 0 项';
    }

    async startSchedule() {
        try {
            await this.apiRequest('/api/schedule/start', { method: 'POST' });
            this.showNotification('定时任务已启动', 'success');
            await this.loadScheduleStatus();
        } catch (error) {
            this.showNotification('启动定时任务失败', 'error');
        }
    }

    async stopSchedule() {
        try {
            await this.apiRequest('/api/schedule/stop', { method: 'POST' });
            this.showNotification('定时任务已停止', 'success');
            await this.loadScheduleStatus();
        } catch (error) {
            this.showNotification('停止定时任务失败', 'error');
        }
    }

    async triggerBackup() {
        try {
            this.showProgress(true);
            await this.apiRequest('/api/schedule/trigger', { method: 'POST' });
            this.showNotification('备份任务已触发', 'success');
            
            // 延迟刷新，给备份任务一些时间完成
            setTimeout(async () => {
                await Promise.all([
                    this.loadBackups(),
                    this.loadDatabaseInfo()
                ]);
            }, 2000);
        } catch (error) {
            this.showNotification('触发备份失败', 'error');
        } finally {
            this.showProgress(false);
        }
    }

    async restoreLatest() {
        try {
            const latest = await this.apiRequest('/api/restore/latest');
            this.showRestoreModal(latest.id);
        } catch (error) {
            this.showNotification('没有可用的备份', 'warning');
        }
    }

    async refreshData() {
        try {
            this.showProgress(true);
            await this.loadInitialData();
            this.showNotification('数据刷新成功', 'success');
        } catch (error) {
            this.showNotification('数据刷新失败', 'error');
        } finally {
            this.showProgress(false);
        }
    }

    showProgress(show) {
        const container = document.querySelector('.progress-container');
        container.style.display = show ? 'block' : 'none';
    }

    showNotification(message, type = 'info') {
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    getStatusBadgeClass(status) {
        const classes = {
            'completed': 'bg-success',
            'running': 'bg-primary',
            'failed': 'bg-danger',
            'pending': 'bg-warning'
        };
        return classes[status] || 'bg-secondary';
    }

    getStatusText(status) {
        const texts = {
            'completed': '完成',
            'running': '运行中',
            'failed': '失败',
            'pending': '等待中'
        };
        return texts[status] || '未知';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString('zh-CN');
    }

    // 配置管理功能
    async loadConfig() {
        try {
            const config = await this.apiRequest('/api/config');
            this.config = config;
            this.populateConfigForm();
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    populateConfigForm() {
        if (!this.config) return;

        // 填充数据库配置
        document.getElementById('configDbHost').value = this.config.database.host;
        document.getElementById('configDbPort').value = this.config.database.port;
        document.getElementById('configDbName').value = this.config.database.database;
        document.getElementById('configDbUser').value = this.config.database.username;
        document.getElementById('configDbPassword').value = this.config.database.password;

        // 填充备份配置
        document.getElementById('configBackupPath').value = this.config.backup.storage_path;
        document.getElementById('configBackupInterval').value = this.config.backup.interval_hours;
        document.getElementById('configMaxBackups').value = this.config.backup.max_backups;
        document.getElementById('configCompression').checked = this.config.backup.compression;
        
        // 填充清理配置
        document.getElementById('configCleanupEnabled').checked = this.config.backup.cleanup_enabled || false;
        document.getElementById('configCleanupInterval').value = this.config.backup.cleanup_interval_days || 7;
        document.getElementById('configCleanupKeepDays').value = this.config.backup.cleanup_keep_days || 30;
    }

    showConfigModal() {
        this.loadConfig();
        const modal = new bootstrap.Modal(document.getElementById('configModal'));
        modal.show();
    }

    async testDatabaseConnection() {
        const resultDiv = document.getElementById('connectionTestResult');
        
        try {
            const config = {
                host: document.getElementById('configDbHost').value,
                port: parseInt(document.getElementById('configDbPort').value),
                database: document.getElementById('configDbName').value,
                username: document.getElementById('configDbUser').value,
                password: document.getElementById('configDbPassword').value
            };

            resultDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> 正在测试连接...</div>';

            const result = await this.apiRequest('/api/config/test', {
                method: 'POST',
                body: JSON.stringify(config)
            });

            if (result.success) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check"></i> ${result.message}
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-times"></i> ${result.message}
                    </div>
                `;
            }
        } catch (error) {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-times"></i> 连接测试失败: ${error.message}
                </div>
            `;
        }
    }

    async updateDatabaseConfig() {
        try {
            const config = {
                host: document.getElementById('configDbHost').value,
                port: parseInt(document.getElementById('configDbPort').value),
                database: document.getElementById('configDbName').value,
                username: document.getElementById('configDbUser').value,
                password: document.getElementById('configDbPassword').value
            };

            const result = await this.apiRequest('/api/config/database', {
                method: 'POST',
                body: JSON.stringify(config)
            });

            if (result.success) {
                this.showNotification('数据库配置更新成功', 'success');
                this.config = result.config;
                
                // 刷新页面数据
                setTimeout(() => {
                    this.loadInitialData();
                }, 1000);
            } else {
                this.showNotification('数据库配置更新失败: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('数据库配置更新失败', 'error');
        }
    }

    async updateBackupConfig() {
        try {
            const config = {
                storage_path: document.getElementById('configBackupPath').value,
                interval_hours: parseInt(document.getElementById('configBackupInterval').value),
                max_backups: parseInt(document.getElementById('configMaxBackups').value),
                compression: document.getElementById('configCompression').checked,
                cleanup_enabled: document.getElementById('configCleanupEnabled').checked,
                cleanup_interval_days: parseInt(document.getElementById('configCleanupInterval').value),
                cleanup_keep_days: parseInt(document.getElementById('configCleanupKeepDays').value)
            };

            const result = await this.apiRequest('/api/config/backup', {
                method: 'POST',
                body: JSON.stringify(config)
            });

            if (result.success) {
                this.showNotification('备份配置更新成功', 'success');
                this.config = result.config;
                
                // 刷新页面数据
                setTimeout(() => {
                    this.loadScheduleStatus();
                }, 1000);
            } else {
                this.showNotification('备份配置更新失败: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('备份配置更新失败', 'error');
        }
    }

    async manualCleanup() {
        if (!confirm('确定要清理旧备份文件吗？此操作不可撤销！')) {
            return;
        }

        try {
            this.showProgress(true);
            
            const result = await this.apiRequest('/api/cleanup', {
                method: 'POST'
            });

            if (result.success) {
                this.showNotification(result.message, 'success');
                
                // 刷新备份列表
                await this.loadBackups();
            } else {
                this.showNotification('清理失败: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('清理失败', 'error');
        } finally {
            this.showProgress(false);
        }
    }

    showTableStructure() {
        // 显示表结构模态框
        const modal = new bootstrap.Modal(document.getElementById('tableStructureModal'));
        
        // 渲染表结构信息
        this.renderTablesInfo(this.tablesData || {});
        
        modal.show();
    }

    async refreshDatabaseInfo() {
        // 专门用于刷新数据库信息的函数
        try {
            await this.loadDatabaseInfo();
            this.showNotification('数据库信息已更新', 'info');
        } catch (error) {
            console.error('刷新数据库信息失败:', error);
        }
    }
}

// 全局函数（供HTML调用）
function createBackup() {
    app.showBackupModal();
}

function confirmBackup() {
    app.confirmBackup();
}

function confirmRestore() {
    app.confirmRestore();
}

function startSchedule() {
    app.startSchedule();
}

function stopSchedule() {
    app.stopSchedule();
}

function triggerBackup() {
    app.triggerBackup();
}

function restoreLatest() {
    app.restoreLatest();
}

function refreshData() {
    app.refreshData();
}

function loadBackups() {
    app.loadBackups();
}

function showConfigModal() {
    app.showConfigModal();
}

function testDatabaseConnection() {
    app.testDatabaseConnection();
}

function updateDatabaseConfig() {
    app.updateDatabaseConfig();
}

function updateBackupConfig() {
    app.updateBackupConfig();
}

function manualCleanup() {
    app.manualCleanup();
}

// 批量删除相关函数
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const backupCheckboxes = document.querySelectorAll('.backup-checkbox');
    
    backupCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    
    updateSelection();
}

function updateSelection() {
    const checkboxes = document.querySelectorAll('.backup-checkbox');
    const selectedCheckboxes = document.querySelectorAll('.backup-checkbox:checked');
    const selectAllCheckbox = document.getElementById('selectAll');
    
    // 更新全选状态
    selectAllCheckbox.checked = checkboxes.length > 0 && selectedCheckboxes.length === checkboxes.length;
    selectAllCheckbox.indeterminate = selectedCheckboxes.length > 0 && selectedCheckboxes.length < checkboxes.length;
    
    // 更新选择计数
    document.getElementById('selectedCount').textContent = `已选择 ${selectedCheckboxes.length} 项`;
    
    // 显示/隐藏批量删除按钮
    const batchDeleteBtn = document.getElementById('batchDeleteBtn');
    batchDeleteBtn.style.display = selectedCheckboxes.length > 0 ? 'inline-block' : 'none';
}

function batchDeleteBackups() {
    const selectedCheckboxes = document.querySelectorAll('.backup-checkbox:checked');
    const selectedIds = Array.from(selectedCheckboxes).map(checkbox => checkbox.value);
    
    if (selectedIds.length === 0) {
        alert('请选择要删除的备份');
        return;
    }
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 个备份吗？此操作不可撤销。`)) {
        app.batchDeleteBackups(selectedIds);
    }
}

function showTableStructure() {
    app.showTableStructure();
}

// 控制页面关闭确认的辅助函数
function enableCloseConfirmation() {
    if (typeof window.setShouldConfirmClose === 'function') {
        window.setShouldConfirmClose(true);
    }
}

function disableCloseConfirmation() {
    if (typeof window.setShouldConfirmClose === 'function') {
        window.setShouldConfirmClose(false);
    }
}

// 初始化应用
const app = new BackupTool(); 