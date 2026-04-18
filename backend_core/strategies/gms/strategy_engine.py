"""
GMS 策略引擎
串联 data_loader -> indicators_calculator -> signal_detector，输出选股结果
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from .data_loader import GMSDataLoader
from .indicators_calculator import GMSIndicatorsCalculator
from .signal_detector import GMSSignalDetector
from .models import GMSIndicators
from .config import GMSConfigManager

logger = logging.getLogger(__name__)


class GMSStrategyEngine:
    """GMS 选股策略引擎"""

    def __init__(
        self,
        data_loader: GMSDataLoader,
        config: Optional[Dict] = None,
    ):
        self.data_loader = data_loader
        cfg = config or GMSConfigManager().get_config()
        self.calculator = GMSIndicatorsCalculator(cfg)
        self.detector = GMSSignalDetector(cfg)
        self.watch_threshold = float(cfg.get("scoring", {}).get("watch_threshold", 60))
        self.alert_threshold = float(cfg.get("scoring", {}).get("alert_threshold", 90))
        self.stable_days = int(cfg.get("scoring", {}).get("instant_deviation_stable_days", 3))

    def screen(
        self,
        codes: List[str],
        date: str,
        market: str = "CN",
        config: Optional[Dict] = None,
        min_score: float = 0,
        max_results: Optional[int] = None,
    ) -> List[Dict]:
        """
        选股：返回符合条件的股票列表

        Args:
            codes: 股票代码列表
            date: 目标日期
            market: CN 或 HK 或 all（all 时分两次查 CN 和 HK）
            config: 覆盖配置
            min_score: 最低总分（默认 0，即 watch_threshold 以下也返回时设为 0）
            max_results: 最大返回数量

        Returns:
            选股结果列表，每项包含 symbol, score_total, buy_type, signal_strength 等
        """
        results = []

        def _is_a_share(c: str) -> bool:
            s = str(c).strip()
            # 6 位数字：6/0/3 为 A 股，9 为沪市 B 股（指标表按 CN 存储），均按 CN 查指标
            return len(s) >= 6 and s.isdigit() and s[0] in "6039"

        def _is_etf(c: str) -> bool:
            s = str(c).strip()
            # ETF基金代码：5/1/8 开头的 6 位数字
            return len(s) >= 6 and s.isdigit() and s[0] in "518"

        if market == "all":
            cn_codes = [c for c in codes if _is_a_share(c)]
            etf_codes = [c for c in codes if _is_etf(c)]
            hk_codes = [c for c in codes if c not in cn_codes and c not in etf_codes]
            code_sets = [("CN", cn_codes), ("ETF", etf_codes), ("HK", hk_codes)]
        else:
            code_sets = [(market, codes)]

        for mt, codes_sub in code_sets:
            if not codes_sub:
                continue

            # 无目标日行情时使用该股票最近可用日数据作为筛选条件
            rows = self.data_loader.load_indicators(
                codes_sub, date, mt, use_latest_per_stock=True
            )
            dev_series_by_code: Dict[str, List[float]] = {}
            if self.stable_days > 1:
                multi_rows = self.data_loader.load_indicators_multi_day(
                    codes_sub, date, mt, days=self.stable_days
                )
                by_code = defaultdict(list)
                for r in multi_rows:
                    by_code[r["code"]].append(r)
                for code, code_rows in by_code.items():
                    code_rows.sort(key=lambda x: x["date"])
                    recent = code_rows[-self.stable_days:]
                    dev_series_by_code[code] = [
                        float(r.get("instant_deviation", 0) or 0) for r in recent
                    ]

            for row in rows:
                code = row.get("code", "")
                dev_series = dev_series_by_code.get(code) if dev_series_by_code else None
                ind = self.calculator.calculate(row, instant_deviation_series=dev_series)
                if ind is None:
                    continue
                if ind.score_total < min_score:
                    continue

                left = self.detector.detect_left_buy(ind)
                right = self.detector.detect_right_buy(ind)
                sell = self.detector.detect_sell(ind)

                ind.left_buy_signal = left
                ind.right_buy_signal = right
                ind.sell_signal = sell

                buy_type = ""
                if left:
                    buy_type = "左侧"
                elif right:
                    buy_type = "右侧"

                st = ind.score_total
                signal_strength = st / 100.0 if st is not None and st > 0 else 0.0

                score_detail = {
                    "score_accumulation": ind.score_accumulation,
                    "score_balance": ind.score_balance,
                    "score_momentum": ind.score_momentum,
                    "score_total": ind.score_total,
                    "accumulation_grade": getattr(ind, "accumulation_grade", ""),
                    "momentum_grade": getattr(ind, "momentum_grade", ""),
                    "accumulation_fz_min": self.calculator.accumulation_fz_min,
                    "balance_ratio_max": self.calculator.balance_ratio_max,
                    "momentum_volume_ratio_min": self.calculator.momentum_volume_ratio_min,
                    "accumulation_s_threshold": self.calculator.acc_s_threshold,
                    "accumulation_a_threshold": self.calculator.acc_a_threshold,
                    "momentum_full_threshold": self.calculator.mom_full_threshold,
                    "momentum_batch_threshold": self.calculator.mom_batch_threshold,
                    "score_acc_fz": getattr(ind, "score_acc_fz", 0),
                    "score_acc_balance": getattr(ind, "score_acc_balance", 0),
                    "score_acc_volume": getattr(ind, "score_acc_volume", 0),
                    "score_mom_ratio_d1": getattr(ind, "score_mom_ratio_d1", 0),
                    "score_mom_deviation": getattr(ind, "score_mom_deviation", 0),
                    "score_mom_volume": getattr(ind, "score_mom_volume", 0),
                    "acc_fz_tiers": self.calculator.acc_fz_tiers,
                    "balance_tiers": self.calculator.balance_tiers,
                    "vol_shrink_tiers": self.calculator.vol_shrink_tiers,
                    "ratio_d1_tiers": self.calculator.ratio_d1_tiers,
                    "vol_attack_tiers": self.calculator.vol_attack_tiers,
                    "weight_acc_fz": self.calculator.weight_acc_fz,
                    "weight_acc_balance": self.calculator.weight_acc_balance,
                    "weight_acc_volume": self.calculator.weight_acc_volume,
                    "weight_mom_ratio_d1": self.calculator.weight_mom_ratio_d1,
                    "weight_mom_deviation": self.calculator.weight_mom_deviation,
                    "weight_mom_volume": self.calculator.weight_mom_volume,
                    "acc_fz_judge": getattr(ind, "acc_fz_judge", ""),
                    "acc_balance_judge": getattr(ind, "acc_balance_judge", ""),
                    "acc_volume_judge": getattr(ind, "acc_volume_judge", ""),
                    "mom_ratio_d1_judge": getattr(ind, "mom_ratio_d1_judge", ""),
                    "mom_deviation_judge": getattr(ind, "mom_deviation_judge", ""),
                    "mom_volume_judge": getattr(ind, "mom_volume_judge", ""),
                    "delta": ind.delta,
                    "d": ind.d,
                    "d20": ind.d + ind.instant_deviation,
                    "d1": ind.d + ind.instant_deviation - ind.delta,
                    "d1_date": (ind.raw_row.get("d1_date") if ind.raw_row else None) or None,
                    "d20_date": (ind.raw_row.get("d20_date") if ind.raw_row else None) or ind.date,
                    "ratio_d20": ind.ratio_d20,
                    "ratio_d1": ind.ratio_d1,
                    "ratio_d": ind.ratio_d,
                    "rising_days": ind.rising_days,
                    "falling_days": ind.falling_days,
                    "avg_volume_20d": ind.avg_volume_20d,
                    "current_volume": ind.current_volume,
                    "volume_ratio": ind.volume_ratio,
                    "fz_ratio": ind.fz_ratio,
                    "instant_deviation": ind.instant_deviation,
                }

                results.append({
                    "symbol": ind.code,
                    "code": ind.code,
                    "date": ind.date,
                    "market_type": ind.market_type,
                    "score_total": ind.score_total,
                    "score_accumulation": ind.score_accumulation,
                    "score_balance": ind.score_balance,
                    "score_momentum": ind.score_momentum,
                    "accumulation_grade": getattr(ind, "accumulation_grade", ""),
                    "momentum_grade": getattr(ind, "momentum_grade", ""),
                    "signal_strength": signal_strength,
                    "buy_type": buy_type,
                    "left_buy_signal": left,
                    "right_buy_signal": right,
                    "sell_signal": sell,
                    "ratio_d20": ind.ratio_d20,
                    "ratio_d1": ind.ratio_d1,
                    "ratio_d": ind.ratio_d,
                    "fz_ratio": ind.fz_ratio,
                    "volume_ratio": ind.volume_ratio,
                    "delta": ind.delta,
                    "d": ind.d,
                    "instant_deviation": ind.instant_deviation,
                    "rising_days": ind.rising_days,
                    "falling_days": ind.falling_days,
                    "score_detail": score_detail,
                })

        results.sort(key=lambda x: x["score_total"], reverse=True)
        if max_results is not None and max_results > 0:
            results = results[:max_results]

        return results
