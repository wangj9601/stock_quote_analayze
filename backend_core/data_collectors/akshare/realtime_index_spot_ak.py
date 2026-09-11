import akshare as ak
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
from backend_core.config.config import DATA_COLLECTORS
from backend_core.database.db import SessionLocal
from sqlalchemy import text


class RealtimeIndexSpotAkCollector:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DATA_COLLECTORS['akshare']['db_file']
        self.db_file = Path(db_path)
        self.logger = logging.getLogger('RealtimeIndexSpotAkCollector')
        # 确保数据库目录存在
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        session = SessionLocal()
        # 指数实时行情表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS index_realtime_quotes (
                code TEXT,
                name TEXT,
                price REAL,
                change REAL,
                pct_chg REAL,
                open REAL,
                pre_close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                amplitude REAL,
                turnover REAL,
                pe REAL,
                volume_ratio REAL,
                update_time TEXT,
                collect_time TEXT,
                index_spot_type INT,
                PRIMARY KEY (code, update_time, index_spot_type)
            )
        '''))
        # 操作日志表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS realtime_collect_operation_logs (
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
        return session

    def _get_index_spot_type(self, name: str) -> int:
        name = str(name or "")
        if any(x in name for x in ['上证', '科创', 'ＳＴＡＲ', 'ＳＥＥ', 'ＳＨＥ', 'Ｓ０', '５０', '１８０', '３８０']):
            return 2  # 上证系列
        if any(x in name for x in ['深证', '创业', 'ＣＮ', '１００', '新', 'Ａ股', 'Ｂ股']):
            return 3  # 深证系列
        if any(x in name for x in ['沪深', '中证', '全指', '基金指数', '综合', '红利']):
            return 1  # 沪深重要指数
        return 0  # 其他

    def _fetch_sina_index_spot(self) -> pd.DataFrame:
        """新浪指数实时（优先路径）。"""
        df = ak.stock_zh_index_spot_sina()
        if df is None:
            raise ValueError("新浪接口返回None")
        if df.empty:
            raise ValueError("新浪接口返回空数据")
        required_columns = [
            '代码', '名称', '最新价', '涨跌额', '涨跌幅',
            '今开', '昨收', '最高', '最低', '成交量', '成交额',
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"新浪接口返回数据缺少必要列: {missing_columns}")
        df = df.copy()
        df['index_spot_type'] = df['名称'].map(self._get_index_spot_type)
        df = df.drop_duplicates(subset=['代码'], keep='first')
        return df

    def _fetch_em_index_spot(self) -> pd.DataFrame:
        """东方财富指数实时（兜底路径）。"""
        df1 = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        df1['index_spot_type'] = 1
        df2 = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        df2['index_spot_type'] = 2
        df3 = ak.stock_zh_index_spot_em(symbol="深证系列指数")
        df3['index_spot_type'] = 3
        df = pd.concat([df1, df2, df3], ignore_index=True)
        df = df.drop_duplicates(subset=['代码'], keep='first')
        return df

    def collect_quotes(self):
        session = None
        try:
            session = self._init_db()
            # 优先新浪；失败再东财官网接口
            df = None
            try:
                df = self._fetch_sina_index_spot()
                self.logger.info("成功使用新浪接口获取指数数据")
            except Exception as sina_e:
                self.logger.warning(
                    "新浪指数数据接口失败，原因：%s，尝试调用东方财富接口。",
                    sina_e,
                )
                try:
                    df = self._fetch_em_index_spot()
                    self.logger.info("成功使用东方财富接口获取指数数据")
                except Exception as em_e:
                    self.logger.error("东方财富指数接口也失败，原因：%s", em_e)
                    raise Exception(
                        f"所有指数数据接口均失败。新浪接口错误：{sina_e}，"
                        f"东方财富接口错误：{em_e}"
                    )

            # 验证 df 是否有效，防止后续处理 None 或空数据
            if df is None or df.empty:
                raise ValueError("未能获取有效的指数数据")

            df['collect_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            affected_rows = 0
            # 清空表
            session.execute(text('DELETE FROM index_realtime_quotes'))
            for _, row in df.iterrows():
                session.execute(text('''
                    INSERT INTO index_realtime_quotes (
                        code, name, price, change, pct_chg, open, pre_close, high, low, volume, amount, amplitude, volume_ratio, update_time, collect_time, index_spot_type
                    ) VALUES (
                        :code, :name, :price, :change, :pct_chg, :open, :pre_close, :high, :low, :volume, :amount, :amplitude, :volume_ratio, :update_time, :collect_time, :index_spot_type
                    )
                    ON CONFLICT (code, update_time, index_spot_type) DO UPDATE SET
                        name = EXCLUDED.name,
                        price = EXCLUDED.price,
                        change = EXCLUDED.change,
                        pct_chg = EXCLUDED.pct_chg,
                        open = EXCLUDED.open,
                        pre_close = EXCLUDED.pre_close,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        volume = EXCLUDED.volume,
                        amount = EXCLUDED.amount,
                        amplitude = EXCLUDED.amplitude,
                        volume_ratio = EXCLUDED.volume_ratio,
                        update_time = EXCLUDED.update_time,
                        collect_time = EXCLUDED.collect_time,
                        index_spot_type = EXCLUDED.index_spot_type
                '''),
                {'code': row['代码'], 'name': row['名称'], 'price': row['最新价'], 'change': row['涨跌额'], 'pct_chg': row['涨跌幅'], 'open': row['今开'], 'pre_close': row['昨收'],
                    'high': row['最高'],
                    'low': row['最低'],
                    'volume': row['成交量'],
                    'amount': row['成交额'],
                    # 如果数据来源为新浪，振幅需要系统计算
                    'amplitude': (row['最高'] - row['最低']) / row['昨收'] * 100 if '振幅' not in row or pd.isnull(row['振幅']) else row['振幅'],
                    # 对于新浪数据，量比需要系统自行计算（假设为1，或用合适的算法替代）
                    'volume_ratio': row['量比'] if '量比' in row and not pd.isnull(row['量比']) else 1,  # 如果量比不存在，则设置为1
                    'update_time': row['update_time'],
                    'collect_time': row['collect_time'],
                    'index_spot_type': row['index_spot_type']
                })
                affected_rows += 1
            # 记录操作日志
            # 安全获取df的长度，防止df为None
            df_len = len(df) if df is not None and not df.empty else 0
            session.execute(text('''
                INSERT INTO realtime_collect_operation_logs
                (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES (
                    :operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at
                )
            '''),
            {
                'operation_type': 'index_realtime_quote_collect',
                'operation_desc': f'采集并更新{df_len}条指数实时行情数据',
                'affected_rows': affected_rows,
                'status': 'success',
                'error_message': None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            session.commit()
            session.close()
            self.logger.info("全部指数实时行情数据采集并入库完成")
            return df

        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            # 记录错误日志
            try:
                if 'session' in locals() and session is not None:
                    session.execute(text('''
                        INSERT INTO realtime_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                        VALUES (
                            :operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at
                        )
                    '''),
                    {
                        'operation_type': 'index_realtime_quote_collect',
                        'operation_desc': '采集指数实时行情数据失败',
                        'affected_rows': 0,
                        'status': 'error',
                        'error_message': error_msg,
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    session.commit()
            except Exception as log_error:
                self.logger.error(f"记录错误日志失败: {log_error}")
            finally:
                if 'session' in locals() and session is not None:
                    session.close()
            return None
