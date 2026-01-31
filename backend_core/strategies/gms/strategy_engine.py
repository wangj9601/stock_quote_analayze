"""
GMS 策略引擎
串联 data_loader -> indicators_calculator -> signal_detector，输出选股结果
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

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
            选股结果列表，每项包含 symbol, name, price, score_total, buy_type, ratio_d20, ratio_d1, fz_ratio 等
        """
        results = []

        def _is_a_share(c: str) -> bool:
            s = str(c).strip()
            return len(s) >= 6 and s.isdigit() and s[0] in "603"

        if market == "all":
            cn_codes = [c for c in codes if _is_a_share(c)]
            hk_codes = [c for c in codes if c not in cn_codes]
            code_sets = [("CN", cn_codes), ("HK", hk_codes)]
        else:
            code_sets = [(market, codes)]

        for mt, codes_sub in code_sets:
            if not codes_sub:
                continue
            rows = self.data_loader.load_indicators(codes_sub, date, mt)
            for row in rows:
                ind = self.calculator.calculate(row)
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

                results.append({
                    "symbol": ind.code,
                    "code": ind.code,
                    "date": ind.date,
                    "market_type": ind.market_type,
                    "score_total": ind.score_total,
                    "score_accumulation": ind.score_accumulation,
                    "score_balance": ind.score_balance,
                    "score_momentum": ind.score_momentum,
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
                    "score_detail": {
                        "score_accumulation": ind.score_accumulation,
                        "score_balance": ind.score_balance,
                        "score_momentum": ind.score_momentum,
                        "score_total": ind.score_total,
                        # 实际使用的评分阈值（后端配置，供前端展示避免与页面参数混淆）
                        "accumulation_fz_min": self.calculator.accumulation_fz_min,
                        "balance_ratio_max": self.calculator.balance_ratio_max,
                        "momentum_volume_ratio_min": self.calculator.momentum_volume_ratio_min,
                        # GMSIndicators 指标细项（供前端得分明细展示）
                        "delta": ind.delta,                    # Δ (d₂₀ - d₁)
                        "d": ind.d,                            # d 20日均价
                        "d20": ind.d + ind.instant_deviation,   # d₂₀ 末日收盘价 = d + (d₂₀-d)
                        "d1": ind.d + ind.instant_deviation - ind.delta,  # d₁ 首日收盘价 = d₂₀ - Δ
                        "ratio_d20": ind.ratio_d20,            # 偏离率 Δ/d₂₀
                        "ratio_d1": ind.ratio_d1,              # 突变率 Δ/d₁
                        "ratio_d": ind.ratio_d,                # Δ/d 相对位移
                        "rising_days": ind.rising_days,        # Z 上涨天数
                        "falling_days": ind.falling_days,      # F 下跌天数
                        "avg_volume_20d": ind.avg_volume_20d,  # m 20日平均成交量
                        "current_volume": ind.current_volume,  # m₂₀ 当日成交量
                        "volume_ratio": ind.volume_ratio,      # 量比 m₂₀/m
                        "fz_ratio": ind.fz_ratio,              # F/Z 数方比
                        "instant_deviation": ind.instant_deviation,  # d₂₀ - d
                    },
                })

        results.sort(key=lambda x: x["score_total"], reverse=True)
        if max_results is not None and max_results > 0:
            results = results[:max_results]

        return results
