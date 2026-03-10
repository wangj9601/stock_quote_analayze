"""
GMS 前端选股接口
供 API 调用的选股入口。
选股时优先从 gms_signal_trace 表读取已有信号，缺失时再计算并回填。
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime

from .data_loader import GMSDataLoader
from .strategy_engine import GMSStrategyEngine
from .config import GMSConfigManager

logger = logging.getLogger(__name__)


def _is_a_share(code: str) -> bool:
    s = str(code).strip()
    return len(s) >= 6 and s.isdigit() and s[0] in "6039"


def _infer_market_type(code: str) -> str:
    return "CN" if _is_a_share(code) else "HK"


def _trace_row_to_result(row) -> dict:
    """将 gms_signal_trace 表的一行转为与 engine.screen 一致的选股结果 dict。"""
    code_str = str(row.code).strip() if row.code is not None else ""
    return {
        "symbol": code_str,
        "code": code_str,
        "date": row.date,
        "market_type": row.market_type,
        "score_total": row.score_total,
        "score_accumulation": getattr(row, "score_accumulation", None),
        "score_momentum": getattr(row, "score_momentum", None),
        "left_buy_signal": row.left_buy_signal,
        "right_buy_signal": row.right_buy_signal,
        "buy_type": (row.buy_type or "").strip(),
        "signal_strength": getattr(row, "signal_strength", None),
        "sell_signal": getattr(row, "sell_signal", None),
    }


def _save_result_to_trace(db, result: dict, date: str) -> None:
    """将 engine.screen 单条结果写入 gms_signal_trace，便于后续优先读表。"""
    try:
        from backend_api.models import GMSSignalTrace
        code = result.get("code") or result.get("symbol") or ""
        market_type = result.get("market_type") or _infer_market_type(code)
        if not code:
            return
        rec = GMSSignalTrace(
            code=code,
            date=date,
            market_type=market_type,
            score_total=result.get("score_total"),
            score_accumulation=result.get("score_accumulation"),
            score_momentum=result.get("score_momentum"),
            signal_strength=result.get("signal_strength"),
            buy_type=result.get("buy_type") or None,
            left_buy_signal=result.get("left_buy_signal"),
            right_buy_signal=result.get("right_buy_signal"),
            sell_signal=result.get("sell_signal"),
        )
        db.merge(rec)
    except Exception as e:
        logger.warning("回填 gms_signal_trace 失败 %s: %s", result.get("code"), e)


class GMSFrontendInterface:
    """GMS 选股前端接口"""

    def __init__(self, db, config: Optional[dict] = None):
        self.db = db
        self.config = config or GMSConfigManager().get_config()
        self.min_score = 0
        self.max_results = 10000

    def set_selection_config(
        self,
        min_score: float = 0,
        max_results: int = 10000,
    ):
        self.min_score = min_score
        self.max_results = max_results

    def get_selection_results(
        self,
        date: Optional[str] = None,
        stock_pool: Optional[List[str]] = None,
        market: str = "all",
    ) -> List[dict]:
        """
        获取选股结果。优先从 gms_signal_trace 表读取；不存在则计算并回填后返回。
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        date = str(date).strip()[:10]

        if stock_pool is None:
            stock_pool = self._get_stock_pool(date, market)
        else:
            stock_pool = list(dict.fromkeys(stock_pool))

        if not stock_pool:
            return []

        # 按市场过滤：只保留当前 market 下的代码
        requested: List[Tuple[str, str]] = []
        for code in stock_pool:
            mt = _infer_market_type(code)
            if market == "all":
                requested.append((code, mt))
            elif market == "cn" and mt == "CN":
                requested.append((code, mt))
            elif market == "hk" and mt == "HK":
                requested.append((code, mt))

        if not requested:
            return []

        # 1) 先从 gms_signal_trace 读取已有记录（单次查询）
        from backend_api.models import GMSSignalTrace

        uniq_requested = list(dict.fromkeys(requested))
        codes_in = [str(c).strip() for c, _ in uniq_requested]
        mts_in = list({str(mt or "").strip() for _, mt in uniq_requested})
        rows = (
            self.db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.date == date,
                GMSSignalTrace.code.in_(codes_in),
                GMSSignalTrace.market_type.in_(mts_in),
            )
            .all()
        )
        # 统一用字符串 (code, market_type) 做 key，避免 DB 返回 int 导致 603667 与 "603667" 对不上
        def _key(c, mt):
            return (str(c).strip(), str(mt or "").strip())
        have_keys = set()
        from_trace: List[dict] = []
        for row in rows:
            if row.score_total is None:
                continue
            key = _key(row.code, row.market_type)
            if key in have_keys:
                continue
            have_keys.add(key)
            from_trace.append(_trace_row_to_result(row))

        # 2) 找出需要计算的 (code, market_type)
        missing = [(code, mt) for code, mt in uniq_requested if _key(code, mt) not in have_keys]
        computed: List[dict] = []
        if missing:
            loader = GMSDataLoader(self.db)
            engine = GMSStrategyEngine(loader, self.config)
            market_val = "CN" if market == "cn" else "HK" if market == "hk" else "all"
            missing_cn = [c for c, mt in missing if mt == "CN"]
            missing_hk = [c for c, mt in missing if mt == "HK"]
            for codes_sub, mt in [(missing_cn, "CN"), (missing_hk, "HK")]:
                if not codes_sub:
                    continue
                try:
                    sub = engine.screen(
                        codes=codes_sub,
                        date=date,
                        market=mt,
                        config=self.config,
                        min_score=0,
                        max_results=self.max_results,
                    )
                    for r in sub:
                        computed.append(r)
                        _save_result_to_trace(self.db, r, date)
                except Exception as e:
                    logger.warning("GMS 选股计算失败 %s %s: %s", date, mt, e)
            if computed:
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()

        # 3) 合并结果，按 min_score 过滤
        combined = from_trace + computed
        if self.min_score > 0:
            combined = [r for r in combined if (r.get("score_total") or 0) >= self.min_score]
        if self.max_results and len(combined) > self.max_results:
            combined = sorted(combined, key=lambda x: -(x.get("score_total") or 0))[: self.max_results]
        return combined

    def _get_stock_pool(self, date: str, market: str) -> List[str]:
        """
        按数据来源获取股票池：
        - cn（全部A股）：A 股基本信息表 stock_basic_info 全部代码
        - hk（全部港股）：港股基本信息表 stock_basic_info_hk 全部代码
        - all：上述两表合并（本接口由 API 在 scope=cn/hk 时分别传 market，此处 all 仅作备用）
        """
        try:
            from backend_api.models import StockBasicInfo, StockBasicInfoHK

            if market == "cn":
                rows = self.db.query(StockBasicInfo.code).all()
                codes = [str(r[0]).zfill(6) if isinstance(r[0], int) else str(r[0]) for r in rows if r[0] is not None]
                logger.info(f"GMS 股票池(全部A股): {len(codes)} 只")
            elif market == "hk":
                rows = self.db.query(StockBasicInfoHK.code).all()
                # 港股代码统一为 5 位补零（与 mean_frequency_resonance_indicators 表一致）
                codes = []
                for r in rows:
                    if r[0] is None:
                        continue
                    c = str(r[0]).strip()
                    if c.isdigit():
                        codes.append(c.zfill(5))
                    else:
                        codes.append(c)
                logger.info(f"GMS 股票池(全部港股): {len(codes)} 只")
            elif market == "all":
                cn_rows = self.db.query(StockBasicInfo.code).all()
                cn_codes = [str(r[0]).zfill(6) if isinstance(r[0], int) else str(r[0]) for r in cn_rows if r[0] is not None]
                hk_rows = self.db.query(StockBasicInfoHK.code).all()
                hk_codes = []
                for r in hk_rows:
                    if r[0] is None:
                        continue
                    c = str(r[0]).strip()
                    hk_codes.append(c.zfill(5) if c.isdigit() else c)
                codes = cn_codes + hk_codes
                logger.info(f"GMS 股票池(全部A+港股): {len(codes)} 只")
            else:
                return []

            return codes
        except Exception as e:
            logger.error(f"GMS 获取股票池失败: {e}", exc_info=True)
            return []
