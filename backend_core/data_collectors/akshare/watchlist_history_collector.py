import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak
from sqlalchemy.orm import Session
from sqlalchemy import exists, text
from backend_core.database.db import get_db

# 假设有自选股表 watchlist，字段 code
from backend_core.models.watchlist import Watchlist  # 需根据实际路径调整
from backend_core.models.historical_quotes import HistoricalQuotes  # 需根据实际路径调整
from backend_core.models.watchlist_history_collection_logs import WatchlistHistoryCollectionLogs  # 需根据实际路径调整

# 指标计算器（采集后计算 MA、MACD、RSI、KDJ、BOLL、MAVOL、PVFRS）
try:
    from backend_core.utils.ma_calculator import MACalculator
    from backend_core.utils.macd_calculator import MACDCalculator
    from backend_core.utils.kdj_calculator import KDJCalculator
    from backend_core.utils.rsi_calculator import RSICalculator
    from backend_core.utils.boll_calculator import BOLLCalculator
    from backend_core.utils.mavol_calculator import MAVOLCalculator
    from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
    _INDICATORS_AVAILABLE = True
except Exception as e:
    logging.getLogger(__name__).warning("指标计算器导入失败，采集后将不计算指标: %s", e)
    _INDICATORS_AVAILABLE = False

# 配置日志
logger = logging.getLogger(__name__)

def get_watchlist_codes(db: Session):
    """获取自选股股票代码列表，去重。"""
    codes = db.query(Watchlist.stock_code).distinct().all()
    return [c[0] for c in codes]

def has_collected(db: Session, stock_code: str) -> bool:
    """判断该股票是否已采集过历史数据。"""
    return db.query(
        exists().where(
            (WatchlistHistoryCollectionLogs.stock_code == stock_code) &
            (WatchlistHistoryCollectionLogs.status == 'success')
        )
    ).scalar()

def is_hk_stock(db: Session, stock_code: str) -> bool:
    """
    判断股票代码是否为港股。
    优先通过查询 stock_basic_info_hk 表判断，如果表中没有记录，则通过代码格式判断。
    港股代码特征：5位数字，以0开头（如 00700, 00111）
    """
    if not stock_code:
        return False
    
    code_str = str(stock_code).strip()
    logger.info(f"[is_hk_stock] 检查股票代码: {code_str}, 长度: {len(code_str)}")
    
    # 方法1：查询 stock_basic_info_hk 表
    try:
        result = db.execute(
            text("SELECT 1 FROM stock_basic_info_hk WHERE code = :code LIMIT 1"),
            {"code": code_str}
        ).fetchone()
        if result is not None:
            logger.info(f"[is_hk_stock] 通过 stock_basic_info_hk 表判断 {code_str} 为港股")
            return True
    except Exception as e:
        logger.warning(f"[is_hk_stock] 查询 stock_basic_info_hk 表时出错: {e}")
    
    
    logger.debug(f"[is_hk_stock] {code_str} 不是港股")
    return False

def normalize_stock_code(stock_code: str) -> str:
    """
    清理和规范化股票代码格式。
    去除空格、点号后缀等，确保代码格式正确。
    
    Args:
        stock_code: 原始股票代码
        
    Returns:
        str: 清理后的股票代码
    """
    if not stock_code:
        return stock_code
    
    code = str(stock_code).strip()
    # 如果包含点号（如 000001.SZ），只取点号前的部分
    if '.' in code:
        code = code.split('.')[0]
    return code

def get_market_from_db(db: Session, stock_code: str) -> str:
    """
    从stock_basic_info表中获取股票的market值。
    
    Args:
        db: 数据库会话
        stock_code: 股票代码
        
    Returns:
        str: market值（如 'SZ' 或 'SH'），如果未找到则返回空字符串
    """
    try:
        result = db.execute(
            text("SELECT market FROM stock_basic_info WHERE code = :code LIMIT 1"),
            {"code": stock_code}
        ).fetchone()
        if result and result[0]:
            return str(result[0]).strip()
    except Exception as e:
        logger.warning(f"[get_market_from_db] 查询股票 {stock_code} 的market值失败: {e}")
    return ""

def build_sina_symbol(stock_code: str, market: str) -> str:
    """
    构建新浪接口需要的symbol参数格式。
    格式：小写市场标识 + 股票代码，如 "sz000001" 或 "sh600000"
    
    Args:
        stock_code: 股票代码（如 "000001"）
        market: 市场标识（如 "SZ" 或 "SH"）
        
    Returns:
        str: 新浪接口的symbol参数（如 "sz000001"）
    """
    if not market:
        return ""
    
    # 将市场标识转换为小写
    market_lower = market.lower()
    # 组合成新浪接口格式
    return f"{market_lower}{stock_code}"

def log_collection(db: Session, stock_code: str, affected_rows: int, status: str, error_message: str = None):
    """写入采集日志。"""
    log = WatchlistHistoryCollectionLogs(
        stock_code=stock_code,
        affected_rows=affected_rows,
        status=status,
        error_message=error_message,
        created_at=datetime.now()
    )
    db.add(log)
    db.commit()

def insert_historical_quotes(db: Session, stock_code: str, df):
    """批量插入历史行情数据，避免重复插入。"""
    rows = []
    # 根据code从watchlist表获取股票名称
    stock_name = None
    try:
        # 可能存在多个自选记录，这里只取第一条名称，避免 MultipleResultsFound 异常
        result = db.query(Watchlist.stock_name).filter(Watchlist.stock_code == stock_code).first()
        if result is not None:
            stock_name = str(result[0])
    except Exception as e:
        logger.warning(f"获取股票 {stock_code} 名称失败: {e}")
    logger.debug(f"股票代码 {stock_code} 的名称: {stock_name}")

    for _, row in df.iterrows():
        hq = HistoricalQuotes(
            code=stock_code,
            name=stock_name,
            date=row.get('日期'),
            open=row.get('开盘'),
            close=row.get('收盘'),
            high=row.get('最高'),
            low=row.get('最低'),
            volume=row.get('成交量'),
            amount=row.get('成交额'),
            amplitude=row.get('振幅'),
            change_percent=row.get('涨跌幅'),
            change=row.get('涨跌额'),
            turnover_rate=row.get('换手率')
            #adjust='qfq'
        )
        rows.append(hq)
    if rows:
        # 执行upsert操作，避免重复插入
        # 这里只能用原生SQL或SQLAlchemy的merge/on_conflict等方式，以下为通用实现（以PostgreSQL为例，其他数据库需调整语法）
        from sqlalchemy.dialects.postgresql import insert

        for hq in rows:
            stmt = insert(HistoricalQuotes).values(
                code=hq.code,
                name=hq.name,    # 新增股票名称字段      
                date=hq.date,
                open=hq.open,
                close=hq.close,
                high=hq.high,
                low=hq.low,
                volume=hq.volume,
                amount=hq.amount,
                amplitude=hq.amplitude,
                change_percent=hq.change_percent,
                change=hq.change,
                turnover_rate=hq.turnover_rate
                #adjust=hq.adjust
            ).on_conflict_do_update(
                index_elements=['code', 'date'],
                set_={
                    'name': hq.name,
                    'open': hq.open,
                    'close': hq.close,
                    'high': hq.high,
                    'low': hq.low,
                    'volume': hq.volume,
                    'amount': hq.amount,
                    'amplitude': hq.amplitude,
                    'change_percent': hq.change_percent,
                    'change': hq.change,
                    'turnover_rate': hq.turnover_rate
                    #'adjust': hq.adjust
                }
            )
            db.execute(stmt)
        db.commit()
    return len(rows)

def insert_historical_quotes_hk(db: Session, stock_code: str, df):
    """批量插入港股历史行情数据，避免重复插入。"""
    rows = []
    # 根据code从watchlist表获取股票名称
    stock_name = None
    try:
        # 可能存在多个自选记录，这里只取第一条名称，避免 MultipleResultsFound 异常
        result = db.query(Watchlist.stock_name).filter(Watchlist.stock_code == stock_code).first()
        if result is not None:
            stock_name = str(result[0])
    except Exception as e:
        logger.warning(f"获取港股 {stock_code} 名称失败: {e}")
    logger.debug(f"港股代码 {stock_code} 的名称: {stock_name}")

    for _, row in df.iterrows():
        # 处理日期格式：从 YYYYMMDD 转换为 YYYY-MM-DD
        date_str = str(row.get('日期', ''))
        if len(date_str) == 8 and date_str.isdigit():
            date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
            date_formatted = date_str
        
        # 港股数据字段映射；历史行情表成交量按「手」存，ak.stock_hk_hist 成交量为股，÷100 转为手
        vol_raw = row.get('成交量') if '成交量' in row.index else None
        vol_val = None
        if vol_raw is not None and not (isinstance(vol_raw, float) and pd.isna(vol_raw)):
            try:
                vol_val = float(vol_raw) / 100
            except (TypeError, ValueError):
                vol_val = None
        row_data = {
            'code': stock_code,
            'name': stock_name,
            'date': date_formatted,
            'open': row.get('开盘') if '开盘' in row.index else None,
            'close': row.get('收盘') if '收盘' in row.index else None,
            'high': row.get('最高') if '最高' in row.index else None,
            'low': row.get('最低') if '最低' in row.index else None,
            'pre_close': row.get('昨收') if '昨收' in row.index else None,
            'volume': vol_val,
            'amount': row.get('成交额') if '成交额' in row.index else None,
            'amplitude': row.get('振幅') if '振幅' in row.index else None,
            'change_percent': row.get('涨跌幅') if '涨跌幅' in row.index else None,
            'change_amount': row.get('涨跌额') if '涨跌额' in row.index else None,
            'turnover_rate': row.get('换手率') if '换手率' in row.index else None,
        }
        rows.append(row_data)
    
    if rows:
        # 使用 PostgreSQL 的 ON CONFLICT DO UPDATE 进行 upsert
        for row_data in rows:
            stmt = text("""
                INSERT INTO historical_quotes_hk (
                    code, name, date, open, close, high, low, pre_close,
                    volume, amount, amplitude, change_percent, change_amount, turnover_rate
                ) VALUES (
                    :code, :name, :date, :open, :close, :high, :low, :pre_close,
                    :volume, :amount, :amplitude, :change_percent, :change_amount, :turnover_rate
                )
                ON CONFLICT (code, date) DO UPDATE SET
                    name = EXCLUDED.name,
                    open = EXCLUDED.open,
                    close = EXCLUDED.close,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    pre_close = EXCLUDED.pre_close,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    amplitude = EXCLUDED.amplitude,
                    change_percent = EXCLUDED.change_percent,
                    change_amount = EXCLUDED.change_amount,
                    turnover_rate = EXCLUDED.turnover_rate
            """)
            db.execute(stmt, row_data)
        db.commit()
    return len(rows)


def _norm_date(d) -> str:
    """将日期规范为 YYYY-MM-DD 字符串。"""
    if d is None or (isinstance(d, float) and pd.isna(d)):
        return None
    if isinstance(d, str):
        if len(d) == 8 and d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return d[:10] if len(d) >= 10 else d
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    return str(d)[:10]


def _get_date_range_from_df(df, date_col='日期'):
    """从采集用的 DataFrame 得到本次写入的日期范围 (start_date, end_date)，均为 YYYY-MM-DD。"""
    if df is None or df.empty or date_col not in df.columns:
        return None, None
    s = df[date_col]
    min_d = s.min()
    max_d = s.max()
    return _norm_date(min_d), _norm_date(max_d)


def _safe_float(val):
    """安全转为 float，无效则返回 None。"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _calculate_indicators_after_collect(db: Session, stock_code: str, market_type: str, start_date: str, end_date: str):
    """
    在历史行情写入后，对该股票在 [start_date, end_date] 范围内计算并写入
    MA、MACD、RSI、KDJ、BOLL、MAVOL、PVFRS 指标。market_type 为 'CN' 或 'HK'。
    单只股票指标失败只打日志，不抛异常。
    """
    if not _INDICATORS_AVAILABLE or not start_date or not end_date:
        return
    table = "historical_quotes" if market_type == 'CN' else "historical_quotes_hk"
    try:
        result = db.execute(text(f"""
            SELECT date, close, high, low, volume
            FROM {table}
            WHERE code = :code AND date <= :end_date
            AND close IS NOT NULL
            ORDER BY date ASC
        """), {'code': stock_code, 'end_date': end_date})
        rows = result.fetchall()
    except Exception as e:
        logger.warning("自选股指标计算：查询历史行情失败 %s %s: %s", stock_code, market_type, e)
        return
    if not rows:
        return
    dates = [str(r[0])[:10] for r in rows]
    closes = [float(r[1]) for r in rows]
    highs = [float(r[2]) if r[2] is not None else float(r[1]) for r in rows]
    lows = [float(r[3]) if r[3] is not None else float(r[1]) for r in rows]
    volumes = [float(r[4]) if r[4] is not None else 0.0 for r in rows]
    now = datetime.now()
    in_range = lambda d: start_date <= d <= end_date

    # MA
    try:
        ma_batch = MACalculator.calculate_ma_batch(closes, periods=[5, 10, 20, 30, 60, 120, 200])
        for i, ma_data in enumerate(ma_batch):
            if i >= len(dates) or not in_range(dates[i]):
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO ma_indicators
                (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200, created_at)
                VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    ma5 = EXCLUDED.ma5, ma10 = EXCLUDED.ma10, ma20 = EXCLUDED.ma20, ma30 = EXCLUDED.ma30,
                    ma60 = EXCLUDED.ma60, ma120 = EXCLUDED.ma120, ma200 = EXCLUDED.ma200, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'ma5': _safe_float(ma_data.get('ma5')), 'ma10': _safe_float(ma_data.get('ma10')),
                'ma20': _safe_float(ma_data.get('ma20')), 'ma30': _safe_float(ma_data.get('ma30')),
                'ma60': _safe_float(ma_data.get('ma60')), 'ma120': _safe_float(ma_data.get('ma120')),
                'ma200': _safe_float(ma_data.get('ma200')), 'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 MA %s %s: %s", stock_code, market_type, e)

    # MACD
    try:
        macd_calc = MACDCalculator()
        macd_batch = macd_calc.calculate_macd_batch(closes)
        for i, macd_data in enumerate(macd_batch):
            if i >= len(dates) or not in_range(dates[i]) or macd_data.get('dif') is None:
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO macd_indicators
                (code, date, market_type, dif, dea, macd, ema12, ema26, created_at)
                VALUES (:code, :date, :market_type, :dif, :dea, :macd, :ema12, :ema26, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    dif = EXCLUDED.dif, dea = EXCLUDED.dea, macd = EXCLUDED.macd,
                    ema12 = EXCLUDED.ema12, ema26 = EXCLUDED.ema26, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'dif': macd_data.get('dif'), 'dea': macd_data.get('dea'), 'macd': macd_data.get('macd'),
                'ema12': macd_data.get('ema12'), 'ema26': macd_data.get('ema26'), 'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 MACD %s %s: %s", stock_code, market_type, e)

    # RSI
    try:
        rsi_calc = RSICalculator([6, 12, 24])
        rsi_batch = rsi_calc.calculate_rsi_batch(closes)
        for i, rsi_data in enumerate(rsi_batch):
            if i >= len(dates) or not in_range(dates[i]):
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO rsi_indicators
                (code, date, market_type, rsi6, rsi12, rsi24, created_at)
                VALUES (:code, :date, :market_type, :rsi6, :rsi12, :rsi24, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    rsi6 = EXCLUDED.rsi6, rsi12 = EXCLUDED.rsi12, rsi24 = EXCLUDED.rsi24, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'rsi6': _safe_float(rsi_data.get('rsi6')), 'rsi12': _safe_float(rsi_data.get('rsi12')),
                'rsi24': _safe_float(rsi_data.get('rsi24')), 'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 RSI %s %s: %s", stock_code, market_type, e)

    # KDJ (calculate_kdj_batch(closes, highs, lows))
    try:
        kdj_calc = KDJCalculator()
        kdj_batch = kdj_calc.calculate_kdj_batch(closes, highs, lows)
        for i, kdj_data in enumerate(kdj_batch):
            if i >= len(dates) or not in_range(dates[i]) or kdj_data.get('k') is None:
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO kdj_indicators
                (code, date, market_type, k, d, j, rsv, created_at)
                VALUES (:code, :date, :market_type, :k, :d, :j, :rsv, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    k = EXCLUDED.k, d = EXCLUDED.d, j = EXCLUDED.j, rsv = EXCLUDED.rsv, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'k': kdj_data.get('k'), 'd': kdj_data.get('d'), 'j': kdj_data.get('j'), 'rsv': kdj_data.get('rsv'),
                'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 KDJ %s %s: %s", stock_code, market_type, e)

    # BOLL
    try:
        boll_calc = BOLLCalculator(20, 2)
        boll_batch = boll_calc.calculate_boll_batch(closes)
        for i, boll_data in enumerate(boll_batch):
            if i >= len(dates) or not in_range(dates[i]) or boll_data.get('mid') is None:
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO boll_indicators (code, date, market_type, mid, upper, lower, created_at)
                VALUES (:code, :date, :market_type, :mid, :upper, :lower, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    mid = EXCLUDED.mid, upper = EXCLUDED.upper, lower = EXCLUDED.lower, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'mid': boll_data.get('mid'), 'upper': boll_data.get('upper'), 'lower': boll_data.get('lower'),
                'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 BOLL %s %s: %s", stock_code, market_type, e)

    # MAVOL
    try:
        df_vol = pd.DataFrame({'date': dates, 'volume': volumes})
        df_vol['date'] = pd.to_datetime(df_vol['date'])
        mavol_df = MAVOLCalculator.calculate_mavol_for_dataframe(df_vol, periods=[5, 10, 20, 30, 60, 120, 200])
        for _, row in mavol_df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
            if not in_range(date_str):
                continue
            db.execute(text("""
                INSERT INTO mavol_indicators
                (code, date, market_type, mavol5, mavol10, mavol20, mavol30, mavol60, mavol120, mavol200, created_at)
                VALUES (:code, :date, :market_type, :mavol5, :mavol10, :mavol20, :mavol30, :mavol60, :mavol120, :mavol200, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    mavol5 = EXCLUDED.mavol5, mavol10 = EXCLUDED.mavol10, mavol20 = EXCLUDED.mavol20, mavol30 = EXCLUDED.mavol30,
                    mavol60 = EXCLUDED.mavol60, mavol120 = EXCLUDED.mavol120, mavol200 = EXCLUDED.mavol200, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'mavol5': _safe_float(row.get('mavol5')), 'mavol10': _safe_float(row.get('mavol10')),
                'mavol20': _safe_float(row.get('mavol20')), 'mavol30': _safe_float(row.get('mavol30')),
                'mavol60': _safe_float(row.get('mavol60')), 'mavol120': _safe_float(row.get('mavol120')),
                'mavol200': _safe_float(row.get('mavol200')), 'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 MAVOL %s %s: %s", stock_code, market_type, e)

    # PVFRS (mean_frequency_resonance_indicators)
    try:
        pvfrs_calc = MeanFrequencyResonanceCalculator()
        pvfrs_results = pvfrs_calc.calculate(closes, volumes, dates=dates, window=20)
        from backend_core.strategies.gms.ma60_source import lookup_ma60_d

        for i, res in enumerate(pvfrs_results):
            if res is None or i >= len(dates) or not in_range(dates[i]):
                continue
            date_str = dates[i]
            db.execute(text("""
                INSERT INTO mean_frequency_resonance_indicators
                (code, date, market_type, macro_displacement_delta, amplitude, ratio_d20, ratio_d1, instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m, ma20_d, ma60_d, mavol20_m, bias, created_at)
                VALUES (:code, :date, :market_type, :delta, :amplitude, :ratio_d20, :ratio_d1, :instant_deviation, :z, :f, :efficiency, :ma20, :ma60_d, :mavol20, :bias, :created_at)
                ON CONFLICT (code, date, market_type) DO UPDATE SET
                    macro_displacement_delta = EXCLUDED.macro_displacement_delta, amplitude = EXCLUDED.amplitude,
                    ratio_d20 = EXCLUDED.ratio_d20, ratio_d1 = EXCLUDED.ratio_d1, instant_deviation = EXCLUDED.instant_deviation,
                    rising_days_z = EXCLUDED.rising_days_z, falling_days_f = EXCLUDED.falling_days_f,
                    efficiency_m20_minus_m = EXCLUDED.efficiency_m20_minus_m, ma20_d = EXCLUDED.ma20_d,
                    ma60_d = EXCLUDED.ma60_d, mavol20_m = EXCLUDED.mavol20_m,
                    bias = EXCLUDED.bias, created_at = EXCLUDED.created_at
            """), {
                'code': stock_code, 'date': date_str, 'market_type': market_type,
                'delta': res.get('macro_displacement_delta'), 'amplitude': res.get('amplitude'),
                'ratio_d20': res.get('ratio_d20'), 'ratio_d1': res.get('ratio_d1'),
                'instant_deviation': res.get('instant_deviation'), 'z': res.get('rising_days_z'),
                'f': res.get('falling_days_f'), 'efficiency': res.get('efficiency_m20_minus_m'),
                'ma20': res.get('ma20_d'), 'ma60_d': lookup_ma60_d(db, stock_code, date_str, market_type),
                'mavol20': res.get('mavol20_m'), 'bias': res.get('bias'),
                'created_at': now
            })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("自选股指标计算 PVFRS %s %s: %s", stock_code, market_type, e)

    logger.info("自选股 %s %s 指标计算完成 [%s ~ %s]", stock_code, market_type, start_date, end_date)


def collect_one_stock_history_and_indicators(db: Session, stock_code: str):
    """
    对单只自选股采集历史行情并计算 MA、MACD、RSI、KDJ、BOLL、MAVOL、PVFRS 指标。
    用于添加自选股成功后由前端触发的即时采集与指标计算。
    不检查 has_collected，每次均拉取并覆盖该 code 的行情与指标。

    Returns:
        dict: {"success": bool, "message": str}
    """
    stock_code = normalize_stock_code(stock_code)
    if not stock_code:
        return {"success": False, "message": "股票代码为空"}
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    try:
        is_hk = is_hk_stock(db, stock_code)
        if is_hk:
            hk_code = stock_code.zfill(5) if stock_code.isdigit() else stock_code
            df = ak.stock_hk_hist(symbol=hk_code, period='daily', start_date='19950101', end_date=end_date, adjust='')
            if df.empty:
                return {"success": False, "message": "港股返回空数据"}
            db.execute(text("DELETE FROM historical_quotes_hk WHERE code = :code"), {"code": stock_code})
            db.commit()
            affected = insert_historical_quotes_hk(db, stock_code, df)
            log_collection(db, stock_code, affected, 'success')
            start_d, end_d = _get_date_range_from_df(df)
            if start_d and end_d:
                _calculate_indicators_after_collect(db, stock_code, 'HK', start_d, end_d)
            return {"success": True, "message": f"港股 {stock_code} 历史行情与指标已更新"}
        else:
            a_code = stock_code.zfill(6) if stock_code.isdigit() and len(stock_code) < 6 else stock_code
            df = None
            try:
                df = ak.stock_zh_a_hist(symbol=a_code, period='daily', start_date='19950101', end_date=end_date, adjust='')
            except Exception as e1:
                market = get_market_from_db(db, stock_code)
                if not market:
                    market = 'SZ' if (stock_code.startswith('0') or stock_code.startswith('3')) else 'SH'
                sina_symbol = build_sina_symbol(a_code, market)
                if not sina_symbol:
                    return {"success": False, "message": f"无法构建新浪 symbol: {e1}"}
                df = ak.stock_zh_a_hist(symbol=sina_symbol, period='daily', start_date='19950101', end_date=end_date, adjust='')
            if df is None or df.empty:
                return {"success": False, "message": "A股返回空数据"}
            db.query(HistoricalQuotes).filter(HistoricalQuotes.code == stock_code).delete()
            db.commit()
            affected = insert_historical_quotes(db, stock_code, df)
            log_collection(db, stock_code, affected, 'success')
            start_d, end_d = _get_date_range_from_df(df)
            if start_d and end_d:
                _calculate_indicators_after_collect(db, stock_code, 'CN', start_d, end_d)
            return {"success": True, "message": f"A股 {stock_code} 历史行情与指标已更新"}
    except Exception as e:
        db.rollback()
        logger.exception("单股采集与指标计算失败 %s: %s", stock_code, e)
        try:
            log_collection(db, stock_code, 0, 'fail', str(e))
        except Exception:
            pass
        return {"success": False, "message": str(e)}


def collect_watchlist_history():
    """
    自选股历史行情采集主函数。
    返回采集成功的股票数量和失败的股票数量。
    支持A股和港股。
    """
    db = next(get_db())
    codes = get_watchlist_codes(db)
    success_count = 0
    fail_count = 0
    for stock_code in set(codes):
        # 清理和规范化股票代码格式
        stock_code = normalize_stock_code(stock_code)
        
        if not stock_code:
            logger.warning(f"[collect_watchlist_history] 股票代码为空，跳过")
            continue
            
        if has_collected(db, stock_code):
            #logger.info(f"[collect_watchlist_history] 股票 {stock_code} 已采集过，跳过")
            continue
        try:
            end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            
            # 判断是否为港股
            logger.info(f"[collect_watchlist_history] 开始判断股票 {stock_code} 是否为港股")
            is_hk = is_hk_stock(db, stock_code)
            logger.info(f"[collect_watchlist_history] 股票 {stock_code} 判断结果: {'港股' if is_hk else 'A股'}")
            
            if is_hk:
                # 港股处理逻辑
                logger.info(f"[collect_watchlist_history] 检测到港股代码: {stock_code}")
                # 确保港股代码格式正确（5位数字）
                hk_code = stock_code.zfill(5) if stock_code.isdigit() else stock_code
                df = ak.stock_hk_hist(symbol=hk_code, period='daily', start_date='19950101', end_date=end_date, adjust='')
                
                # 检查返回的DataFrame是否为空
                if df.empty:
                    logger.warning(f"港股 {stock_code} 返回空数据，可能该股票已退市或代码无效")
                    log_collection(db, stock_code, 0, 'fail', '返回空数据，可能该股票已退市或代码无效')
                    fail_count += 1
                    continue
                
                # 批量插入前，先删除该stock_code在港股历史行情表中的旧数据
                db.execute(
                    text("DELETE FROM historical_quotes_hk WHERE code = :code"),
                    {"code": stock_code}
                )
                db.commit()
                
                affected_rows = insert_historical_quotes_hk(db, stock_code, df)
                log_collection(db, stock_code, affected_rows, 'success')
                success_count += 1
                try:
                    start_d, end_d = _get_date_range_from_df(df)
                    if start_d and end_d:
                        _calculate_indicators_after_collect(db, stock_code, 'HK', start_d, end_d)
                except Exception as ind_err:
                    logger.warning("港股 %s 采集后指标计算失败: %s", stock_code, ind_err)
            else:
                # A股处理逻辑
                logger.info(f"[collect_watchlist_history] 开始采集A股 {stock_code} 的历史数据")
                # 确保A股代码格式正确（6位数字）
                a_code = stock_code.zfill(6) if stock_code.isdigit() and len(stock_code) < 6 else stock_code
                df = None
                
                # 先尝试调用 stock_zh_a_hist（东方财富接口）
                try:
                    df = ak.stock_zh_a_hist(symbol=a_code, period='daily', start_date='19950101', end_date=end_date, adjust='')
                    logger.info(f"[collect_watchlist_history] 成功使用 stock_zh_a_hist 接口获取A股 {stock_code} 的历史数据")
                except Exception as e1:
                    logger.warning(f"[collect_watchlist_history] 调用 stock_zh_a_hist 失败，尝试使用新浪接口，错误详情: {e1}")
                    
                    # 如果 stock_zh_a_hist 失败，尝试调用新浪接口
                    try:
                        # 从stock_basic_info表获取market值
                        market = get_market_from_db(db, stock_code)
                        if not market:
                            # 如果表中没有market值，尝试根据股票代码推断
                            if stock_code.startswith('0') or stock_code.startswith('3'):
                                market = 'SZ'
                            else:
                                market = 'SH'
                            logger.info(f"[collect_watchlist_history] 未在stock_basic_info表中找到market值，根据代码推断为: {market}")
                        
                        # 构建新浪接口需要的symbol参数（格式：sz000001 或 sh600000）
                        sina_symbol = build_sina_symbol(a_code, market)
                        if not sina_symbol:
                            raise ValueError(f"无法构建新浪接口的symbol参数，stock_code: {stock_code}, market: {market}")
                        
                        logger.info(f"[collect_watchlist_history] 使用新浪接口，symbol: {sina_symbol}")
                        # 调用新浪接口
                        # 注意：新浪接口的symbol参数格式为 "sz000001" 或 "sh600000"（小写市场标识+股票代码）
                        # stock_zh_a_hist 接口支持这种格式作为备用数据源
                        df = ak.stock_zh_a_hist(symbol=sina_symbol, period='daily', start_date='19950101', end_date=end_date, adjust='')
                        logger.info(f"[collect_watchlist_history] 成功使用新浪接口获取A股 {stock_code} 的历史数据")
                    except Exception as e2:
                        logger.error(f"[collect_watchlist_history] 调用新浪接口也失败: {e2}")
                        raise Exception(f"stock_zh_a_hist和新浪接口都失败: stock_zh_a_hist错误={e1}, 新浪接口错误={e2}")
                
                # 检查返回的DataFrame是否为空
                if df is None or df.empty:
                    logger.warning(f"A股 {stock_code} 返回空数据，可能该股票已退市或代码无效")
                    log_collection(db, stock_code, 0, 'fail', '返回空数据，可能该股票已退市或代码无效')
                    fail_count += 1
                    continue
                
                # 批量插入前，先删除该stock_code的历史数据
                db.query(HistoricalQuotes).filter(HistoricalQuotes.code == stock_code).delete()
                db.commit()
                affected_rows = insert_historical_quotes(db, stock_code, df)
                log_collection(db, stock_code, affected_rows, 'success')
                success_count += 1
                try:
                    start_d, end_d = _get_date_range_from_df(df)
                    if start_d and end_d:
                        _calculate_indicators_after_collect(db, stock_code, 'CN', start_d, end_d)
                except Exception as ind_err:
                    logger.warning("A股 %s 采集后指标计算失败: %s", stock_code, ind_err)
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            logger.error(f"[collect_watchlist_history] 采集股票 {stock_code} 失败: {error_msg}", exc_info=True)
            try:
                log_collection(db, stock_code, 0, 'fail', error_msg)
            except Exception as log_error:
                logger.error(f"记录采集失败日志时出错: {log_error}")
            fail_count += 1
            print(f"[collect_watchlist_history] 采集 {stock_code} 失败: {error_msg}")
        time.sleep(10)
    return {"success": success_count, "fail": fail_count}
