import akshare as ak
import traceback
from datetime import datetime
import sys
import os
from backend_core.config.config import DATA_COLLECTORS
from backend_core.database.db import SessionLocal
from sqlalchemy import text

class RealtimeStockIndustryBoardCollector:
    def __init__(self):
        self.db_file = DATA_COLLECTORS['akshare']['db_file']
        self.table_name = 'industry_board_realtime_quotes'
        self.log_table = 'realtime_collect_operation_logs'

    def fetch_data(self):
        # 调用akshare接口
        df = ak.stock_board_industry_name_em()
        return df

    def save_to_db(self, df):
        session = SessionLocal()
        try:
            # 字段映射：中文->英文
            col_map = {
                "板块代码": "board_code",
                "板块名称": "board_name",
                "最新价": "latest_price",
                "涨跌额": "change_amount",
                "涨跌幅": "change_percent",
                "总市值": "total_market_value",
                "成交量": "volume",
                "成交额": "amount",
                "换手率": "turnover_rate",
                "领涨股": "leading_stock_name",
                "领涨股涨跌幅": "leading_stock_change_percent",
                "领涨股代码": "leading_stock_code"
            }
            # 只保留映射字段
            now = datetime.now().replace(microsecond=0)
            keep_cols = [k for k in col_map.keys() if k in df.columns]
            df = df[keep_cols].rename(columns=col_map)
            df['update_time'] = now
            columns = list(df.columns)
            # 清空旧数据（可选，或用upsert）
            session.execute(text(f"DELETE FROM {self.table_name}"))
            # 插入新数据（upsert）
            for _, row in df.iterrows():
                value_dict = {}
                for col in columns:
                    v = row[col]
                    if hasattr(v, 'item'):
                        v = v.item()
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
