# -*- coding: utf-8 -*-
"""LDS 选股引擎：编排总龙 + 板龙，再打分。"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.board_roles.service import (
    extract_leader_mid_from_payload,
    fetch_board_roles_payload,
)
from backend_core.market_review.market_leader import pick_market_leader
from backend_core.market_review.rules import yuan_to_yi
from backend_core.strategies.double_bottom.data_loader import resolve_effective_trade_date
from backend_core.strategies.double_bottom.universe import resolve_stock_pool

from .config import LdsConfigManager, get_default_lds_config
from .detector import evaluate_candidate, merge_hits_by_code

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _is_st_name(name: str) -> bool:
    n = (name or "").upper().replace(" ", "")
    return n.startswith("ST") or n.startswith("*ST") or "ST" in n[:4]


class LdsStrategyEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_lds_config()

    def _load_zt_rows(self, db: Session, trade_date: str) -> List[Dict[str, Any]]:
        d = trade_date[:10]
        try:
            rows = db.execute(
                text(
                    """
                    SELECT code, name, change_percent, seal_fund, board_count, industry
                    FROM stock_zt_pool_daily
                    WHERE trade_date = :d
                    """
                ),
                {"d": d},
            ).fetchall()
        except Exception:
            logger.exception("LDS 涨停池加载失败")
            db.rollback()
            return []
        out = []
        for code, name, chg, seal, bc, industry in rows:
            out.append(
                {
                    "code": str(code).zfill(6) if str(code).isdigit() else str(code),
                    "name": str(name or code),
                    "change_percent": _f(chg),
                    "seal_fund": seal,
                    "board_count": int(bc or 0),
                    "industry": industry,
                    "amount": None,
                }
            )
        return out

    def _height_code(self, zt_rows: List[Dict[str, Any]]) -> Optional[str]:
        best = None
        max_bc = -1
        for r in zt_rows:
            bc = int(r.get("board_count") or 0)
            if bc > max_bc:
                max_bc = bc
                best = r.get("code")
        return best

    def _mv_yi_map(self, db: Session, codes: Sequence[str]) -> Dict[str, float]:
        if not codes:
            return {}
        from sqlalchemy import bindparam

        out: Dict[str, float] = {}
        uniq = [str(c) for c in dict.fromkeys(codes)]
        for i in range(0, len(uniq), 200):
            chunk = uniq[i : i + 200]
            try:
                stmt = text(
                    """
                    SELECT code, circulating_market_value
                    FROM stock_realtime_quote
                    WHERE code IN :codes
                      AND trade_date = (
                        SELECT MAX(trade_date) FROM stock_realtime_quote
                        WHERE change_percent IS NOT NULL
                      )
                    """
                ).bindparams(bindparam("codes", expanding=True))
                rows = db.execute(stmt, {"codes": chunk}).fetchall()
            except Exception:
                logger.debug("LDS 市值查询失败，回退空", exc_info=True)
                db.rollback()
                return out
            for code, mv in rows:
                c = str(code).zfill(6) if str(code).isdigit() else str(code)
                yi = yuan_to_yi(mv)
                if yi is not None:
                    out[c] = float(yi)
        return out

    def _flow_map(self, db: Session, trade_date: str, codes: Sequence[str]) -> Dict[str, float]:
        if not codes:
            return {}
        out: Dict[str, float] = {}
        uniq = [str(c) for c in dict.fromkeys(codes)]
        from sqlalchemy import bindparam

        for i in range(0, len(uniq), 200):
            chunk = uniq[i : i + 200]
            try:
                stmt = text(
                    """
                    SELECT code, net_amount
                    FROM stock_fund_flow_daily
                    WHERE trade_date = :d AND code IN :codes
                    """
                ).bindparams(bindparam("codes", expanding=True))
                rows = db.execute(stmt, {"d": trade_date[:10], "codes": chunk}).fetchall()
            except Exception:
                db.rollback()
                return out
            for code, net in rows:
                c = str(code).zfill(6) if str(code).isdigit() else str(code)
                yi = yuan_to_yi(net)
                if yi is not None:
                    out[c] = float(yi)
        return out

    def _board_stats_from_payload(
        self, payload: Dict[str, Any]
    ) -> Tuple[int, float, Optional[float], Dict[str, Dict[str, Any]]]:
        stocks = list(payload.get("stocks") or [])
        by_code: Dict[str, Dict[str, Any]] = {}
        chgs: List[float] = []
        zt_n = 0
        up_n = 0
        for s in stocks:
            code = str(s.get("code") or "").zfill(6)
            if not code:
                continue
            by_code[code] = s
            chg = _f(s.get("change_percent"))
            if chg is None:
                continue
            chgs.append(chg)
            if chg > 0:
                up_n += 1
            # 粗涨停
            thr = 19.5 if code.startswith(("300", "301", "688")) else 9.5
            if chg >= thr:
                zt_n += 1
        up_ratio = (up_n / len(chgs)) if chgs else 0.0
        median = statistics.median(chgs) if chgs else None
        return zt_n, up_ratio, median, by_code

    def _resolve_boards(
        self,
        db: Session,
        *,
        trade_date: str,
        pool: Dict[str, Any],
        scan: Dict[str, Any],
        industry_board_codes: Optional[Sequence[Any]],
        concept_board_codes: Optional[Sequence[Any]],
    ) -> List[Dict[str, str]]:
        """返回 [{board_type, board_code, board_name}]"""
        max_boards = max(1, int(scan.get("max_boards") or 20))
        boards: List[Dict[str, str]] = []
        seen: Set[str] = set()

        def _add(bt: str, code: str, name: str = "") -> None:
            key = f"{bt}:{code}"
            if not code or key in seen:
                return
            seen.add(key)
            boards.append({"board_type": bt, "board_code": str(code), "board_name": name or ""})

        for c in concept_board_codes or []:
            _add("concept", str(c))
        for c in industry_board_codes or []:
            _add("industry", str(c))

        # 池内板标签
        boards_by = pool.get("boards_by_code") or {}
        for _code, blist in boards_by.items():
            for b in blist or []:
                if isinstance(b, dict):
                    bt = str(b.get("board_type") or b.get("type") or "concept")
                    bc = str(b.get("board_code") or b.get("code") or "")
                    bn = str(b.get("board_name") or b.get("name") or "")
                    if bc:
                        _add(bt if bt in ("industry", "concept") else "concept", bc, bn)

        # 复盘主线：当日概念/行业命中（可选）
        if str(scan.get("board_scope") or "") == "mainline_plus_pool":
            try:
                rows = db.execute(
                    text(
                        """
                        SELECT board_type, board_code, board_name
                        FROM market_daily_mainline_hits
                        WHERE trade_date = :d
                        ORDER BY board_type, board_code
                        LIMIT :lim
                        """
                    ),
                    {"d": trade_date[:10], "lim": max_boards},
                ).fetchall()
                for bt, bc, bn in rows:
                    if str(bt) in ("concept", "industry") and bc:
                        _add(str(bt), str(bc), str(bn or ""))
            except Exception:
                logger.debug("LDS 主线命中表不可用", exc_info=True)
                db.rollback()

        return boards[:max_boards]

    def screen(
        self,
        db: Session,
        *,
        trade_date: Optional[str] = None,
        config_id: Optional[int] = None,
        stock_pool_mode: str = "stocks",
        industry_board_codes: Optional[Sequence[Any]] = None,
        concept_board_codes: Optional[Sequence[Any]] = None,
        stock_codes: Optional[Sequence[Any]] = None,
        universe_limit: Optional[int] = None,
        max_results: Optional[int] = None,
        force_recompute: bool = False,
    ) -> Dict[str, Any]:
        cm = LdsConfigManager()
        cid = int(config_id) if config_id is not None else None
        cfg = cm.get_config(cid) if cid is not None else (
            self.config if self.config else cm.get_config(None)
        )
        if cid is None:
            try:
                cid = int(cfg.get("_config_id") or cm.get_default_config_id())
            except Exception:
                cid = cm.get_default_config_id()

        scan = dict(cfg.get("scan") or {})
        date_s = resolve_effective_trade_date(db, trade_date)
        pool = resolve_stock_pool(
            db,
            stock_pool_mode=stock_pool_mode,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
            stock_codes=stock_codes,
            universe_limit=universe_limit if (universe_limit or 0) > 0 else None,
        )
        codes: List[str] = list(pool["codes"] or [])
        scope_set = set(codes)
        empty = {
            "trade_date": date_s,
            "config_id": cid,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": 0,
            "hit_count": 0,
            "items": [],
            "force_recompute": bool(force_recompute),
            "scope_codes": codes,
        }
        if not codes and stock_pool_mode != "market":
            # 全市场时 resolve 可能很大；若为空仍继续用涨停池
            pass

        zt_rows = self._load_zt_rows(db, date_s)
        height_code = self._height_code(zt_rows)
        max_board = max((int(r.get("board_count") or 0) for r in zt_rows), default=0) or 1

        # 主线名：优先行业板名
        main_name = None
        if industry_board_codes:
            main_name = str(industry_board_codes[0])
        ml = pick_market_leader(zt_rows, main_name=None)
        candidates: List[Dict[str, Any]] = []

        # —— 板龙 ——
        boards = self._resolve_boards(
            db,
            trade_date=date_s,
            pool=pool,
            scan=scan,
            industry_board_codes=industry_board_codes,
            concept_board_codes=concept_board_codes,
        )
        on_mainline_boards = {b["board_code"] for b in boards}

        for b in boards:
            try:
                payload = fetch_board_roles_payload(
                    db,
                    board_type=b["board_type"],
                    board_code=b["board_code"],
                    board_name=b.get("board_name") or None,
                )
            except Exception:
                logger.debug("LDS board_roles 失败 %s", b, exc_info=True)
                db.rollback()
                continue
            if not payload:
                continue
            roles = extract_leader_mid_from_payload(payload)
            zt_n, up_ratio, median, by_code = self._board_stats_from_payload(payload)
            bname = roles.get("board_name") or b.get("board_name") or payload.get("board_name") or ""
            for lead in roles.get("leaders") or []:
                code = str(lead.get("code") or "").zfill(6)
                if scope_set and code not in scope_set and stock_pool_mode != "market":
                    # 池外板龙：若池非空且非全市场，跳过
                    if codes:
                        continue
                row = by_code.get(code) or {}
                name = str(lead.get("name") or row.get("name") or code)
                if scan.get("exclude_st", True) and _is_st_name(name):
                    continue
                chg = _f(lead.get("change_percent") if lead.get("change_percent") is not None else row.get("change_percent")) or 0.0
                amt = _f(row.get("amount")) or 0.0
                candidates.append(
                    {
                        "code": code,
                        "name": name,
                        "role": "board_leader",
                        "board_code": b["board_code"],
                        "board_name": bname,
                        "board_count": next(
                            (int(z["board_count"]) for z in zt_rows if z["code"] == code),
                            0,
                        ),
                        "change_percent": chg,
                        "amount": amt,
                        "board_role_score": _f(lead.get("board_role_score")) or 0.0,
                        "zt_n": zt_n,
                        "up_ratio": up_ratio,
                        "board_median_chg": median,
                        "had_bomb_weak_board": False,
                        "amount_pctile": min(100.0, (amt / 5e8) * 50.0) if amt else 40.0,
                        "height_pctile": 100.0
                        * (
                            next((int(z["board_count"]) for z in zt_rows if z["code"] == code), 0)
                            / max_board
                        ),
                        "seal_yi": yuan_to_yi(
                            next((z.get("seal_fund") for z in zt_rows if z["code"] == code), None)
                        )
                        or 0.0,
                        "is_height_stock": code == height_code,
                        "had_diverge": False,
                        "on_mainline": b["board_code"] in on_mainline_boards,
                        "is_primary": True,
                    }
                )

        # —— 总龙 ——
        if ml:
            code = str(ml["code"]).zfill(6)
            if (not codes) or code in scope_set or stock_pool_mode == "market":
                name = str(ml.get("name") or code)
                if not (scan.get("exclude_st", True) and _is_st_name(name)):
                    zt = next((z for z in zt_rows if z["code"] == code), {})
                    # 用主线板统计作带动代理：取第一块板
                    zt_n, up_ratio, median = 1, 0.2, 0.0
                    if boards:
                        try:
                            payload = fetch_board_roles_payload(
                                db,
                                board_type=boards[0]["board_type"],
                                board_code=boards[0]["board_code"],
                            )
                            if payload:
                                zt_n, up_ratio, median, _ = self._board_stats_from_payload(payload)
                        except Exception:
                            db.rollback()
                    candidates.append(
                        {
                            "code": code,
                            "name": name,
                            "role": "market_leader",
                            "board_code": "",
                            "board_name": "",
                            "board_count": ml.get("board_count"),
                            "change_percent": _f(zt.get("change_percent")) or 10.0,
                            "amount": _f(zt.get("amount")) or 0.0,
                            "board_role_score": None,
                            "market_leader_score": ml.get("score"),
                            "zt_n": max(zt_n, int(ml.get("board_count") or 1)),
                            "up_ratio": max(up_ratio, 0.35),
                            "board_median_chg": median if median is not None else 1.0,
                            "had_bomb_weak_board": False,
                            "amount_pctile": 70.0,
                            "height_pctile": 100.0
                            * (int(ml.get("board_count") or 0) / max_board),
                            "seal_yi": ml.get("seal_yi") or 0.0,
                            "is_height_stock": code == height_code,
                            "had_diverge": int(ml.get("board_count") or 0) >= 2,
                            "on_mainline": True,
                            "is_primary": True,
                        }
                    )
                    for alt in ml.get("alternates") or []:
                        ac = str(alt.get("code") or "").zfill(6)
                        if not ac or ac == code:
                            continue
                        if codes and ac not in scope_set and stock_pool_mode != "market":
                            continue
                        candidates.append(
                            {
                                "code": ac,
                                "name": str(alt.get("name") or ac),
                                "role": "market_leader",
                                "board_code": "",
                                "board_name": "",
                                "board_count": alt.get("board_count"),
                                "change_percent": 9.9,
                                "amount": 0.0,
                                "board_role_score": None,
                                "market_leader_score": alt.get("score"),
                                "zt_n": zt_n,
                                "up_ratio": up_ratio,
                                "board_median_chg": median,
                                "had_bomb_weak_board": False,
                                "amount_pctile": 55.0,
                                "height_pctile": 100.0
                                * (int(alt.get("board_count") or 0) / max_board),
                                "seal_yi": 0.0,
                                "is_height_stock": ac == height_code,
                                "had_diverge": True,
                                "on_mainline": True,
                                "is_primary": False,
                            }
                        )

        all_codes = list({c["code"] for c in candidates})
        mv_map = self._mv_yi_map(db, all_codes)
        flow_map = self._flow_map(db, date_s, all_codes)
        for c in candidates:
            c["mv_yi"] = mv_map.get(c["code"], 50.0)  # 缺市值时给中性默认避免全灭
            c["net_inflow_yi"] = flow_map.get(c["code"])
            # 量比代理：有净流入则偏高
            if c.get("net_inflow_yi") is not None and float(c["net_inflow_yi"]) > 0:
                c["vol_ratio_actual"] = 2.0
            else:
                c["vol_ratio_actual"] = 1.0
            # 分歧：连板≥2 或 非首板
            if int(c.get("board_count") or 0) >= 2:
                c["had_diverge"] = True

        raw_items: List[Dict[str, Any]] = []
        for c in candidates:
            hit = evaluate_candidate(c, cfg=cfg)
            if not hit:
                continue
            hit["date"] = date_s
            hit["trade_date"] = date_s
            raw_items.append(hit)

        items = merge_hits_by_code(raw_items)
        cap = max_results if max_results is not None else int(scan.get("max_results") or 0)
        if cap and cap > 0:
            items = items[: int(cap)]

        return {
            "trade_date": date_s,
            "config_id": cid,
            "scope_meta": pool.get("scope_meta") or {},
            "screened": len(candidates),
            "hit_count": len(items),
            "raw_hit_count": len(raw_items),
            "items": items,
            "force_recompute": bool(force_recompute),
            "scope_codes": codes or all_codes,
            "boards_scanned": len(boards),
        }
