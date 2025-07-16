import os
import subprocess
import gzip
import asyncio
from datetime import datetime
from typing import Optional
import psycopg2
from .models import BackupInfo, DatabaseConfig, BackupConfig, RestoreResponse
from .backup import BackupManager


class RestoreManager:
    def __init__(self, db_config: DatabaseConfig, backup_config: BackupConfig):
        self.db_config = db_config
        self.backup_config = backup_config
        self.backup_manager = BackupManager(db_config, backup_config)
    
    async def restore_backup(self, backup_id: str, restore_type: str = "full", force: bool = False) -> RestoreResponse:
        """恢复指定的备份"""
        backup_info = self.backup_manager.load_backup_info(backup_id)
        if not backup_info:
            raise ValueError(f"备份 {backup_id} 不存在")
        
        if backup_info.status != "completed":
            raise ValueError(f"备份 {backup_id} 状态不正确: {backup_info.status}")
        
        backup_file = os.path.join(
            self.backup_config.storage_path,
            backup_info.filename
        )
        
        if not os.path.exists(backup_file):
            raise ValueError(f"备份文件不存在: {backup_file}")
        
        try:
            # 检查版本兼容性
            if not force:
                await self.check_version_compatibility(backup_info)
            
            # 根据恢复类型执行不同的恢复策略
            if restore_type == "normal":
                # 普通恢复 - 使用原来的恢复逻辑
                await self.execute_restore(backup_file, backup_info.compressed)
                message = f"恢复备份 {backup_id} 成功"
            elif restore_type == "full":
                await self.execute_full_restore(backup_file, backup_info.compressed)
                message = f"完全恢复备份 {backup_id} 成功"
            elif restore_type == "incremental":
                await self.execute_incremental_restore(backup_file, backup_info.compressed)
                message = f"增量恢复备份 {backup_id} 成功"
            else:
                raise ValueError(f"不支持的恢复类型: {restore_type}")
            
            return RestoreResponse(
                success=True,
                message=message,
                backup_id=backup_id,
                restored_at=datetime.now()
            )
            
        except Exception as e:
            return RestoreResponse(
                success=False,
                message=f"恢复失败: {str(e)}",
                backup_id=backup_id,
                restored_at=datetime.now()
            )
    
    async def check_version_compatibility(self, backup_info: BackupInfo):
        """检查Alembic版本兼容性"""
        if backup_info.alembic_version:
            current_version = self.backup_manager.get_alembic_version()
            if current_version and current_version != backup_info.alembic_version:
                print(f"警告: 当前版本 {current_version} 与备份版本 {backup_info.alembic_version} 不匹配")
                # 这里可以添加更严格的版本检查逻辑
    
    async def execute_full_restore(self, backup_file: str, compressed: bool):
        """执行完全恢复 - 先清空数据库，再恢复"""
        print("执行完全恢复...")
        
        # 先清空数据库中的所有表
        await self.clear_database()
        
        # 然后执行标准恢复
        await self.execute_restore(backup_file, compressed)
    
    async def execute_incremental_restore(self, backup_file: str, compressed: bool):
        """用可靠逻辑实现增量恢复：只补齐缺失数据"""
        import re
        print("🔄 [新] 执行简单增量恢复...")
        # 1. 读取备份文件内容
        if compressed:
            import gzip
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                content = f.read()
        else:
            with open(backup_file, 'r', encoding='utf-8') as f:
                content = f.read()
        # 2. 解析所有表的COPY数据
        copy_pattern = r"COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;\n(.*?)\n\\\."
        tables = {}
        for match in re.finditer(copy_pattern, content, re.DOTALL):
            table_name = match.group(1)
            columns_str = match.group(2)
            data_content = match.group(3)
            columns = [col.strip().strip('"') for col in columns_str.split(',')]
            rows = []
            for line in data_content.strip().split('\n'):
                if line.strip():
                    row_data = line.strip().split('\t')
                    if len(row_data) == len(columns):
                        rows.append(row_data)
            tables[table_name] = {
                'columns': columns,
                'rows': rows,
                'count': len(rows)
            }
            print(f"   📋 表 {table_name}: {len(rows)} 行")
            print(f"   📊 列: {columns}")
        # 3. 对比并补齐每个表
        import psycopg2
        total_inserted = 0
        for table_name, backup_data in tables.items():
            print(f"\n📊 处理表: {table_name}")
            # 获取当前数据库数据
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public' 
                ORDER BY ordinal_position
            """, (table_name,))
            db_columns = [row[0] for row in cursor.fetchall()]
            cursor.execute(f'SELECT * FROM "{table_name}" ORDER BY 1')
            db_rows = cursor.fetchall()
            # 获取主键
            cursor.execute('''
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary;
            ''', (table_name,))
            pk_columns = [row[0] for row in cursor.fetchall()]
            print(f"   主键字段: {pk_columns}")
            if not pk_columns:
                print(f"   ⚠️ 表 {table_name} 没有主键，跳过")
                conn.close()
                continue
            # 当前数据的主键集合
            def create_key(row, columns, pk_columns):
                return '|'.join([f"{pk}:{str(row[columns.index(pk)])}" for pk in pk_columns if pk in columns])
            db_keys = set()
            for row in db_rows:
                db_keys.add(create_key(row, db_columns, pk_columns))
            # 找出缺失的行
            missing_rows = []
            for row in backup_data['rows']:
                key = create_key(row, backup_data['columns'], pk_columns)
                if key not in db_keys:
                    missing_rows.append(row)
            print(f"   缺失行数: {len(missing_rows)}")
            if missing_rows:
                print(f"   缺失的主键 (前5个):")
                for i, row in enumerate(missing_rows[:5]):
                    key = create_key(row, backup_data['columns'], pk_columns)
                    print(f"     {i+1}. {key}")
                # 类型转换
                cursor.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public' 
                    ORDER BY ordinal_position
                """, (table_name,))
                column_info = cursor.fetchall()
                column_types = {col[0]: col[1] for col in column_info}
                converted_rows = []
                for row in missing_rows:
                    converted_row = []
                    for i, (col_name, value) in enumerate(zip(backup_data['columns'], row)):
                        try:
                            dtype = column_types.get(col_name, 'text')
                            if value is None or value == '' or value == 'NULL':
                                converted_row.append(None)
                            elif dtype.startswith('int'):
                                converted_row.append(int(value))
                            elif dtype.startswith('numeric') or dtype.startswith('float'):
                                converted_row.append(float(value))
                            elif dtype.startswith('date'):
                                from datetime import datetime
                                converted_row.append(datetime.strptime(value, '%Y-%m-%d').date())
                            else:
                                converted_row.append(str(value))
                        except Exception as e:
                            print(f"⚠️ 类型转换失败: {col_name}={value} -> {e}")
                            converted_row.append(value)
                    converted_rows.append(converted_row)
                # 插入
                placeholders = ', '.join(['%s'] * len(backup_data['columns']))
                column_names = ', '.join([f'"{col}"' for col in backup_data['columns']])
                insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
                try:
                    cursor.executemany(insert_sql, converted_rows)
                    conn.commit()
                    inserted_count = cursor.rowcount
                    print(f"✅ 表 {table_name} 成功插入 {inserted_count} 行")
                    total_inserted += inserted_count
                except Exception as e:
                    print(f"❌ 插入失败: {e}")
                    conn.rollback()
            else:
                print(f"   ✅ 表 {table_name} 无需恢复")
            conn.close()
        print(f"\n" + "=" * 60)
        print(f"📋 增量恢复完成")
        print(f"✅ 总共插入 {total_inserted} 行数据")
    
    async def get_current_database_snapshot(self) -> dict:
        """获取当前数据库的数据快照"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            snapshot = {}
            
            # 获取所有表名
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = cursor.fetchall()
            
            # 获取每个表的数据
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()
                    
                    # 获取列名
                    cursor.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = %s AND table_schema = 'public' 
                        ORDER BY ordinal_position
                    """, (table_name,))
                    columns_info = cursor.fetchall()
                    
                    snapshot[table_name] = {
                        'columns': [col[0] for col in columns_info],
                        'types': [col[1] for col in columns_info],
                        'rows': rows
                    }
                except Exception as e:
                    print(f"获取表 {table_name} 数据失败: {e}")
                    continue
            
            conn.close()
            return snapshot
            
        except Exception as e:
            print(f"获取数据库快照失败: {e}")
            return {}
    
    def parse_backup_data(self, sql_content: str) -> dict:
        """解析备份文件中的数据"""
        backup_data = {}
        current_table = None
        current_columns = []
        current_rows = []
        in_copy_section = False
        
        lines = sql_content.split('\n')
        
        for line in lines:
            line_upper = line.upper().strip()
            
            # 检测CREATE TABLE语句
            if line_upper.startswith('CREATE TABLE'):
                # 保存前一个表的数据
                if current_table and current_columns:
                    backup_data[current_table] = {
                        'columns': current_columns,
                        'rows': current_rows,
                        'count': len(current_rows)
                    }
                    print(f"[解析备份] 表 {current_table} 解析完成，共 {len(current_rows)} 行数据")
                
                # 开始新表 - 去掉schema前缀
                table_name = line.split()[2].strip('"')
                if '.' in table_name:
                    table_name = table_name.split('.')[-1]  # 去掉schema前缀
                current_table = table_name
                current_columns = []
                current_rows = []
                in_copy_section = False
                print(f"[解析备份] 发现表: {table_name}")
            
            # 检测COPY语句
            elif line_upper.startswith('COPY ') and current_table:
                in_copy_section = True
                # 解析列名
                if '(' in line and ')' in line:
                    cols_part = line[line.find('(')+1:line.find(')')]
                    current_columns = [col.strip().strip('"') for col in cols_part.split(',')]
                    print(f"[解析备份] 表 {current_table} 的列: {current_columns}")
            
            # 检测数据行
            elif in_copy_section and line.strip() and not line.startswith('\\'):
                if line.strip() == r'\.':
                    in_copy_section = False
                else:
                    # 解析数据行
                    row_data = line.strip().split('\t')
                    if len(row_data) == len(current_columns):
                        # 转换数据类型
                        converted_row = self.convert_backup_row_data(row_data)
                        current_rows.append(converted_row)
        
        # 保存最后一个表
        if current_table and current_columns:
            backup_data[current_table] = {
                'columns': current_columns,
                'rows': current_rows,
                'count': len(current_rows)
            }
            print(f"[解析备份] 表 {current_table} 解析完成，共 {len(current_rows)} 行数据")
        
        return backup_data
    
    def convert_backup_row_data(self, row_data: list) -> list:
        """转换备份行数据的数据类型"""
        converted = []
        for val in row_data:
            if val == '\\N' or val == '':
                converted.append(None)
            elif val.lower() == 'true':
                converted.append(True)
            elif val.lower() == 'false':
                converted.append(False)
            else:
                # 尝试转换为数字
                try:
                    if '.' in val:
                        converted.append(float(val))
                    else:
                        converted.append(int(val))
                except ValueError:
                    converted.append(val)
        return converted
    
    def get_primary_key_columns(self, table_name: str) -> list:
        """获取表的主键字段名列表"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary;
            ''', (table_name,))
            pk_columns = [row[0] for row in cursor.fetchall()]
            conn.close()
            return pk_columns
        except Exception as e:
            print(f"获取表 {table_name} 主键字段失败: {e}")
            return []

    def create_row_key(self, row: list, columns: list, pk_columns: Optional[list] = None) -> str:
        if pk_columns is None:
            pk_columns = []
        # 主键字段强制转为字符串，保证类型一致
        if pk_columns:
            key_parts = []
            for pk in pk_columns:
                if pk in columns:
                    idx = columns.index(pk)
                    val = row[idx]
                    key_parts.append(f"{pk}:{str(val) if val is not None else 'NULL'}")
            return '|'.join(key_parts)
        # fallback: 全字段
        key_parts = []
        for i, val in enumerate(row):
            key_parts.append(f"{columns[i]}:{str(val) if val is not None else 'NULL'}")
        return '|'.join(key_parts)

    def create_row_keys(self, rows: list, columns: list, pk_columns: Optional[list] = None) -> set:
        """为所有行创建唯一标识集合，优先用主键字段"""
        if pk_columns is None:
            pk_columns = []
        keys = set()
        for row in rows:
            key = self.create_row_key(row, columns, pk_columns)
            keys.add(key)
        return keys

    def calculate_incremental_restore_data(self, current_snapshot: dict, backup_data: dict) -> list:
        """只补齐备份有但当前没有的数据，唯一性优先用主键"""
        restore_data = []
        for table_name, backup_table_data in backup_data.items():
            if table_name not in current_snapshot:
                # 表不存在，跳过（或可选实现创建表）
                print(f"[增量恢复] 表 {table_name} 不存在，跳过")
                continue
            current_table_data = current_snapshot[table_name]
            pk_columns = self.get_primary_key_columns(table_name) or []
            # 生成唯一key集合
            current_keys = self.create_row_keys(current_table_data['rows'], current_table_data['columns'], pk_columns)
            backup_keys = self.create_row_keys(backup_table_data['rows'], backup_table_data['columns'], pk_columns)
            # 找出备份有但当前没有的key
            missing_keys = backup_keys - current_keys
            missing_rows = []
            for row in backup_table_data['rows']:
                row_key = self.create_row_key(row, backup_table_data['columns'], pk_columns)
                if row_key in missing_keys:
                    missing_rows.append(row)
            if missing_rows:
                print(f"[增量恢复] 表 {table_name} 需补齐 {len(missing_rows)} 行")
                restore_data.append({
                    'type': 'rows_missing',
                    'table': table_name,
                    'missing_rows': missing_rows,
                    'columns': backup_table_data['columns']
                })
        return restore_data
    
    async def execute_incremental_restore_data(self, restore_data: list):
        """执行增量恢复数据"""
        for item in restore_data:
            if item['type'] == 'table_missing':
                # 表不存在，需要创建表并插入所有数据
                print(f"表 {item['table']} 不存在，需要创建表结构")
                await self.create_table_and_restore_data(item)
                
            elif item['type'] == 'rows_missing':
                # 检查表是否存在
                if await self.table_exists(item['table']):
                    # 为每个表单独处理，避免事务冲突
                    await self.restore_table_missing_rows(item)
                else:
                    print(f"表 {item['table']} 不存在，跳过数据恢复")
    
    async def create_table_and_restore_data(self, item: dict):
        """创建表并恢复数据"""
        table_name = item['table']
        table_data = item['data']
        
        print(f"尝试创建表 {table_name} 并恢复数据")
        
        # 这里需要从备份文件中提取CREATE TABLE语句
        # 由于当前实现限制，我们暂时跳过表创建
        print(f"表 {table_name} 创建功能暂未实现，跳过")
        print(f"建议先使用普通恢复或完全恢复来创建表结构")
    
    async def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table_name,))
            
            result = cursor.fetchone()
            exists = result[0] if result else False
            
            conn.close()
            return exists
            
        except Exception as e:
            print(f"检查表 {table_name} 是否存在时出错: {e}")
            return False
    
    async def restore_table_missing_rows(self, item: dict):
        """恢复单个表的缺失行 - 改进版本"""
        table_name = item['table']
        columns = item['columns']
        missing_rows = item['missing_rows']
        print(f"🔄 恢复表 {table_name} 中缺失的 {len(missing_rows)} 行数据")
        if not missing_rows:
            print(f"✅ 表 {table_name} 无需恢复数据")
            return
        # 获取主键字段
        pk_columns = self.get_primary_key_columns(table_name)
        # 尝试批量插入以提高性能
        batch_size = 100
        success_count = 0
        error_count = 0
        for i in range(0, len(missing_rows), batch_size):
            batch = missing_rows[i:i + batch_size]
            try:
                # 极详细日志：打印每一条缺失行的主键和值
                for row in batch:
                    pk_info = ', '.join([f'{pk}={row[columns.index(pk)]}' for pk in pk_columns if pk in columns])
                    print(f"[增量恢复][准备插入] 主键: {pk_info} 全部字段: {dict(zip(columns, row))}")
                batch_success = await self.insert_batch_rows(table_name, columns, batch)
                success_count += batch_success
                print(f"📦 批次 {i//batch_size + 1}: 成功插入 {batch_success}/{len(batch)} 行")
            except Exception as e:
                print(f"❌ 批次 {i//batch_size + 1} 失败: {e}")
                error_count += len(batch)
                # 如果批量插入失败，尝试逐行插入
                for row in batch:
                    try:
                        pk_info = ', '.join([f'{pk}={row[columns.index(pk)]}' for pk in pk_columns if pk in columns])
                        print(f"[增量恢复][单行插入] 主键: {pk_info} 全部字段: {dict(zip(columns, row))}")
                        await self.insert_single_row(table_name, columns, row)
                        success_count += 1
                    except Exception as row_error:
                        print(f"❌ 单行插入失败: {row_error}")
                        error_count += 1
        print(f"✅ 表 {table_name} 恢复完成: 成功 {success_count} 行, 失败 {error_count} 行")
    
    async def insert_batch_rows(self, table_name: str, columns: list, rows: list) -> int:
        if not rows:
            return 0
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public' 
                ORDER BY ordinal_position
            """, (table_name,))
            column_info = cursor.fetchall()
            column_types = {col[0]: col[1] for col in column_info}
            column_nullable = {col[0]: col[2] == 'YES' for col in column_info}
            # 转换所有行的数据类型
            converted_rows = []
            for row in rows:
                converted_row = []
                for i, (col_name, value) in enumerate(zip(columns, row)):
                    try:
                        # 类型转换：int/float/str/date
                        dtype = column_types.get(col_name, 'text')
                        if value is None or value == '' or value == 'NULL':
                            converted_row.append(None)
                        elif dtype.startswith('int'):
                            converted_row.append(int(value))
                        elif dtype.startswith('numeric') or dtype.startswith('float') or dtype.startswith('double'):
                            converted_row.append(float(value))
                        elif dtype.startswith('date'):
                            from datetime import datetime
                            converted_row.append(datetime.strptime(value, '%Y-%m-%d').date())
                        else:
                            converted_row.append(str(value))
                    except Exception as e:
                        print(f"⚠️ 数据类型转换失败: {col_name}={value} -> {e}")
                        converted_row.append(value)
                converted_rows.append(converted_row)
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])
            insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
            if self.has_primary_key(table_name):
                insert_sql += ' ON CONFLICT DO NOTHING'
            # 日志：打印将要插入的主键
            pk_columns = self.get_primary_key_columns(table_name)
            for row in converted_rows:
                pk_info = ', '.join([f'{pk}={row[columns.index(pk)]}' for pk in pk_columns if pk in columns])
                print(f"[增量恢复] 插入前主键信息: {pk_info}")
            cursor.executemany(insert_sql, converted_rows)
            conn.commit()
            print(f"[增量恢复] 表 {table_name} 成功插入 {len(converted_rows)} 行数据")
            return len(converted_rows)
        except Exception as e:
            print(f"❌ 批量插入失败: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()
    
    async def insert_single_row(self, table_name: str, columns: list, row_data: list):
        """插入单行数据 - 改进版本，处理数据类型转换"""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            # 获取表的列信息，包括数据类型
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public' 
                ORDER BY ordinal_position
            """, (table_name,))
            column_info = cursor.fetchall()
            
            # 创建列名到数据类型的映射
            column_types = {col[0]: col[1] for col in column_info}
            column_nullable = {col[0]: col[2] == 'YES' for col in column_info}
            
            # 转换数据类型
            converted_data = []
            for i, (col_name, value) in enumerate(zip(columns, row_data)):
                try:
                    converted_value = self.convert_value_for_column(value, column_types.get(col_name, 'text'), column_nullable.get(col_name, True))
                    converted_data.append(converted_value)
                except Exception as e:
                    print(f"⚠️ 列 {col_name} 数据类型转换失败: {value} -> {e}")
                    # 如果转换失败，使用原始值
                    converted_data.append(value)
            
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])
            
            insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
            
            # 使用ON CONFLICT DO NOTHING避免主键冲突
            if self.has_primary_key(table_name):
                insert_sql += ' ON CONFLICT DO NOTHING'
            
            cursor.execute(insert_sql, converted_data)
            
            conn.commit()
            
        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            print(f"⚠️ 数据完整性错误 (表 {table_name}): {e}")
            # 不抛出异常，继续处理下一行
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ 插入数据失败 (表 {table_name}): {e}")
            # 不抛出异常，继续处理下一行
        finally:
            if conn:
                conn.close()
    
    def convert_value_for_column(self, value, column_type: str, is_nullable: bool):
        """根据列类型转换值"""
        if value is None:
            if is_nullable:
                return None
            else:
                # 根据列类型提供默认值
                if 'int' in column_type:
                    return 0
                elif 'float' in column_type or 'numeric' in column_type:
                    return 0.0
                elif 'bool' in column_type:
                    return False
                else:
                    return ''
        
        # 处理字符串类型
        if isinstance(value, str):
            if value.lower() == 'null':
                return None if is_nullable else ''
            elif value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
        
        # 根据列类型进行转换
        try:
            if 'int' in column_type:
                return int(value) if value is not None else 0
            elif 'float' in column_type or 'numeric' in column_type:
                return float(value) if value is not None else 0.0
            elif 'bool' in column_type:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                else:
                    return bool(value)
            else:
                # 文本类型，确保是字符串
                return str(value) if value is not None else ''
        except (ValueError, TypeError) as e:
            print(f"⚠️ 数据类型转换失败: {value} -> {column_type}: {e}")
            # 返回原始值
            return value
    
    def has_primary_key(self, table_name: str) -> bool:
        """检查表是否有主键"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints 
                WHERE table_name = %s 
                AND constraint_type = 'PRIMARY KEY'
            """, (table_name,))
            
            result = cursor.fetchone()
            has_pk = result[0] > 0 if result else False
            
            conn.close()
            return has_pk
            
        except Exception as e:
            print(f"检查主键失败: {e}")
            return False
    
    def filter_cleanup_commands(self, sql_content: str) -> str:
        """过滤掉清理命令，只保留数据插入部分"""
        lines = sql_content.split('\n')
        filtered_lines = []
        in_data_section = False
        
        for line in lines:
            line_upper = line.upper().strip()
            
            # 跳过数据库级别的操作
            if any(keyword in line_upper for keyword in [
                'DROP DATABASE', 'CREATE DATABASE', 'DROP SCHEMA', 'CREATE SCHEMA'
            ]):
                continue
            
            # 跳过表结构删除操作
            if any(keyword in line_upper for keyword in [
                'DROP TABLE IF EXISTS', 'DROP TABLE', 'DROP SEQUENCE', 'DROP INDEX',
                'DROP VIEW', 'DROP FUNCTION', 'DROP TRIGGER', 'DROP RULE'
            ]):
                continue
            
            # 跳过COMMENT ON等元数据命令
            if line_upper.startswith('COMMENT ON'):
                continue
            
            # 跳过SET语句（环境设置）
            if line_upper.startswith('SET ') and not in_data_section:
                continue
            
            # 跳过SELECT pg_catalog.set_config等系统调用
            if 'pg_catalog.set_config' in line_upper and not in_data_section:
                continue
            
            # 检测数据部分的开始
            if 'COPY ' in line_upper or line_upper.startswith('INSERT INTO'):
                in_data_section = True
            
            # 保留CREATE TABLE语句（表结构）
            if line_upper.startswith('CREATE TABLE'):
                filtered_lines.append(line)
                continue
            
            # 保留所有数据操作语句
            if in_data_section or any(keyword in line_upper for keyword in [
                'INSERT INTO', 'COPY ', 'SELECT ', 'VALUES'
            ]):
                filtered_lines.append(line)
                continue
            
            # 保留其他可能有用的语句
            if not line_upper.startswith('--') and line.strip():  # 保留非注释行
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    async def execute_filtered_restore(self, sql_content: str):
        """执行过滤后的SQL恢复"""
        # 构建psql命令
        cmd = [
            'psql',
            f'--host={self.db_config.host}',
            f'--port={self.db_config.port}',
            f'--username={self.db_config.username}',
            f'--dbname={self.db_config.database}',
            '--quiet'
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config.password
        
        # 执行SQL恢复
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate(input=sql_content.encode('utf-8'))
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace').strip()
            raise Exception(f"增量恢复失败: {error_msg}")
    
    async def clear_database(self):
        """清空数据库中的所有表"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = cursor.fetchall()
            
            # 删除所有表
            for table in tables:
                table_name = table[0]
                cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            
            conn.commit()
            conn.close()
            print(f"已清空数据库中的 {len(tables)} 个表")
            
        except Exception as e:
            raise Exception(f"清空数据库失败: {str(e)}")
    
    async def clear_table_data_only(self):
        """只清空表数据，保留表结构"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = cursor.fetchall()
            
            # 只清空表数据，不删除表结构
            for table in tables:
                table_name = table[0]
                cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
            
            conn.commit()
            conn.close()
            print(f"已清空 {len(tables)} 个表的数据，保留表结构")
            
        except Exception as e:
            raise Exception(f"清空表数据失败: {str(e)}")
    
    def filter_for_incremental_restore(self, sql_content: str) -> str:
        """为增量恢复过滤SQL，只保留数据插入部分"""
        lines = sql_content.split('\n')
        filtered_lines = []
        in_data_section = False
        
        for line in lines:
            line_upper = line.upper().strip()
            
            # 跳过数据库级别的操作
            if any(keyword in line_upper for keyword in [
                'DROP DATABASE', 'CREATE DATABASE', 'DROP SCHEMA', 'CREATE SCHEMA'
            ]):
                continue
            
            # 跳过表结构操作（保留现有表结构）
            if any(keyword in line_upper for keyword in [
                'DROP TABLE IF EXISTS', 'DROP TABLE', 'CREATE TABLE', 'DROP SEQUENCE', 
                'DROP INDEX', 'DROP VIEW', 'DROP FUNCTION', 'DROP TRIGGER', 'DROP RULE',
                'ALTER TABLE', 'CREATE INDEX', 'CREATE SEQUENCE'
            ]):
                continue
            
            # 跳过COMMENT ON等元数据命令
            if line_upper.startswith('COMMENT ON'):
                continue
            
            # 跳过SET语句（环境设置）
            if line_upper.startswith('SET ') and not in_data_section:
                continue
            
            # 跳过SELECT pg_catalog.set_config等系统调用
            if 'pg_catalog.set_config' in line_upper and not in_data_section:
                continue
            
            # 检测数据部分的开始
            if 'COPY ' in line_upper or line_upper.startswith('INSERT INTO'):
                in_data_section = True
            
            # 保留所有数据操作语句
            if in_data_section or any(keyword in line_upper for keyword in [
                'INSERT INTO', 'COPY ', 'SELECT ', 'VALUES'
            ]):
                filtered_lines.append(line)
                continue
            
            # 保留其他可能有用的语句（但不包括表结构）
            if not line_upper.startswith('--') and line.strip() and not any(keyword in line_upper for keyword in [
                'CREATE', 'DROP', 'ALTER'
            ]):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    async def execute_restore(self, backup_file: str, compressed: bool):
        """执行恢复命令"""
        # 构建psql命令
        cmd = [
            'psql',
            f'--host={self.db_config.host}',
            f'--port={self.db_config.port}',
            f'--username={self.db_config.username}',
            f'--dbname={self.db_config.database}',
            '--quiet'
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config.password
        
        # 读取SQL内容
        if compressed:
            # 从压缩文件读取内容
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                sql_content = f.read()
        else:
            # 从普通文件读取内容
            with open(backup_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
        
        # 执行SQL恢复
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate(input=sql_content.encode('utf-8'))
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace').strip()
            raise Exception(f"恢复失败: {error_msg}")
    
    def get_latest_backup(self) -> Optional[BackupInfo]:
        """获取最新的备份"""
        backups = self.backup_manager.get_backup_list()
        completed_backups = [b for b in backups if b.status == "completed"]
        return completed_backups[0] if completed_backups else None
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            conn.close()
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    async def get_database_info(self) -> dict:
        """获取数据库信息"""
        try:
            conn = psycopg2.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                database=self.db_config.database,
                user=self.db_config.username,
                password=self.db_config.password
            )
            cursor = conn.cursor()
            
            # 获取数据库大小
            cursor.execute(f"SELECT pg_size_pretty(pg_database_size('{self.db_config.database}'))")
            db_size_result = cursor.fetchone()
            db_size = db_size_result[0] if db_size_result else "Unknown"
            
            # 获取表数量
            cursor.execute("""
                SELECT count(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count_result = cursor.fetchone()
            table_count = table_count_result[0] if table_count_result else 0
            
            # 获取表名和表结构信息
            cursor.execute("""
                SELECT 
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)
            columns_result = cursor.fetchall()
            
            # 组织表结构数据
            tables = {}
            for row in columns_result:
                table_name, column_name, data_type, is_nullable, column_default = row
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append({
                    "column_name": column_name,
                    "data_type": data_type,
                    "is_nullable": is_nullable,
                    "column_default": column_default
                })
            
            conn.close()
            
            return {
                "database_size": db_size,
                "table_count": table_count,
                "tables": tables
            }
            
        except Exception as e:
            return {"error": str(e)} 