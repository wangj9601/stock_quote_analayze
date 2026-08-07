# -*- coding: utf-8 -*-
"""GMS 主行业板共振：归属解析、板块斜率、软减分后处理。

资金流字段本轮仅预留（板级尚未采集）；强弱主用 sector_slope，旁证用实时涨跌。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DEFAULT_BOARD_WEAK_POINTS = 10.0
DEFAULT_SECTOR_SLOPE_WINDOW = 60
DEFAULT_BOARD_PANEL_LIMIT = 40  # 每板最多采样成分股，控制选股耗时
DEFAULT_LOOKBACK = 120


def empty_board_resonance() -> Dict[str, Any]:
    return {
        "primary_board_code": None,
        "primary_board_name": None,
        "primary_board_kind": None,
        "sector_slope": None,
        "board_change_percent": None,
        "board_weak": False,
        "board_weak_reason": None,
        "board_main_net_inflow": None,  # 二期：板级资金流
        "enable_board_fund_flow": False,
    }


def resolve_board_resonance_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    root = config if isinstance(config, dict) else {}
    scoring = root.get("scoring") if isinstance(root.get("scoring"), dict) else {}
    br = root.get("board_resonance") if isinstance(root.get("board_resonance"), dict) else {}
    if not br and isinstance(scoring.get("board_resonance"), dict):
        br = scoring["board_resonance"]

    def _get(key: str, default: Any) -> Any:
        if key in br and br[key] is not None:
            return br[key]
        if key in scoring and scoring[key] is not None:
            return scoring[key]
        if key in root and root[key] is not None:
            return root[key]
        return default

    return {
        "enabled": bool(_get("board_resonance_enabled", True)),
        "sector_slope_window": int(_get("sector_slope_window", DEFAULT_SECTOR_SLOPE_WINDOW)),
        "slope_weak_threshold": float(_get("board_slope_weak_threshold", 0.0)),
        "panel_member_limit": int(_get("board_panel_member_limit", DEFAULT_BOARD_PANEL_LIMIT)),
        "lookback_days": int(_get("board_slope_lookback_days", DEFAULT_LOOKBACK)),
        "enable_board_fund_flow": bool(_get("enable_board_fund_flow", False)),
        "use_realtime_change_fallback": bool(_get("board_use_realtime_change_fallback", True)),
    }


def _find_board_weak_rule(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    scoring = (config or {}).get("scoring") or {}
    for r in scoring.get("penalty_rules") or []:
        if isinstance(r, dict) and (r.get("id") or "").strip() == "board_weak" and r.get("enabled", True):
            return r
    return None


def batch_resolve_primary_boards(
    db,
    codes: Sequence[str],
    *,
    board_code_source: str = "tonghuashun",
) -> Dict[str, Dict[str, Any]]:
    """批量解析主行业板（成分数最多）；无行业时不回退概念（与展示行业一致优先）。"""
    from sqlalchemy import bindparam, text

    from backend_core.strategies.rpe.data_loader import _norm_code

    out: Dict[str, Dict[str, Any]] = {}
    norms = []
    for c in codes:
        n = _norm_code(c)
        if n and n not in norms:
            norms.append(n)
    if not norms:
        return out

    # 分批避免 IN 过长
    chunk = 400
    for i in range(0, len(norms), chunk):
        part = norms[i : i + chunk]
        try:
            sql = text(
                """
                SELECT DISTINCT ON (c.stock_code)
                       c.stock_code,
                       c.board_code,
                       COALESCE(b.board_name, c.board_code) AS board_name,
                       cnt.n AS member_count
                FROM industry_board_constituents c
                JOIN (
                    SELECT board_code, COUNT(*) AS n
                    FROM industry_board_constituents
                    GROUP BY board_code
                ) cnt ON cnt.board_code = c.board_code
                LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                WHERE c.stock_code IN :codes
                  AND (
                    :src = '' OR b.board_code_source IS NULL OR b.board_code_source = :src
                  )
                ORDER BY c.stock_code, cnt.n DESC, c.board_code ASC
                """
            ).bindparams(bindparam("codes", expanding=True))
            rows = db.execute(sql, {"codes": part, "src": board_code_source or ""}).fetchall()
            for r in rows:
                code = _norm_code(r[0])
                if not code:
                    continue
                out[code] = {
                    "board_code": str(r[1]),
                    "board_name": str(r[2] or r[1]),
                    "board_kind": "industry",
                    "member_count": int(r[3] or 0),
                }
        except Exception as e:
            logger.warning("batch_resolve_primary_boards failed: %s", e)
            # 回退：不按 source 过滤
            try:
                sql2 = text(
                    """
                    SELECT DISTINCT ON (c.stock_code)
                           c.stock_code,
                           c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name,
                           cnt.n AS member_count
                    FROM industry_board_constituents c
                    JOIN (
                        SELECT board_code, COUNT(*) AS n
                        FROM industry_board_constituents
                        GROUP BY board_code
                    ) cnt ON cnt.board_code = c.board_code
                    LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                    ORDER BY c.stock_code, cnt.n DESC, c.board_code ASC
                    """
                ).bindparams(bindparam("codes", expanding=True))
                rows = db.execute(sql2, {"codes": part}).fetchall()
                for r in rows:
                    code = _norm_code(r[0])
                    if code and code not in out:
                        out[code] = {
                            "board_code": str(r[1]),
                            "board_name": str(r[2] or r[1]),
                            "board_kind": "industry",
                            "member_count": int(r[3] or 0),
                        }
            except Exception as e2:
                logger.warning("batch_resolve_primary_boards fallback failed: %s", e2)
    return out


def _load_board_change_percents(db, board_codes: Sequence[str]) -> Dict[str, Optional[float]]:
    from sqlalchemy import bindparam, text

    out: Dict[str, Optional[float]] = {}
    codes = [str(c) for c in board_codes if c]
    if not codes:
        return out
    try:
        sql = text(
            """
            SELECT board_code, change_percent
            FROM industry_board_realtime_quotes
            WHERE board_code IN :codes
            """
        ).bindparams(bindparam("codes", expanding=True))
        for r in db.execute(sql, {"codes": codes}).fetchall():
            bc = str(r[0])
            try:
                out[bc] = float(r[1]) if r[1] is not None else None
            except (TypeError, ValueError):
                out[bc] = None
    except Exception as e:
        logger.debug("load board change_percent failed: %s", e)
    return out


def compute_board_sector_slope(
    loader,
    board_code: str,
    *,
    board_kind: str = "industry",
    end_date: Optional[str] = None,
    window: int = DEFAULT_SECTOR_SLOPE_WINDOW,
    lookback: int = DEFAULT_LOOKBACK,
    member_limit: int = DEFAULT_BOARD_PANEL_LIMIT,
) -> Optional[float]:
    """合成板块量权基准并算斜率；失败返回 None。"""
    from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark, sector_slope

    try:
        members = loader.load_board_members(board_code, board_kind=board_kind)
        if len(members) < 5:
            return None
        codes = [m["code"] for m in members[: max(5, int(member_limit))]]
        panel = loader.load_sector_panel(codes, end_date=end_date, lookback=lookback)
        if len(panel) < 5:
            return None
        date_members = loader.build_date_members(panel)
        benchmark = compute_vwap_benchmark(date_members)
        if len(benchmark) < max(10, int(window) // 2):
            return None
        return sector_slope(benchmark, int(window))
    except Exception as e:
        logger.debug("compute_board_sector_slope %s failed: %s", board_code, e)
        return None


def _is_board_weak(
    *,
    sector_slope_v: Optional[float],
    board_change_percent: Optional[float],
    slope_threshold: float,
    use_realtime_fallback: bool,
) -> Tuple[bool, Optional[str]]:
    if sector_slope_v is not None:
        if float(sector_slope_v) < float(slope_threshold):
            return True, "sector_slope_negative"
        return False, "sector_slope_ok"
    if use_realtime_fallback and board_change_percent is not None:
        if float(board_change_percent) < 0:
            return True, "realtime_change_negative"
        return False, "realtime_change_ok"
    return False, "insufficient_board_data"


def apply_board_weak_penalty_to_item(
    item: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """若 board_weak 且配置了减分规则，从总分后处理扣分并写入 score_detail。"""
    if not item.get("board_weak"):
        return
    rule = _find_board_weak_rule(config)
    if not rule:
        # 无规则时仍打 risk_tags，不改分
        tags = list(item.get("risk_tags") or [])
        if "board_weak" not in tags:
            tags.append("board_weak")
            item["risk_tags"] = tags
        return

    from backend_core.strategies.gms.scoring._helpers import safe_float

    points = safe_float(rule.get("points"), DEFAULT_BOARD_WEAK_POINTS)
    if points <= 0:
        return

    sd = item.get("score_detail") if isinstance(item.get("score_detail"), dict) else {}
    sd = dict(sd)
    penalties = list(sd.get("penalties") or [])
    if any(isinstance(p, dict) and p.get("id") == "board_weak" for p in penalties):
        return  # 已应用

    label = rule.get("label") or "主行业板走弱"
    detail = {
        "id": "board_weak",
        "label": label,
        "points": points,
        "applied": True,
        "sector_slope": item.get("sector_slope"),
        "board_change_percent": item.get("board_change_percent"),
        "board_weak_reason": item.get("board_weak_reason"),
        "primary_board_code": item.get("primary_board_code"),
        "primary_board_name": item.get("primary_board_name"),
        "post_process": True,
    }
    penalties.append(detail)
    prev_deduction = safe_float(sd.get("score_penalty_deduction"), 0.0)
    new_deduction = prev_deduction + points
    sd["penalties"] = penalties
    sd["score_penalty_deduction"] = new_deduction
    if sd.get("score_base_total") is None and item.get("score_total") is not None:
        sd["score_base_total"] = safe_float(item.get("score_total"), 0.0) + prev_deduction

    base = sd.get("score_base_total")
    if base is None:
        base = safe_float(item.get("score_total"), 0.0) + points
        sd["score_base_total"] = base
    new_total = max(0.0, safe_float(base, 0.0) - new_deduction)
    sd["score_total"] = new_total
    item["score_detail"] = sd
    item["score_total"] = new_total
    # 信号强度约定为总分/100
    try:
        item["signal_strength"] = round(new_total / 100.0, 4)
    except Exception:
        pass

    br = sd.get("board_resonance") if isinstance(sd.get("board_resonance"), dict) else {}
    br = dict(br)
    br.update(
        {
            "board_weak": True,
            "penalty_applied": True,
            "penalty_points": points,
        }
    )
    sd["board_resonance"] = br
    item["score_detail"] = sd

    tags = list(item.get("risk_tags") or [])
    if "board_weak" not in tags:
        tags.append("board_weak")
        item["risk_tags"] = tags


def enrich_results_with_board_resonance(
    db,
    results: List[Dict[str, Any]],
    *,
    config: Optional[Dict[str, Any]] = None,
    end_date: Optional[str] = None,
    board_code_source: str = "tonghuashun",
) -> None:
    """就地 enrich GMS 选股结果：主行业板、斜率、board_weak、预留资金流；并应用软减分。"""
    br_cfg = resolve_board_resonance_config(config)
    if not br_cfg.get("enabled", True):
        for item in results:
            item.setdefault("board_weak", False)
            item.setdefault("board_main_net_inflow", None)
            item.setdefault("enable_board_fund_flow", False)
        return

    from backend_core.strategies.rpe.data_loader import RPEDataLoader, _norm_code

    codes = []
    for item in results:
        c = _norm_code(item.get("symbol") or item.get("code"))
        if c:
            codes.append(c)

    primary_map = batch_resolve_primary_boards(db, codes, board_code_source=board_code_source)
    board_codes = sorted({v["board_code"] for v in primary_map.values() if v.get("board_code")})
    change_map = _load_board_change_percents(db, board_codes)

    loader = RPEDataLoader(db)
    slope_cache: Dict[str, Optional[float]] = {}
    window = int(br_cfg["sector_slope_window"])
    lookback = int(br_cfg["lookback_days"])
    member_limit = int(br_cfg["panel_member_limit"])
    slope_th = float(br_cfg["slope_weak_threshold"])
    use_rt = bool(br_cfg["use_realtime_change_fallback"])
    enable_ff = bool(br_cfg["enable_board_fund_flow"])

    for bc in board_codes:
        slope_cache[bc] = compute_board_sector_slope(
            loader,
            bc,
            board_kind="industry",
            end_date=end_date,
            window=window,
            lookback=lookback,
            member_limit=member_limit,
        )

    for item in results:
        code = _norm_code(item.get("symbol") or item.get("code"))
        info = primary_map.get(code) if code else None
        payload = empty_board_resonance()
        payload["enable_board_fund_flow"] = enable_ff
        # 二期启用前恒为 None
        payload["board_main_net_inflow"] = None

        if info:
            bc = info["board_code"]
            payload["primary_board_code"] = bc
            payload["primary_board_name"] = info.get("board_name")
            payload["primary_board_kind"] = info.get("board_kind") or "industry"
            slope_v = slope_cache.get(bc)
            chg = change_map.get(bc)
            payload["sector_slope"] = round(float(slope_v), 6) if slope_v is not None else None
            payload["board_change_percent"] = chg
            weak, reason = _is_board_weak(
                sector_slope_v=slope_v,
                board_change_percent=chg,
                slope_threshold=slope_th,
                use_realtime_fallback=use_rt,
            )
            payload["board_weak"] = weak
            payload["board_weak_reason"] = reason
        else:
            payload["board_weak_reason"] = "no_primary_board"

        item["primary_board_code"] = payload["primary_board_code"]
        item["primary_board_name"] = payload["primary_board_name"]
        item["primary_board_kind"] = payload["primary_board_kind"]
        item["sector_slope"] = payload["sector_slope"]
        item["board_change_percent"] = payload["board_change_percent"]
        item["board_weak"] = payload["board_weak"]
        item["board_weak_reason"] = payload["board_weak_reason"]
        item["board_main_net_inflow"] = payload["board_main_net_inflow"]
        item["enable_board_fund_flow"] = payload["enable_board_fund_flow"]

        sd = item.get("score_detail") if isinstance(item.get("score_detail"), dict) else {}
        sd = dict(sd)
        sd["board_resonance"] = dict(payload)
        item["score_detail"] = sd

        apply_board_weak_penalty_to_item(item, config=config)
