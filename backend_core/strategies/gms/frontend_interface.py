"""
GMS 前端选股接口
供 API 与回测调用的选股入口。
策略信号记录优先从 gms_signal_trace 表读取；若不存在或缺失，则增量重新计算，结果回填写入 gms_signal_trace。
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime

from sqlalchemy import cast, distinct, func, String

from .data_loader import GMSDataLoader
from .strategy_engine import GMSStrategyEngine
from .config import GMSConfigManager

from backend_api.services.gms_selection_snapshot import enrich_trace_meta

logger = logging.getLogger(__name__)

_GMS_BATCH_SIZE = max(50, int(os.getenv("GMS_SCREENING_BATCH_SIZE", "200")))


def _is_a_share(code: str) -> bool:
    from backend_api.utils.cn_listed_board_filter import is_cn_listed_equity_code

    return is_cn_listed_equity_code(code)


def _is_etf(code: str) -> bool:
    s = str(code).strip()
    return len(s) >= 6 and s.isdigit() and s[0] in "518"


def _infer_market_type(code: str) -> str:
    if _is_a_share(code):
        return "CN"
    if _is_etf(code):
        return "ETF"
    return "HK"


def _normalize_cn_pool_code(code: Any) -> str:
    if code is None:
        return ""
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _normalize_hk_pool_code(code: Any) -> str:
    if code is None:
        return ""
    s = str(code).strip()
    if s.isdigit() and len(s) < 5:
        return s.zfill(5)
    return s


def _normalize_etf_pool_code(code: Any) -> str:
    return str(code).strip() if code is not None else ""


def _resolve_pool_date_for_quotes(db, requested: str, model) -> str:
    """
    将请求日解析为行情表上可用的池基准日：
    - 晚于表内最新日：钳到 MAX(date)
    - 当日无采集记录：回退 MAX(date)
    - 否则使用请求日
    """
    requested = str(requested or "").strip()[:10]
    if not requested:
        requested = datetime.now().strftime("%Y-%m-%d")

    col = model.date
    row_max = db.query(func.max(col)).scalar()
    if row_max is None:
        return requested
    if hasattr(row_max, "strftime"):
        max_s = row_max.strftime("%Y-%m-%d")
    else:
        max_s = str(row_max).strip()[:10]

    if requested > max_s:
        return max_s

    exists = (
        db.query(model.code)
        .filter(cast(col, String) == requested)
        .limit(1)
        .first()
    )
    if exists is not None:
        return requested
    return max_s


def _distinct_codes_from_quotes(
    db,
    model,
    date_str: str,
    normalize_fn: Callable[[Any], str],
) -> List[str]:
    """取指定交易日行情表内 DISTINCT code（即当日已采集股票）。"""
    rows = (
        db.query(distinct(model.code))
        .filter(cast(model.date, String) == date_str)
        .order_by(model.code)
        .all()
    )
    out: List[str] = []
    seen: set[str] = set()
    for row in rows:
        if not row or row[0] is None:
            continue
        code = normalize_fn(row[0])
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _trace_row_to_result(row) -> dict:
    """将 gms_signal_trace 表的一行转为与 engine.screen 一致的选股结果 dict。"""
    code_str = str(row.code).strip() if row.code is not None else ""
    delta = getattr(row, "delta", None)
    d = getattr(row, "d", None)
    instant_deviation = getattr(row, "instant_deviation", None)
    # 与 strategy_engine 中 score_detail 的口径对齐：
    # d20 = d + instant_deviation
    # d1  = d20 - delta
    d20 = (d + instant_deviation) if (d is not None and instant_deviation is not None) else None
    d1 = (d20 - delta) if (d20 is not None and delta is not None) else None
    score_detail = {
        "score_total": getattr(row, "score_total", None),
        "score_accumulation": getattr(row, "score_accumulation", None),
        "score_momentum": getattr(row, "score_momentum", None),
        "score_acc_fz": getattr(row, "score_acc_fz", None),
        "score_acc_balance": getattr(row, "score_acc_balance", None),
        "score_acc_volume": getattr(row, "score_acc_volume", None),
        "score_mom_ratio_d1": getattr(row, "score_mom_ratio_d1", None),
        "score_mom_deviation": getattr(row, "score_mom_deviation", None),
        "score_mom_volume": getattr(row, "score_mom_volume", None),
        "acc_fz_judge": getattr(row, "acc_fz_judge", None),
        "acc_balance_judge": getattr(row, "acc_balance_judge", None),
        "acc_volume_judge": getattr(row, "acc_volume_judge", None),
        "mom_ratio_d1_judge": getattr(row, "mom_ratio_d1_judge", None),
        "mom_deviation_judge": getattr(row, "mom_deviation_judge", None),
        "mom_volume_judge": getattr(row, "mom_volume_judge", None),
        "accumulation_grade": getattr(row, "accumulation_grade", None),
        "momentum_grade": getattr(row, "momentum_grade", None),
        # 指标细项（前端得分明细面板直接读取这些字段）
        "delta": delta,
        "d": d,
        "d20": d20,
        "d1": d1,
        "ratio_d20": getattr(row, "ratio_d20", None),
        "ratio_d1": getattr(row, "ratio_d1", None),
        "fz_ratio": getattr(row, "fz_ratio", None),
        "volume_ratio": getattr(row, "volume_ratio", None),
        "instant_deviation": instant_deviation,
        "rising_days": getattr(row, "rising_days", None),
        "falling_days": getattr(row, "falling_days", None),
    }
    risk_tags = getattr(row, "risk_tags", None)
    if risk_tags is None and hasattr(row, "__dict__"):
        risk_tags = row.__dict__.get("risk_tags")
    out = {
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
        "delta": delta,
        "d": d,
        "ratio_d20": getattr(row, "ratio_d20", None),
        "ratio_d1": getattr(row, "ratio_d1", None),
        "fz_ratio": getattr(row, "fz_ratio", None),
        "rising_days": getattr(row, "rising_days", None),
        "falling_days": getattr(row, "falling_days", None),
        "score_detail": score_detail,
        "risk_tags": risk_tags or [],
    }
    return out


def _save_result_to_trace(db, result: dict, date: str, config_id: int) -> None:
    """
    将 engine.screen 单条结果完整写入 gms_signal_trace，便于后续优先读表。
    回测与选股均依赖此表：优先读 trace，缺失时增量计算并回填。
    """
    try:
        from backend_api.models import GMSSignalTrace
        code = result.get("code") or result.get("symbol") or ""
        market_type = result.get("market_type") or _infer_market_type(code)
        if not code:
            return
        sd = result.get("score_detail") or {}
        rec = GMSSignalTrace(
            code=code,
            date=date,
            market_type=market_type,
            config_id=int(config_id),
            score_total=result.get("score_total"),
            score_accumulation=result.get("score_accumulation"),
            score_momentum=result.get("score_momentum"),
            signal_strength=result.get("signal_strength"),
            buy_type=result.get("buy_type") or None,
            left_buy_signal=result.get("left_buy_signal"),
            right_buy_signal=result.get("right_buy_signal"),
            sell_signal=result.get("sell_signal"),
            accumulation_grade=result.get("accumulation_grade") or None,
            momentum_grade=result.get("momentum_grade") or None,
            delta=result.get("delta"),
            d=result.get("d"),
            ratio_d20=result.get("ratio_d20"),
            ratio_d1=result.get("ratio_d1"),
            fz_ratio=result.get("fz_ratio"),
            volume_ratio=result.get("volume_ratio"),
            instant_deviation=result.get("instant_deviation"),
            rising_days=result.get("rising_days"),
            falling_days=result.get("falling_days"),
            score_acc_fz=sd.get("score_acc_fz"),
            score_acc_balance=sd.get("score_acc_balance"),
            score_acc_volume=sd.get("score_acc_volume"),
            score_mom_ratio_d1=sd.get("score_mom_ratio_d1"),
            score_mom_deviation=sd.get("score_mom_deviation"),
            score_mom_volume=sd.get("score_mom_volume"),
            acc_fz_judge=sd.get("acc_fz_judge") or None,
            acc_balance_judge=sd.get("acc_balance_judge") or None,
            acc_volume_judge=sd.get("acc_volume_judge") or None,
            mom_ratio_d1_judge=sd.get("mom_ratio_d1_judge") or None,
            mom_deviation_judge=sd.get("mom_deviation_judge") or None,
            mom_volume_judge=sd.get("mom_volume_judge") or None,
        )
        db.merge(rec)
        rt = result.get("risk_tags")
        sd_full = result.get("score_detail")
        if rt is not None or sd_full is not None:
            try:
                import json
                from sqlalchemy import text as sql_text

                db.execute(
                    sql_text(
                        """
                        UPDATE gms_signal_trace
                        SET risk_tags = CAST(:rt AS JSONB),
                            score_detail = COALESCE(CAST(:sd AS JSONB), score_detail)
                        WHERE code = :code AND date = :dt AND market_type = :mt AND config_id = :cid
                        """
                    ),
                    {
                        "rt": json.dumps(rt or [], ensure_ascii=False),
                        "sd": json.dumps(sd_full, ensure_ascii=False, default=str) if sd_full else None,
                        "code": code,
                        "dt": date,
                        "mt": market_type,
                        "cid": int(config_id),
                    },
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning("回填 gms_signal_trace 失败 %s: %s", result.get("code"), e)


class GMSFrontendInterface:
    """GMS 选股前端接口"""

    def __init__(
        self,
        db,
        config: Optional[dict] = None,
        config_id: Optional[int] = None,
    ):
        self.db = db
        self._mgr = GMSConfigManager()
        self.config_id = self._mgr.resolve_config_id(config_id)
        self.config = config or self._mgr.get_config(self.config_id)
        self.use_trace = self._mgr.should_use_trace(self.config_id)
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
        trace_only: bool = False,
        return_meta: bool = False,
        exclude_st: bool = False,
        cn_board_segment: Optional[str] = None,
    ) -> Union[List[dict], Tuple[List[dict], Dict[str, Any]]]:
        """
        获取选股结果。优先从 gms_signal_trace 表读取策略信号记录；
        若不存在或缺失，则增量重新计算，结果回填写入 gms_signal_trace 后返回。

        Args:
            trace_only: 为 True 时只读库内 trace，不对缺失股票做实时计算（用于前端先快速展示缓存）。
            return_meta: 为 True 时返回 (列表, 统计字典)，便于接口返回 trace_complete 等字段。
            exclude_st: 为 True 时剔除 A 股 ST 类股票（名称含 ST）。
            cn_board_segment: A 股板块 MAIN/CYB/SZ_SME/KCB/BJ；仅过滤 A 股代码，港股/ETF 保留。
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        date = str(date).strip()[:10]

        if stock_pool is None:
            stock_pool = self._get_stock_pool(date, market)
        else:
            stock_pool = list(dict.fromkeys(stock_pool))

        if cn_board_segment:
            from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

            stock_pool = filter_stock_codes_by_board_segment(stock_pool, cn_board_segment)

        if exclude_st and stock_pool:
            from backend_api.utils.st_stock_filter import filter_codes_exclude_st

            before = len(stock_pool)
            stock_pool = filter_codes_exclude_st(self.db, stock_pool)
            if before != len(stock_pool):
                logger.info(
                    "GMS 剔除 ST 相关股: %s -> %s 只",
                    before,
                    len(stock_pool),
                )

        if not stock_pool:
            empty_meta = {
                "from_trace_count": 0,
                "computed_count": 0,
                "requested_count": 0,
                "trace_complete": True,
            }
            return ([], empty_meta) if return_meta else []

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
            elif market == "etf" and mt == "ETF":
                requested.append((code, mt))

        if not requested:
            empty_meta = {
                "from_trace_count": 0,
                "computed_count": 0,
                "requested_count": 0,
                "trace_complete": True,
            }
            return ([], empty_meta) if return_meta else []

        # 1) 先从 gms_signal_trace 读取已有记录（单次查询）
        from backend_api.models import GMSSignalTrace

        uniq_requested = list(dict.fromkeys(requested))
        codes_in = [str(c).strip() for c, _ in uniq_requested]
        mts_in = list({str(mt or "").strip() for _, mt in uniq_requested})
        from_trace: List[dict] = []
        have_keys = set()
        if self.use_trace:
            rows = (
                self.db.query(GMSSignalTrace)
                .filter(
                    GMSSignalTrace.date == date,
                    GMSSignalTrace.code.in_(codes_in),
                    GMSSignalTrace.market_type.in_(mts_in),
                    GMSSignalTrace.config_id == self.config_id,
                )
                .all()
            )
            # 统一用字符串 (code, market_type) 做 key，避免 DB 返回 int 导致 603667 与 "603667" 对不上
            def _key(c, mt):
                return (str(c).strip(), str(mt or "").strip())
            for row in rows:
                if row.score_total is None:
                    continue
                key = _key(row.code, row.market_type)
                if key in have_keys:
                    continue
                have_keys.add(key)
                from_trace.append(_trace_row_to_result(row))
        else:
            def _key(c, mt):
                return (str(c).strip(), str(mt or "").strip())

        missing = [(code, mt) for code, mt in uniq_requested if _key(code, mt) not in have_keys]
        computed: List[dict] = []
        if missing and not trace_only:
            loader = GMSDataLoader(self.db)
            engine = GMSStrategyEngine(loader, self.config)
            missing_cn = [c for c, mt in missing if mt == "CN"]
            missing_etf = [c for c, mt in missing if mt == "ETF"]
            missing_hk = [c for c, mt in missing if mt == "HK"]
            # 大批量股票池时每 100 只一批计算并打印进度，避免长时间无日志
            batch_size = _GMS_BATCH_SIZE
            pool_label = {"CN": "全部A股", "ETF": "全部ETF", "HK": "全部港股"}
            for codes_sub, mt in [(missing_cn, "CN"), (missing_etf, "ETF"), (missing_hk, "HK")]:
                if not codes_sub:
                    continue
                total_missing = len(codes_sub)
                label = pool_label.get(mt, mt)
                for start in range(0, total_missing, batch_size):
                    chunk = codes_sub[start : start + batch_size]
                    done = min(start + len(chunk), total_missing)
                    try:
                        sub = engine.screen(
                            codes=chunk,
                            date=date,
                            market=mt,
                            config=self.config,
                            min_score=0,
                            max_results=self.max_results,
                        )
                        for r in sub:
                            computed.append(r)
                            if self.use_trace:
                                _save_result_to_trace(self.db, r, date, self.config_id)
                        logger.info(
                            "GMS 策略信号计算进度 %s(%s) %s：已完成 %d/%d 只",
                            label,
                            mt,
                            date,
                            done,
                            total_missing,
                        )
                    except Exception as e:
                        logger.warning(
                            "GMS 选股计算失败 %s %s 批次 %d-%d: %s",
                            date,
                            mt,
                            start + 1,
                            done,
                            e,
                        )
                        # 发生 DB 异常后当前事务会进入 failed 状态，需回滚后再继续后续批次
                        try:
                            self.db.rollback()
                        except Exception:
                            pass
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

        meta: Dict[str, Any] = enrich_trace_meta(
            {
                "from_trace_count": len(from_trace),
                "computed_count": len(computed),
                "requested_count": len(uniq_requested),
                "trace_complete": len(missing) == 0,
                "config_id": self.config_id,
                "use_trace": self.use_trace,
                "batch_size": _GMS_BATCH_SIZE,
            }
        )
        if return_meta:
            return combined, meta
        return combined

    def _get_stock_pool(self, date: str, market: str) -> List[str]:
        """
        按当日采集行情获取股票池（非基本信息表全量）：
        - cn：historical_quotes 在基准日的 DISTINCT code
        - hk：historical_quotes_hk
        - etf：fund_historical_quotes
        - all：三者并集
        基准日优先使用请求 date；若该日尚无采集则回退至对应行情表最新有数据交易日。
        """
        try:
            from backend_api.models import FundHistoricalQuotes, HistoricalQuotes, HistoricalQuotesHK

            req_date = str(date).strip()[:10]

            if market == "cn":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotes)
                codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotes, eff, _normalize_cn_pool_code
                )
                logger.info("GMS 股票池(全部A股, %s): %s 只", eff, len(codes))
                return codes

            if market == "hk":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotesHK)
                codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotesHK, eff, _normalize_hk_pool_code
                )
                logger.info("GMS 股票池(全部港股, %s): %s 只", eff, len(codes))
                return codes

            if market == "etf":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, FundHistoricalQuotes)
                codes = _distinct_codes_from_quotes(
                    self.db, FundHistoricalQuotes, eff, _normalize_etf_pool_code
                )
                logger.info("GMS 股票池(全部ETF, %s): %s 只", eff, len(codes))
                return codes

            if market == "all":
                eff_cn = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotes)
                cn_codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotes, eff_cn, _normalize_cn_pool_code
                )
                eff_hk = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotesHK)
                hk_codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotesHK, eff_hk, _normalize_hk_pool_code
                )
                eff_etf = _resolve_pool_date_for_quotes(self.db, req_date, FundHistoricalQuotes)
                etf_codes = _distinct_codes_from_quotes(
                    self.db, FundHistoricalQuotes, eff_etf, _normalize_etf_pool_code
                )
                codes = cn_codes + etf_codes + hk_codes
                logger.info(
                    "GMS 股票池(全部A+ETF+港股, 请求日=%s): %s 只 [A股 %s@%s, ETF %s@%s, 港股 %s@%s]",
                    req_date,
                    len(codes),
                    len(cn_codes),
                    eff_cn,
                    len(etf_codes),
                    eff_etf,
                    len(hk_codes),
                    eff_hk,
                )
                return codes

            return []
        except Exception as e:
            logger.error(f"GMS 获取股票池失败: {e}", exc_info=True)
            return []
