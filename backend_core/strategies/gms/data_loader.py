"""
GMS 数据加载器
从 mean_frequency_resonance_indicators 表加载指标，并计算 Δ/d、量比
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GMSDataLoader:
    """从 mean_frequency_resonance_indicators 加载 GMS 所需指标"""

    def __init__(self, db: Session):
        self.db = db

    def load_indicators(
        self,
        codes: List[str],
        date: str,
        market_type: str = "CN",
        use_latest_per_stock: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        批量加载指定日期、市场的指标数据。

        Args:
            codes: 股票代码列表
            date: 目标日期 (YYYY-MM-DD)
            market_type: CN 或 HK
            use_latest_per_stock: 若为 True，当某股票在目标日无数据时，使用该股票
                date <= date 的最近一天的数据（历史行情表中无当天数据时以最近一天为筛选条件）

        Returns:
            每只股票的指标字典列表，包含表字段及衍生的 ratio_d、volume_ratio
        """
        if not codes:
            return []

        try:
            from sqlalchemy import desc
            from backend_api.models import MeanFrequencyResonanceIndicators

            date_str = str(date).strip()[:10]
            if use_latest_per_stock:
                # 每只股票取 date <= date_str 的最近一条记录（无当天数据则用最近可用日）
                query = (
                    self.db.query(MeanFrequencyResonanceIndicators)
                    .filter(
                        MeanFrequencyResonanceIndicators.code.in_(codes),
                        MeanFrequencyResonanceIndicators.date <= date_str,
                        MeanFrequencyResonanceIndicators.market_type == market_type,
                    )
                    .order_by(
                        MeanFrequencyResonanceIndicators.code,
                        desc(MeanFrequencyResonanceIndicators.date),
                    )
                )
                rows = query.all()
                # 按 code 去重，保留每个 code 的第一条（即最近日期）
                seen = set()
                unique_rows = []
                for item in rows:
                    if item.code not in seen:
                        seen.add(item.code)
                        unique_rows.append(item)
                rows = unique_rows
            else:
                query = self.db.query(MeanFrequencyResonanceIndicators).filter(
                    MeanFrequencyResonanceIndicators.code.in_(codes),
                    MeanFrequencyResonanceIndicators.date == date_str,
                    MeanFrequencyResonanceIndicators.market_type == market_type,
                )
                rows = query.all()

            result = []
            for item in rows:
                delta = item.macro_displacement_delta or 0.0
                ma20_d = item.ma20_d or 0.0
                mavol20_m = item.mavol20_m or 0.0
                eff_m20_m = item.efficiency_m20_minus_m or 0.0

                # Δ/d 从表的 bias 字段取值
                ratio_d = getattr(item, "bias", None)

                # 计算 m₂₀ 和量比: m20 = efficiency_m20_minus_m + mavol20_m
                current_volume = eff_m20_m + mavol20_m if mavol20_m else 0.0
                volume_ratio = None
                if mavol20_m and mavol20_m > 0:
                    volume_ratio = current_volume / mavol20_m

                row_dict = {
                    "code": item.code,
                    "date": str(item.date)[:10] if item.date else str(date)[:10],
                    "market_type": item.market_type or market_type,
                    "macro_displacement_delta": delta,
                    "ma20_d": ma20_d,
                    "ratio_d20": getattr(item, "ratio_d20", None),
                    "ratio_d1": getattr(item, "ratio_d1", None),
                    "instant_deviation": item.instant_deviation or 0.0,
                    "rising_days_z": item.rising_days_z or 0,
                    "falling_days_f": item.falling_days_f or 0,
                    "mavol20_m": mavol20_m,
                    "efficiency_m20_minus_m": eff_m20_m,
                    "ratio_d": ratio_d,
                    "current_volume": current_volume,
                    "volume_ratio": volume_ratio,
                    "d1": getattr(item, "d1", None),
                    "d1_date": getattr(item, "d1_date", None),
                    "d20": getattr(item, "d20", None),
                    "d20_date": getattr(item, "d20_date", None),
                    "ma60_d": getattr(item, "ma60_d", None),
                }
                result.append(row_dict)

            self._enrich_ma60_missing(result, market_type)

            logger.info(
                f"GMS 加载 {len(result)} 条指标, date={date}, market={market_type}"
                + (", 无当日数据时已用最近可用日" if use_latest_per_stock else "")
            )
            return result

        except Exception as e:
            logger.error(f"GMS 加载指标失败: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            raise

    def load_indicators_multi_day(
        self,
        codes: List[str],
        end_date: str,
        market_type: str = "CN",
        days: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        加载指定日期范围内最近 N 日的指标数据，用于计算「站稳3日」等多日逻辑

        Args:
            codes: 股票代码列表
            end_date: 截止日期 (YYYY-MM-DD)，取 date <= end_date 的最近 days 日
            market_type: CN 或 HK
            days: 需要的天数，默认 3

        Returns:
            List[Dict]，按 code + date 升序，每只股票可含多行
        """
        if not codes:
            return []

        try:
            from sqlalchemy import desc
            from backend_api.models import MeanFrequencyResonanceIndicators

            end_dt = str(end_date).strip()[:10]
            # 子查询：每只股票取 date <= end_date 的最近 days 个交易日
            subq = (
                self.db.query(
                    MeanFrequencyResonanceIndicators.code,
                    MeanFrequencyResonanceIndicators.date,
                )
                .filter(
                    MeanFrequencyResonanceIndicators.code.in_(codes),
                    MeanFrequencyResonanceIndicators.date <= end_dt,
                )
                .order_by(
                    MeanFrequencyResonanceIndicators.code,
                    desc(MeanFrequencyResonanceIndicators.date),
                )
            ).subquery()

            # 使用 row_number 或 limit 取每只股票最近 days 日（SQLite 无 row_number，改用多次查询或 in_ 子查询）
            # 简化：直接查 date <= end_date 的所有记录，按 code, date desc 排序，在 Python 中取每只股票前 days 条
            query = (
                self.db.query(MeanFrequencyResonanceIndicators)
                .filter(
                    MeanFrequencyResonanceIndicators.code.in_(codes),
                    MeanFrequencyResonanceIndicators.date <= end_dt,
                    MeanFrequencyResonanceIndicators.market_type == market_type,
                )
                .order_by(
                    MeanFrequencyResonanceIndicators.code,
                    MeanFrequencyResonanceIndicators.date.desc(),
                )
            )
            rows = query.all()

            # 按 code 分组，每只股票取最近 days 日
            by_code: Dict[str, List] = {}
            for item in rows:
                c = item.code
                if c not in by_code:
                    by_code[c] = []
                if len(by_code[c]) < days:
                    by_code[c].append(item)

            result = []
            for code in codes:
                for item in (by_code.get(code) or []):
                    delta = item.macro_displacement_delta or 0.0
                    ma20_d = item.ma20_d or 0.0
                    mavol20_m = item.mavol20_m or 0.0
                    eff_m20_m = item.efficiency_m20_minus_m or 0.0
                    ratio_d = getattr(item, "bias", None)
                    current_volume = eff_m20_m + mavol20_m if mavol20_m else 0.0
                    volume_ratio = current_volume / mavol20_m if mavol20_m and mavol20_m > 0 else None

                    row_dict = {
                        "code": item.code,
                        "date": str(item.date)[:10] if item.date else "",
                        "market_type": item.market_type or market_type,
                        "macro_displacement_delta": delta,
                        "ma20_d": ma20_d,
                        "ratio_d20": getattr(item, "ratio_d20", None),
                        "ratio_d1": getattr(item, "ratio_d1", None),
                        "instant_deviation": item.instant_deviation or 0.0,
                        "rising_days_z": item.rising_days_z or 0,
                        "falling_days_f": item.falling_days_f or 0,
                        "mavol20_m": mavol20_m,
                        "efficiency_m20_minus_m": eff_m20_m,
                        "ratio_d": ratio_d,
                        "current_volume": current_volume,
                        "volume_ratio": volume_ratio,
                    }
                    result.append(row_dict)

            # 按 code, date 升序（日期从小到大，便于算“最近3日”）
            result.sort(key=lambda x: (x["code"], x["date"]))

            logger.info(f"GMS 多日加载 {len(result)} 条, end_date={end_dt}, market={market_type}, days={days}")
            return result

        except Exception as e:
            logger.error(f"GMS 多日加载指标失败: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            raise

    def _enrich_ma60_missing(self, rows: List[Dict[str, Any]], market_type: str) -> None:
        """为缺失 ma60_d 的行从行情表估算 60 日均价（仅补缺，不覆盖已有值）。"""
        need: Dict[str, str] = {}
        for r in rows:
            if r.get("ma60_d") is not None:
                continue
            code = str(r.get("code") or "").strip()
            dt = str(r.get("date") or "")[:10]
            if code and dt:
                need[code] = dt
        if not need:
            return
        try:
            from sqlalchemy import desc
            from backend_api.models import HistoricalQuotes, HistoricalQuotesHK

            cache: Dict[str, float] = {}
            for code, end_dt in need.items():
                if market_type == "HK":
                    q = (
                        self.db.query(HistoricalQuotesHK.close)
                        .filter(
                            HistoricalQuotesHK.code == code,
                            HistoricalQuotesHK.date <= end_dt,
                        )
                        .order_by(desc(HistoricalQuotesHK.date))
                        .limit(60)
                    )
                else:
                    q = (
                        self.db.query(HistoricalQuotes.close)
                        .filter(
                            HistoricalQuotes.code == code,
                            HistoricalQuotes.date <= end_dt,
                        )
                        .order_by(desc(HistoricalQuotes.date))
                        .limit(60)
                    )
                closes = [float(x[0]) for x in q.all() if x[0] is not None]
                if len(closes) >= 60:
                    cache[code] = sum(closes[:60]) / 60.0
                elif closes:
                    cache[code] = sum(closes) / len(closes)
            for r in rows:
                if r.get("ma60_d") is not None:
                    continue
                code = str(r.get("code") or "").strip()
                if code in cache:
                    r["ma60_d"] = cache[code]
        except Exception as e:
            logger.warning("GMS 补全 ma60_d 失败: %s", e)
