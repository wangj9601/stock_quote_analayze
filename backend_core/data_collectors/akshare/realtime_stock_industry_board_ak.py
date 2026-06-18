import akshare as ak
import pandas as pd
import traceback
from datetime import datetime
import sys
from backend_core.config.config import DATA_COLLECTORS
from backend_core.database.db import SessionLocal
from backend_core.data_collectors.akshare.industry_board_normalize import (
    enrich_leading_stock_codes,
    industry_board_to_english_df,
    normalize_ths_industry_df,
)
from backend_core.data_collectors.akshare.board_code_rules import is_concept_board_code

try:
    from backend_api.utils.industry_board_query import lookup_leading_code_from_constituents
except ImportError:
    lookup_leading_code_from_constituents = None  # type: ignore
from sqlalchemy import text

class RealtimeStockIndustryBoardCollector:
    def __init__(self):
        self.db_file = DATA_COLLECTORS['akshare']['db_file']
        self.table_name = 'industry_board_realtime_quotes'
        self.log_table = 'realtime_collect_operation_logs'
        self._init_db()

    def _init_db(self):
        session = SessionLocal()
        try:
            # 创建行业板块基本信息表
            print("Creating industry_board_basic_info...")
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS industry_board_basic_info (
                    board_code TEXT PRIMARY KEY,
                    board_name TEXT,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            session.commit()
            print("Created industry_board_basic_info.")
        except Exception as e:
            print(f"Error creating industry_board_basic_info: {e}")
            session.rollback()

        try:
            # 创建行业板块实时行情表
            print(f"Creating {self.table_name}...")
            session.execute(text(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    board_code TEXT,
                    board_name TEXT,
                    latest_price REAL,
                    change_amount REAL,
                    change_percent REAL,
                    total_market_value REAL,
                    volume REAL,
                    amount REAL,
                    turnover_rate REAL,
                    up_count INTEGER,
                    down_count INTEGER,
                    leading_stock_name TEXT,
                    leading_stock_change_percent REAL,
                    leading_stock_code TEXT,
                    update_time TIMESTAMP,
                    PRIMARY KEY (board_code, update_time)
                )
            '''))
            session.commit()
            # 兼容旧表结构：补齐历史缺失字段
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS up_count INTEGER"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS down_count INTEGER"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_name TEXT"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_change_percent REAL"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_code TEXT"))
            session.commit()
            print(f"Created {self.table_name}.")
        except Exception as e:
            print(f"Error creating {self.table_name}: {e}")
            session.rollback()

        try:
            # 创建日志表
            print(f"Creating {self.log_table}...")
            session.execute(text(f'''
                CREATE TABLE IF NOT EXISTS {self.log_table} (
                    id SERIAL PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_desc TEXT NOT NULL,
                    affected_rows INTEGER,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            session.commit()
            print(f"Created {self.log_table}.")
        except Exception as e:
            print(f"Error creating {self.log_table}: {e}")
            session.rollback()
        finally:
            session.close()

    def fetch_data(self):
        # 调用akshare接口
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            print(f"[采集] 东方财富接口调用失败: {e}，尝试调用同花顺接口...")
            try:
                df = ak.stock_board_industry_summary_ths()
                return normalize_ths_industry_df(df)
            except Exception as e2:
                print(f"[采集] 同花顺接口调用也失败: {e2}")
                raise e # 抛出原始异常或新异常

    def _load_stock_name_code_map(self, session) -> dict:
        try:
            rows = session.execute(
                text(
                    "SELECT code, name FROM stock_basic_info "
                    "WHERE name IS NOT NULL AND code IS NOT NULL"
                )
            ).fetchall()
            return {str(name).strip(): str(code).strip() for code, name in rows if name and code}
        except Exception as e:
            print(f"[采集] 读取 stock_basic_info 失败，跳过领涨股代码补全: {e}")
            return {}

    def save_to_db(self, df):
        session = SessionLocal()
        try:
            now = datetime.now().replace(microsecond=0)
            df = industry_board_to_english_df(df)
            if df.empty:
                return False, "归一化后数据为空"
            name_code_map = self._load_stock_name_code_map(session)
            df = enrich_leading_stock_codes(df, name_code_map)
            if lookup_leading_code_from_constituents and "leading_stock_name" in df.columns:
                if "leading_stock_code" not in df.columns:
                    df["leading_stock_code"] = None
                for idx, row in df.iterrows():
                    existing = row.get("leading_stock_code")
                    if existing is not None and not pd.isna(existing) and str(existing).strip():
                        continue
                    bcode = row.get("board_code")
                    lname = row.get("leading_stock_name")
                    if pd.isna(bcode) or pd.isna(lname):
                        continue
                    code = lookup_leading_code_from_constituents(
                        session, str(bcode).strip(), str(lname).strip()
                    )
                    if code:
                        df.at[idx, "leading_stock_code"] = code
            df["update_time"] = now
            
            # 更新行业板块基本信息表
            # 使用 executemany 优化性能? 或者简单的循环
            # 这里为了简单和处理冲突，使用循环
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS concept_board_basic_info (
                    board_code VARCHAR(20) PRIMARY KEY,
                    board_name VARCHAR(100),
                    create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
            '''))
            session.commit()

            basic_info_count = 0
            concept_basic_count = 0
            for _, row in df.iterrows():
                # 确保 board_code 存在且不为空
                if pd.isna(row.get('board_code')) or row.get('board_code') == '':
                    print(f"Skipping row with empty board_code: {row.get('board_name')}")
                    continue

                bcode = str(row['board_code']).strip()
                try:
                    if is_concept_board_code(bcode):
                        session.execute(text('''
                            INSERT INTO concept_board_basic_info (board_code, board_name, create_date)
                            VALUES (:board_code, :board_name, :create_date)
                            ON CONFLICT (board_code) DO UPDATE SET
                                board_name = EXCLUDED.board_name,
                                create_date = EXCLUDED.create_date
                        '''), {
                            'board_code': bcode,
                            'board_name': row['board_name'],
                            'create_date': now
                        })
                        concept_basic_count += 1
                    else:
                        session.execute(text('''
                            INSERT INTO industry_board_basic_info (board_code, board_name, create_date)
                            VALUES (:board_code, :board_name, :create_date)
                            ON CONFLICT (board_code) DO UPDATE SET
                                board_name = EXCLUDED.board_name,
                                create_date = EXCLUDED.create_date
                        '''), {
                            'board_code': bcode,
                            'board_name': row['board_name'],
                            'create_date': now
                        })
                        basic_info_count += 1
                except Exception as e:
                    print(f"Error inserting basic info for {row.get('board_code')}: {e}")

            print(f"Inserted/updated {basic_info_count} industry + {concept_basic_count} concept basic_info")
            session.commit()  # Commit basic info changes
            
            columns = list(df.columns)
            # 清空旧数据（可选，或用upsert）
            session.execute(text(f"DELETE FROM {self.table_name}"))
            # 插入新数据（upsert）
            for _, row in df.iterrows():
                if pd.isna(row.get("board_code")) or str(row.get("board_code", "")).strip() == "":
                    continue
                if is_concept_board_code(str(row.get("board_code"))):
                    continue
                value_dict = {}
                for col in columns:
                    v = row[col]
                    if hasattr(v, 'item'):
                        v = v.item()
                    if pd.isna(v):
                        v = None
                    if str(type(v)).endswith("Timestamp'>"):
                        v = v.to_pydatetime().isoformat()
                    if col == 'update_time' and not isinstance(v, str):
                        v = v.isoformat()
                    value_dict[col] = v
                placeholders = ','.join([f':{col}' for col in columns])
                col_names = ','.join([f'"{col}"' for col in columns])
                # 构造upsert SQL
                update_set = ','.join([f'"{col}"=EXCLUDED."{col}"' for col in columns if col not in ('board_code','update_time')])
                sql = f'INSERT INTO {self.table_name} ({col_names}) VALUES ({placeholders}) ON CONFLICT (board_code, update_time) DO UPDATE SET {update_set}'
                session.execute(text(sql), value_dict)
            session.commit()
            return True, None
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def write_log(self, operation_type, operation_desc, affected_rows, status, error_message=None):
        session = SessionLocal()
        try:
            now = datetime.now().replace(microsecond=0)
            session.execute(text(f"INSERT INTO {self.log_table} (operation_type, operation_desc, affected_rows, status, error_message, created_at) VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)"),
                           {'operation_type': operation_type, 'operation_desc': operation_desc, 'affected_rows': affected_rows, 'status': status, 'error_message': error_message or '', 'created_at': now})
            session.commit()
        except Exception as e:
            print(f"[LOG ERROR] {e}")
        finally:
            session.close()

    def run(self):
        try:
            print("[采集] 开始采集行业板块实时行情...")
            df = self.fetch_data()
            print(f"[采集] 获取到{len(df)}条数据")
            ok, err = self.save_to_db(df)
            if ok:
                print("[采集] 数据写入成功")
                self.write_log(
                    operation_type="industry_board_realtime",
                    operation_desc="采集行业板块实时行情",
                    affected_rows=len(df),
                    status="success",
                    error_message=None
                )
            else:
                print(f"[采集] 数据写入失败: {err}")
                self.write_log(
                    operation_type="industry_board_realtime",
                    operation_desc="采集行业板块实时行情",
                    affected_rows=0,
                    status="fail",
                    error_message=err
                )
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[采集] 采集异常: {e}\n{tb}")
            self.write_log(
                operation_type="industry_board_realtime",
                operation_desc="采集行业板块实时行情",
                affected_rows=0,
                status="fail",
                error_message=str(e) + "\n" + tb
            )

if __name__ == '__main__':
    collector = RealtimeStockIndustryBoardCollector()
    collector.run()
