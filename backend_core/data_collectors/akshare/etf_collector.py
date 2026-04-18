#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF基金行情数据采集器
支持ETF列表同步、实时行情采集、历史行情采集及技术指标计算
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time
import random

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import akshare as ak
import pandas as pd
from backend_core.database.db import SessionLocal
from sqlalchemy import text

from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.rsi_calculator import RSICalculator
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etf_collect.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ETFCollector:
    """ETF基金数据采集器"""

    # ETF 指标表中使用的 market_type 标识
    MARKET_TYPE = 'ETF'

    def __init__(self):
        self.session = SessionLocal()
        self.collected_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_funds = []
        self._init_tables()

    def __del__(self):
        """析构函数，确保session被关闭"""
        if hasattr(self, 'session'):
            self.session.close()

    def _init_tables(self):
        """初始化基金相关表结构"""
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS fund_basic_info (
                    code VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    fund_type VARCHAR(20),
                    listing_date TEXT,
                    fund_company VARCHAR(100),
                    industry TEXT,
                    total_shares REAL,
                    free_float_shares REAL,
                    shares_updated_at TIMESTAMP,
                    collect_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS fund_realtime_quote (
                    code VARCHAR(20) NOT NULL,
                    trade_date VARCHAR(20) NOT NULL,
                    name VARCHAR(100),
                    current_price REAL,
                    change_percent REAL,
                    volume REAL,
                    amount REAL,
                    high REAL,
                    low REAL,
                    open REAL,
                    pre_close REAL,
                    turnover_rate REAL,
                    total_market_value REAL,
                    circulating_market_value REAL,
                    update_time TIMESTAMP,
                    PRIMARY KEY(code, trade_date)
                )
            '''))
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS fund_historical_quotes (
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(100),
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    pre_close REAL,
                    volume REAL,
                    amount REAL,
                    change_percent REAL,
                    change REAL,
                    amplitude REAL,
                    turnover_rate REAL,
                    collected_source VARCHAR(50),
                    collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(code, date)
                )
            '''))
            self.session.commit()
            logger.info("基金相关表初始化完成")
        except Exception as e:
            logger.warning(f"基金表初始化失败（可能已存在）: {e}")
            self.session.rollback()

    # ===================== ETF列表同步 =====================

    def sync_etf_list(self) -> Dict:
        """
        从 akshare 同步ETF基础信息列表

        Returns:
            Dict: 同步结果统计
        """
        try:
            logger.info("开始同步ETF基础信息列表...")
            # 使用 fund_etf_spot_em 获取当前所有ETF的基本行情（含名称和代码）
            df = ak.fund_etf_spot_em()

            if df is None or df.empty:
                logger.warning("未获取到ETF列表数据")
                return {'total': 0, 'inserted': 0, 'updated': 0, 'failed': 0}

            logger.info(f"从akshare获取到 {len(df)} 只ETF基金")

            inserted = 0
            updated = 0
            failed = 0

            for _, row in df.iterrows():
                try:
                    code = str(row.get('代码', '')).strip()
                    name = str(row.get('名称', '')).strip()

                    if not code or not name:
                        continue

                    self.session.execute(text('''
                        INSERT INTO fund_basic_info (code, name, fund_type, collect_enabled, created_at, updated_at)
                        VALUES (:code, :name, :fund_type, TRUE, :now, :now)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            updated_at = EXCLUDED.updated_at
                    '''), {
                        'code': code,
                        'name': name,
                        'fund_type': 'ETF',
                        'now': datetime.now()
                    })
                    inserted += 1

                except Exception as e:
                    logger.error(f"同步ETF {code} 失败: {e}")
                    failed += 1
                    continue

            self.session.commit()
            result = {
                'total': len(df),
                'inserted': inserted,
                'updated': updated,
                'failed': failed
            }
            logger.info(f"ETF列表同步完成: {result}")
            return result

        except Exception as e:
            logger.error(f"同步ETF列表失败: {e}")
            self.session.rollback()
            return {'total': 0, 'inserted': 0, 'updated': 0, 'failed': 1, 'error': str(e)}

    # ===================== 获取ETF列表 =====================

    def get_etf_list(self) -> List[Dict]:
        """从数据库获取ETF列表"""
        try:
            result = self.session.execute(text("""
                SELECT code, name
                FROM fund_basic_info
                WHERE COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
            """))
            funds = []
            for row in result.fetchall():
                funds.append({'code': row[0], 'name': row[1] if row[1] else ''})
            logger.info(f"从数据库获取到 {len(funds)} 只ETF基金")
            return funds
        except Exception as e:
            logger.error(f"获取ETF列表失败: {e}")
            return []

    # ===================== 历史行情采集 =====================

    def collect_single_etf_historical(self, etf_code: str, start_date: str, end_date: str) -> bool:
        """
        采集单只ETF的历史行情数据

        Args:
            etf_code: ETF代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            bool: 采集是否成功
        """
        try:
            # 检查已存在数据
            existing = self._check_existing_data(etf_code, start_date, end_date)

            # 获取ETF名称
            name_row = self.session.execute(
                text("SELECT name FROM fund_basic_info WHERE code = :code"),
                {"code": etf_code}
            ).fetchone()
            etf_name = (name_row[0] or '').strip() if name_row and name_row[0] else ''

            logger.info(f"开始采集ETF {etf_code} ({etf_name}) 的历史数据...")

            # 使用 fund_etf_hist_sina 作为主数据源（更稳定）
            max_retries = 5
            df = None
            for attempt in range(max_retries):
                try:
                    # fund_etf_hist_sina 需要加上交易所前缀
                    symbol = self._get_sina_symbol(etf_code)
                    df = ak.fund_etf_hist_sina(symbol=symbol)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"ETF {etf_code} 第 {attempt + 1} 次采集失败，{wait_time:.1f}秒后重试: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"ETF {etf_code} 采集最终失败: {e}")

            if df is None or df.empty:
                logger.warning(f"ETF {etf_code} 未获取到有效数据")
                return False

            logger.info(f"ETF {etf_code} 采集到 {len(df)} 条数据")

            # fund_etf_hist_sina 返回列: date, open, high, low, close, volume
            success_count = 0
            skip_count = 0

            for _, row in df.iterrows():
                try:
                    trade_date = pd.to_datetime(row['date']).strftime('%Y-%m-%d')

                    # 日期范围过滤
                    if trade_date < start_date or trade_date > end_date:
                        continue

                    # 已存在检查
                    if trade_date in existing:
                        skip_count += 1
                        continue

                    data = {
                        'code': etf_code,
                        'name': etf_name,
                        'date': trade_date,
                        'open': float(row['open']) if pd.notna(row['open']) else None,
                        'high': float(row['high']) if pd.notna(row['high']) else None,
                        'low': float(row['low']) if pd.notna(row['low']) else None,
                        'close': float(row['close']) if pd.notna(row['close']) else None,
                        'pre_close': None,
                        'volume': float(row['volume']) if pd.notna(row['volume']) else None,
                        'amount': None,
                        'change_percent': None,
                        'change': None,
                        'amplitude': None,
                        'turnover_rate': None,
                        'collected_source': 'akshare_sina',
                        'collected_date': datetime.now().isoformat()
                    }

                    self.session.execute(text("""
                        INSERT INTO fund_historical_quotes
                        (code, name, date, open, high, low, close, pre_close,
                         volume, amount, change_percent, change, amplitude,
                         turnover_rate, collected_source, collected_date)
                        VALUES (:code, :name, :date, :open, :high, :low, :close, :pre_close,
                                :volume, :amount, :change_percent, :change, :amplitude,
                                :turnover_rate, :collected_source, :collected_date)
                        ON CONFLICT (code, date) DO UPDATE SET
                            name = EXCLUDED.name,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            collected_source = EXCLUDED.collected_source,
                            collected_date = EXCLUDED.collected_date
                    """), data)
                    success_count += 1

                except Exception as e:
                    logger.error(f"处理ETF {etf_code} 日期 {trade_date} 数据时出错: {e}")
                    continue

            self.session.commit()
            self.collected_count += success_count
            self.skipped_count += skip_count

            logger.info(f"ETF {etf_code} 处理完成: 新增 {success_count} 条，跳过 {skip_count} 条")

            # 计算指标（仅新增数据时）
            if success_count > 0:
                self._calculate_all_indicators(etf_code, start_date, end_date)

            time.sleep(random.uniform(0.5, 1.5))
            return True

        except Exception as e:
            logger.error(f"采集ETF {etf_code} 历史数据失败: {e}")
            self.failed_count += 1
            self.failed_funds.append(f"{etf_code}: {str(e)}")
            self.session.rollback()
            return False

    def collect_historical_data(self, start_date: str, end_date: str,
                                 etf_codes: Optional[List[str]] = None) -> Dict:
        """
        批量采集ETF历史行情数据

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            etf_codes: 指定ETF代码列表，None则采集全部

        Returns:
            Dict: 采集结果统计
        """
        try:
            logger.info(f"开始批量采集ETF历史行情数据: {start_date} 到 {end_date}")

            if etf_codes:
                funds = []
                for code in etf_codes:
                    result = self.session.execute(
                        text("SELECT code, name FROM fund_basic_info WHERE code = :code"),
                        {'code': code}
                    )
                    row = result.fetchone()
                    if row:
                        funds.append({'code': row[0], 'name': row[1] if row[1] else ''})
                    else:
                        logger.warning(f"ETF代码 {code} 在fund_basic_info表中不存在")
            else:
                funds = self.get_etf_list()

            if not funds:
                logger.error("没有找到需要采集的ETF")
                return {'total': 0, 'success': 0, 'failed': 0, 'collected': 0, 'skipped': 0}

            logger.info(f"准备采集 {len(funds)} 只ETF的历史数据")

            # 重置计数器
            self.collected_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_funds = []

            success_count = 0
            for i, fund in enumerate(funds, 1):
                logger.info(f"进度: {i}/{len(funds)} - 采集ETF {fund['code']} ({fund['name']})")
                if self.collect_single_etf_historical(fund['code'], start_date, end_date):
                    success_count += 1
                if i % 10 == 0:
                    logger.info(f"已处理 {i}/{len(funds)} 只ETF，成功 {success_count} 只")

            result = {
                'total': len(funds),
                'success': success_count,
                'failed': self.failed_count,
                'collected': self.collected_count,
                'skipped': self.skipped_count,
                'failed_details': self.failed_funds
            }
            logger.info(f"ETF批量采集完成: {result}")
            return result

        except Exception as e:
            logger.error(f"ETF批量采集失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1, 'collected': 0, 'skipped': 0, 'error': str(e)}

    # ===================== 辅助方法 =====================

    def _get_sina_symbol(self, code: str) -> str:
        """根据ETF代码返回新浪接口需要的带交易所前缀的代码"""
        c = str(code).strip()
        if c.startswith(('5', '51')):
            return f'sh{c}'
        elif c.startswith(('1', '15', '16')):
            return f'sz{c}'
        # 默认按上海
        return f'sh{c}'

    def _check_existing_data(self, etf_code: str, start_date: str, end_date: str) -> set:
        """检查已存在的数据日期"""
        try:
            result = self.session.execute(text("""
                SELECT date FROM fund_historical_quotes
                WHERE code = :code AND date >= :start_date AND date <= :end_date
                ORDER BY date
            """), {'code': etf_code, 'start_date': start_date, 'end_date': end_date})
            return {str(row[0]) for row in result.fetchall()}
        except Exception as e:
            logger.error(f"检查ETF {etf_code} 已存在数据失败: {e}")
            return set()

    # ===================== 指标计算 =====================

    def _calculate_all_indicators(self, etf_code: str, start_date: str, end_date: str):
        """计算所有技术指标"""
        try:
            self._calculate_and_save_ma(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} MA指标计算失败: {e}")

        try:
            self._calculate_and_save_mavol(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} MAVOL指标计算失败: {e}")

        try:
            self._calculate_and_save_macd(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} MACD指标计算失败: {e}")

        try:
            self._calculate_and_save_kdj(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} KDJ指标计算失败: {e}")

        try:
            self._calculate_and_save_rsi(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} RSI指标计算失败: {e}")

        try:
            self._calculate_and_save_boll(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} BOLL指标计算失败: {e}")

        try:
            self._calculate_and_save_mean_frequency(etf_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"ETF {etf_code} 均值频率共振指标计算失败: {e}")

    def _load_historical_data(self, etf_code: str, start_date: str, end_date: str,
                               extra_days: int = 60):
        """从fund_historical_quotes加载历史数据用于指标计算"""
        query_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=extra_days)).strftime('%Y-%m-%d')
        result = self.session.execute(text("""
            SELECT date, open, high, low, close, volume
            FROM fund_historical_quotes
            WHERE code = :code AND date >= :start AND date <= :end
            AND close IS NOT NULL AND volume IS NOT NULL
            ORDER BY date ASC
        """), {'code': etf_code, 'start': query_start, 'end': end_date})
        return result.fetchall()

    def _calculate_and_save_macd(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存MACD指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date)
        if len(rows) < 26:
            return
        closes = [float(r[4]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = MACDCalculator()
        results = calculator.calculate_macd_batch(closes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'macd_indicators',
                                    ['dif', 'dea', 'macd', 'ema12', 'ema26'],
                                    lambda r: r['dif'] is not None)

    def _calculate_and_save_kdj(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存KDJ指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date)
        if len(rows) < 9:
            return
        highs = [float(r[2]) for r in rows]
        lows = [float(r[3]) for r in rows]
        closes = [float(r[4]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = KDJCalculator()
        results = calculator.calculate_kdj_batch(highs, lows, closes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'kdj_indicators',
                                    ['k', 'd', 'j', 'rsv'],
                                    lambda r: r['k'] is not None)

    def _calculate_and_save_rsi(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存RSI指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date)
        if len(rows) < 24:
            return
        closes = [float(r[4]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = RSICalculator()
        results = calculator.calculate_rsi_batch(closes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'rsi_indicators',
                                    ['rsi6', 'rsi12', 'rsi24'],
                                    lambda r: r.get('rsi6') is not None)

    def _calculate_and_save_ma(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存MA指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date, extra_days=250)
        if len(rows) < 5:
            return
        closes = [float(r[4]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = MACalculator()
        results = calculator.calculate_ma_batch(closes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'ma_indicators',
                                    ['ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120', 'ma200'],
                                    lambda r: r.get('ma5') is not None)

    def _calculate_and_save_boll(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存BOLL指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date)
        if len(rows) < 20:
            return
        closes = [float(r[4]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = BOLLCalculator()
        results = calculator.calculate_boll_batch(closes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'boll_indicators',
                                    ['mid', 'upper', 'lower'],
                                    lambda r: r.get('mid') is not None)

    def _calculate_and_save_mavol(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存MAVOL指标"""
        rows = self._load_historical_data(etf_code, start_date, end_date, extra_days=250)
        if len(rows) < 5:
            return
        volumes = [float(r[5]) for r in rows]
        dates = [r[0] for r in rows]
        calculator = MAVOLCalculator()
        results = calculator.calculate_mavol_batch(volumes)
        if not results:
            return
        self._save_indicator_batch(etf_code, dates, results, start_date, end_date,
                                    'mavol_indicators',
                                    ['mavol5', 'mavol10', 'mavol20', 'mavol30', 'mavol60', 'mavol120', 'mavol200'],
                                    lambda r: r.get('mavol5') is not None)

    def _calculate_and_save_mean_frequency(self, etf_code: str, start_date: str, end_date: str):
        """计算并保存均值频率共振指标（GMS核心指标）"""
        rows = self._load_historical_data(etf_code, start_date, end_date)
        if len(rows) < 21:
            return
        dates = [r[0] for r in rows]
        closes = [float(r[4]) for r in rows]
        volumes = [float(r[5]) for r in rows]

        calculator = MeanFrequencyResonanceCalculator()
        results = calculator.calculate(closes, volumes, dates=dates)
        if not results:
            return

        saved_count = 0
        start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

        for i, res in enumerate(results):
            if res is None:
                continue
            date_obj = dates[i] if isinstance(dates[i], datetime) else datetime.strptime(str(dates[i]), '%Y-%m-%d').date()
            if date_obj < start_obj or date_obj > end_obj:
                continue
            date_str = date_obj.strftime('%Y-%m-%d') if hasattr(date_obj, 'strftime') else str(date_obj)
            try:
                self.session.execute(text("""
                    INSERT INTO mean_frequency_resonance_indicators
                    (code, date, market_type, macro_displacement_delta, amplitude, ratio_d20, ratio_d1,
                     instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m,
                     ma20_d, mavol20_m, bias, d1, d1_date, d20, d20_date, created_at)
                    VALUES (:code, :date, :mt, :delta, :amplitude, :ratio_d20, :ratio_d1,
                            :instant_deviation, :z, :f, :efficiency,
                            :ma20, :mavol20, :bias, :d1, :d1_date, :d20, :d20_date, :created_at)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        macro_displacement_delta = EXCLUDED.macro_displacement_delta,
                        amplitude = EXCLUDED.amplitude,
                        ratio_d20 = EXCLUDED.ratio_d20,
                        ratio_d1 = EXCLUDED.ratio_d1,
                        instant_deviation = EXCLUDED.instant_deviation,
                        rising_days_z = EXCLUDED.rising_days_z,
                        falling_days_f = EXCLUDED.falling_days_f,
                        efficiency_m20_minus_m = EXCLUDED.efficiency_m20_minus_m,
                        ma20_d = EXCLUDED.ma20_d,
                        mavol20_m = EXCLUDED.mavol20_m,
                        bias = EXCLUDED.bias,
                        d1 = EXCLUDED.d1,
                        d1_date = EXCLUDED.d1_date,
                        d20 = EXCLUDED.d20,
                        d20_date = EXCLUDED.d20_date,
                        created_at = EXCLUDED.created_at
                """), {
                    'code': etf_code, 'date': date_str, 'mt': self.MARKET_TYPE,
                    'delta': res['macro_displacement_delta'],
                    'amplitude': res.get('amplitude'),
                    'ratio_d20': res.get('ratio_d20'),
                    'ratio_d1': res.get('ratio_d1'),
                    'instant_deviation': res['instant_deviation'],
                    'z': res['rising_days_z'], 'f': res['falling_days_f'],
                    'efficiency': res['efficiency_m20_minus_m'],
                    'ma20': res['ma20_d'], 'mavol20': res['mavol20_m'],
                    'bias': res['bias'],
                    'd1': res.get('d1'), 'd1_date': res.get('d1_date'),
                    'd20': res.get('d20'), 'd20_date': res.get('d20_date'),
                    'created_at': datetime.now()
                })
                saved_count += 1
            except Exception as e:
                logger.error(f"保存ETF {etf_code} 日期 {date_str} 均值频率共振失败: {e}")
                continue

        if saved_count > 0:
            self.session.commit()
            logger.debug(f"ETF {etf_code} 均值频率共振指标完成，保存 {saved_count} 条")

    def _save_indicator_batch(self, code, dates, results, start_date, end_date,
                               table_name, columns, valid_check):
        """通用指标保存方法"""
        saved = 0
        start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

        for i, res in enumerate(results):
            if not valid_check(res):
                continue
            date_obj = dates[i] if isinstance(dates[i], datetime) else datetime.strptime(str(dates[i]), '%Y-%m-%d').date()
            if date_obj < start_obj or date_obj > end_obj:
                continue
            date_str = date_obj.strftime('%Y-%m-%d') if hasattr(date_obj, 'strftime') else str(date_obj)

            cols_str = ', '.join(columns)
            vals_str = ', '.join([f':{c}' for c in columns])
            update_str = ', '.join([f'{c} = EXCLUDED.{c}' for c in columns])

            params = {
                'code': code,
                'date': date_str,
                'market_type': self.MARKET_TYPE,
                'created_at': datetime.now()
            }
            for c in columns:
                params[c] = res.get(c)

            try:
                self.session.execute(text(f"""
                    INSERT INTO {table_name}
                    (code, date, market_type, {cols_str}, created_at)
                    VALUES (:code, :date, :market_type, {vals_str}, :created_at)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        {update_str}, created_at = EXCLUDED.created_at
                """), params)
                saved += 1
            except Exception as e:
                logger.error(f"保存{table_name} {code}/{date_str} 失败: {e}")
                continue

        if saved > 0:
            self.session.commit()
            logger.debug(f"ETF {code} {table_name} 保存 {saved} 条")


# ===================== 命令行入口 =====================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='ETF基金数据采集器')
    parser.add_argument('--action', choices=['sync_list', 'collect'], default='collect',
                        help='操作类型：sync_list=同步列表, collect=采集行情')
    parser.add_argument('--start_date', default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                        help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end_date', default=datetime.now().strftime('%Y-%m-%d'),
                        help='结束日期 YYYY-MM-DD')
    parser.add_argument('--codes', nargs='*', help='指定ETF代码列表')
    args = parser.parse_args()

    collector = ETFCollector()

    if args.action == 'sync_list':
        result = collector.sync_etf_list()
        print(f"ETF列表同步结果: {result}")
    elif args.action == 'collect':
        result = collector.collect_historical_data(args.start_date, args.end_date, args.codes)
        print(f"ETF行情采集结果: {result}")
