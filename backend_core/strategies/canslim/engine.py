# -*- coding: utf-8 -*-
"""CAN SLIM 选股引擎：C+A+N+S+L 合取，M 大盘开关。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from backend_core.strategies.canslim.config import merge_canslim_config
from backend_core.strategies.canslim.data_loader import CanSlimDataLoader

logger = logging.getLogger(__name__)


def _is_annual(end_date: str) -> bool:
    s = str(end_date or "")
    return len(s) >= 8 and s[4:8] == "1231"


def _pick_q_yoy(row: Dict[str, Any]) -> Optional[float]:
    for k in ("q_eps_yoy", "q_netprofit_yoy", "q_profit_yoy"):
        v = row.get(k)
        if v is not None:
            return float(v)
    return None


def _apply_qfq(
    bars: List[Dict[str, Any]], factors: List[Tuple[str, float]]
) -> List[Dict[str, Any]]:
    """P_qfq = P_raw * f_t / f_T。"""
    if not bars or not factors:
        return bars
    fmap = {d: f for d, f in factors}
    # forward-fill 因子
    dates = [b["date"] for b in bars if b.get("date")]
    if not dates:
        return bars
    sorted_f = sorted(factors, key=lambda x: x[0])
    filled: Dict[str, float] = {}
    fi = 0
    cur = None
    for d in sorted(dates):
        while fi < len(sorted_f) and sorted_f[fi][0] <= d:
            cur = sorted_f[fi][1]
            fi += 1
        if cur is not None:
            filled[d] = cur
    if not filled:
        return bars
    f_T = filled.get(dates[-1]) or sorted_f[-1][1]
    if not f_T:
        return bars
    out = []
    for b in bars:
        d = b.get("date")
        f = filled.get(d) if d else None
        nb = dict(b)
        if f is not None:
            ratio = f / f_T
            for k in ("open", "high", "low", "close"):
                if nb.get(k) is not None:
                    nb[k] = float(nb[k]) * ratio
        out.append(nb)
    return out


def _cagr(first: float, last: float, years: float) -> Optional[float]:
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    try:
        return (pow(last / first, 1.0 / years) - 1.0) * 100.0
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


class CanSlimEngine:
    def __init__(self, db: Session, config: Optional[Dict[str, Any]] = None):
        self.db = db
        self.cfg = merge_canslim_config(config)
        self.loader = CanSlimDataLoader(db)

    def _letter_enabled(self, letter: str) -> bool:
        return bool((self.cfg.get(letter) or {}).get("enabled", True))

    def _skip_letter(self, letter: str) -> Dict[str, Any]:
        return {
            "ok": True,
            "skipped": True,
            "enabled": False,
            "reason": f"{letter} 已关闭（不参与过滤）",
        }

    def _letter_result(
        self, letter: str, enabled: bool, evaluated: Dict[str, Any]
    ) -> Dict[str, Any]:
        """启用：原样返回评估结果；关闭：标记 skipped，但仍保留指标供表格展示。"""
        if enabled:
            out = dict(evaluated or {})
            out["enabled"] = True
            out["skipped"] = False
            return out
        out = self._skip_letter(letter)
        for k, v in (evaluated or {}).items():
            if k in ("ok", "skipped", "enabled", "reason"):
                continue
            out[k] = v
        return out

    @staticmethod
    def _peek_latest_roe(fina_rows: List[Dict[str, Any]]) -> Optional[float]:
        """从已加载财务行取最近年报 ROE（展示用，不参与过滤）。"""
        if not fina_rows:
            return None
        annuals = [r for r in fina_rows if _is_annual(r.get("end_date") or "")]
        candidates = annuals if annuals else list(fina_rows)
        for r in candidates:
            roe = r.get("roe_waa")
            if roe is None:
                roe = r.get("roe")
            if roe is not None:
                try:
                    return float(roe)
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _peek_q_eps_yoy(fina_rows: List[Dict[str, Any]]) -> Optional[float]:
        """从已加载财务行取最近一期季增%（展示用）。"""
        if not fina_rows:
            return None
        for r in fina_rows:
            y = _pick_q_yoy(r)
            if y is not None:
                return y
        return None

    def check_market(self, asof: str) -> Dict[str, Any]:
        mcfg = self.cfg.get("M") or {}
        if not mcfg.get("enabled", True):
            return {
                "ok": True,
                "enabled": False,
                "reason": "大盘过滤已关闭",
            }
        ts_code = str(mcfg.get("index_ts_code") or "000300.SH")
        win = int(mcfg.get("ma_window") or 50)
        slope_lb = int(mcfg.get("ma_slope_lookback") or 10)
        need = win + slope_lb + 2
        closes = self.loader.load_index_closes(ts_code, asof, limit=need + 10)
        vals = [c["close"] for c in closes if c.get("close") is not None]
        if len(vals) < need:
            return {
                "ok": False,
                "enabled": True,
                "index_ts_code": ts_code,
                "reason": f"指数日线不足（需≥{need}，有{len(vals)}）；请先跑 index_daily_cn",
            }
        ma_now = sum(vals[-win:]) / win
        ma_prev = sum(vals[-(win + slope_lb) : -slope_lb]) / win
        last_close = vals[-1]
        above = last_close > ma_now
        rising = ma_now > ma_prev
        ok = above and rising
        reason = (
            f"{ts_code} 收盘{last_close:.2f} {'>' if above else '≤'} MA{win}={ma_now:.2f}，"
            f"MA{win} {'上升' if rising else '未升'}（较{slope_lb}日前 {ma_prev:.2f}）"
        )
        return {
            "ok": ok,
            "enabled": True,
            "index_ts_code": ts_code,
            "close": last_close,
            "ma": ma_now,
            "ma_prev": ma_prev,
            "reason": reason if ok else f"大盘未确认上升：{reason}",
        }

    def eval_C(self, fina_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        ccfg = self.cfg.get("C") or {}
        min_yoy = float(ccfg.get("q_eps_yoy_min") or 25.0)
        # 最新非空单季同比行（优先非年报；若仅有年报也尝试 q_*）
        latest = None
        for row in fina_rows:
            yoy = _pick_q_yoy(row)
            if yoy is not None:
                latest = row
                break
        if latest is None:
            return {"ok": False, "reason": "无单季同比数据", "q_eps_yoy": None}
        yoy = _pick_q_yoy(latest)
        sales = latest.get("q_sales_yoy")
        ok = yoy is not None and yoy >= min_yoy
        if ok and ccfg.get("require_sales_yoy"):
            smin = float(ccfg.get("q_sales_yoy_min") or 20.0)
            if sales is None or sales < smin:
                ok = False
                return {
                    "ok": False,
                    "reason": f"营收同比 {sales} < {smin}%",
                    "q_eps_yoy": yoy,
                    "q_sales_yoy": sales,
                    "end_date": latest.get("end_date"),
                }
        return {
            "ok": bool(ok),
            "reason": f"单季同比 {yoy:.1f}% {'≥' if ok else '<'} {min_yoy}%" if yoy is not None else "缺同比",
            "q_eps_yoy": yoy,
            "q_sales_yoy": sales,
            "end_date": latest.get("end_date"),
        }

    def eval_A(self, fina_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        acfg = self.cfg.get("A") or {}
        years = int(acfg.get("annual_years") or 3)
        min_yoy = float(acfg.get("annual_eps_yoy_min") or 25.0)
        roe_min = float(acfg.get("roe_min") or 17.0)
        annuals = [r for r in fina_rows if _is_annual(r.get("end_date") or "")]
        # fina_rows 已按 end_date DESC
        annuals = annuals[: max(years + 1, 4)]

        def _roe_of(row: Optional[Dict[str, Any]]) -> Optional[float]:
            if not row:
                return None
            roe = row.get("roe_waa")
            if roe is None:
                roe = row.get("roe")
            try:
                return float(roe) if roe is not None else None
            except (TypeError, ValueError):
                return None

        if len(annuals) < years:
            return {
                "ok": False,
                "reason": f"年报不足{years}期（有{len(annuals)}）",
                "roe": _roe_of(annuals[0]) if annuals else self._peek_latest_roe(fina_rows),
            }
        take = annuals[:years]
        yoys = []
        for r in take:
            y = r.get("basic_eps_yoy")
            if y is None:
                y = r.get("dt_eps_yoy")
            yoys.append(float(y) if y is not None else None)

        growth_ok = all(y is not None and y >= min_yoy for y in yoys)
        cagr_val = None
        if not growth_ok and acfg.get("use_cagr_fallback", True):
            # 用更早一期 eps 与最近一期算 CAGR
            eps_list = [r.get("eps") for r in annuals if r.get("eps") is not None]
            if len(eps_list) >= years:
                cagr_val = _cagr(float(eps_list[years - 1]), float(eps_list[0]), float(years - 1) if years > 1 else 1.0)
                # 上面 annuals DESC：eps_list[0]=最新，eps_list[years-1]=较旧
                growth_ok = cagr_val is not None and cagr_val >= float(acfg.get("cagr_min") or min_yoy)

        latest = take[0]
        roe = _roe_of(latest)
        roe_ok = roe is not None and float(roe) >= roe_min
        ok = growth_ok and roe_ok
        reason_parts = []
        if growth_ok:
            if all(y is not None and y >= min_yoy for y in yoys):
                reason_parts.append(f"近{years}年EPS同比均≥{min_yoy}%")
            else:
                reason_parts.append(f"CAGR≈{cagr_val:.1f}%≥门槛")
        else:
            reason_parts.append(f"年增速未达标 yoy={yoys} cagr={cagr_val}")
        if roe_ok:
            reason_parts.append(f"ROE {roe:.1f}%≥{roe_min}%")
        else:
            reason_parts.append(f"ROE {roe} < {roe_min}%")
        return {
            "ok": bool(ok),
            "reason": "；".join(reason_parts),
            "annual_eps_yoys": yoys,
            "cagr": cagr_val,
            "roe": float(roe) if roe is not None else None,
            "end_dates": [r.get("end_date") for r in take],
        }

    def eval_N(
        self,
        bars_qfq: List[Dict[str, Any]],
        cupb: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        ncfg = self.cfg.get("N") or {}
        min_ratio = float(ncfg.get("near_high_min_ratio") or 0.85)
        lookback = int(ncfg.get("lookback_bars") or 252)
        near_ok = False
        ratio = None
        high_52 = None
        close = None
        if bars_qfq:
            window = bars_qfq[-lookback:] if len(bars_qfq) >= lookback else bars_qfq
            highs = [b["high"] for b in window if b.get("high") is not None]
            close = bars_qfq[-1].get("close")
            if highs and close is not None:
                high_52 = max(highs)
                if high_52 > 0:
                    ratio = float(close) / float(high_52)
                    near_ok = ratio >= min_ratio
        cupb_ok = False
        cupb_status = None
        if ncfg.get("allow_cupb", True) and cupb:
            allowed = {str(s).lower() for s in (ncfg.get("cupb_statuses") or ["forming", "confirmed"])}
            cupb_status = str(cupb.get("status") or "").lower()
            cupb_ok = cupb_status in allowed
        ok = near_ok or cupb_ok
        parts = []
        if ratio is not None:
            parts.append(f"距52周高 {ratio*100:.1f}%（门槛≥{min_ratio*100:.0f}%）")
        if cupb_status:
            parts.append(f"CUPB={cupb_status}")
        if not parts:
            parts.append("无价格/杯柄数据")
        return {
            "ok": bool(ok),
            "reason": ("新高或杯柄通过：" if ok else "未近新高且无杯柄：") + "；".join(parts),
            "near_high_ratio": ratio,
            "high_52w": high_52,
            "close": close,
            "cupb_status": cupb_status,
            "near_high_ok": near_ok,
            "cupb_ok": cupb_ok,
        }

    def eval_S(
        self,
        free_float_shares: Optional[float],
        last_bar: Optional[Dict[str, Any]],
        mavol: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        scfg = self.cfg.get("S") or {}
        max_yi = float(scfg.get("circ_shares_max_yi") or 20.0)
        circ_yi = None
        if free_float_shares is not None and free_float_shares > 0:
            circ_yi = float(free_float_shares) / 1e8
        size_ok = circ_yi is not None and circ_yi <= max_yi
        vol_ok = True
        vol_ratio = None
        if scfg.get("require_up_day_volume", True) and last_bar:
            o = last_bar.get("open")
            c = last_bar.get("close")
            vol = last_bar.get("volume")
            is_up = c is not None and o is not None and float(c) > float(o)
            if is_up:
                key = str(scfg.get("volume_vs_mavol") or "mavol20")
                base = None
                if mavol:
                    if key == "mavol20":
                        base = mavol.get("mavol20")
                    else:
                        base = mavol.get("mavol60") or mavol.get("mavol20")
                vmin = float(scfg.get("volume_ratio_min") or 1.0)
                if base and base > 0 and vol is not None:
                    vol_ratio = float(vol) / float(base)
                    vol_ok = vol_ratio >= vmin
                else:
                    vol_ok = False
        ok = size_ok and vol_ok
        parts = []
        if circ_yi is not None:
            parts.append(f"流通股{circ_yi:.2f}亿{'≤' if size_ok else '>'}{max_yi}")
        else:
            parts.append("缺流通股本")
        if vol_ratio is not None:
            parts.append(f"量/均量={vol_ratio:.2f}")
        elif scfg.get("require_up_day_volume", True):
            parts.append("阳量未校验或不足")
        return {
            "ok": bool(ok),
            "reason": "；".join(parts),
            "circ_shares_yi": circ_yi,
            "volume_ratio": vol_ratio,
        }

    def eval_L(self, rs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        lcfg = self.cfg.get("L") or {}
        min_rs = int(lcfg.get("rs_rating_min") or 80)
        strong = int(lcfg.get("rs_strong_min") or 90)
        if not rs or rs.get("rs_rating") is None:
            return {"ok": False, "reason": "无 RS Rating", "rs_rating": None}
        rating = int(rs["rs_rating"])
        ok = rating >= min_rs
        tag = "很强" if rating >= strong else ("偏强" if ok else "偏弱")
        return {
            "ok": ok,
            "reason": f"RS {rating} {'≥' if ok else '<'} {min_rs}（{tag}）",
            "rs_rating": rating,
            "rs_tag": tag,
            "rs_date": rs.get("date"),
        }

    def screen(
        self,
        *,
        asof: Optional[str] = None,
        codes: Optional[Sequence[str]] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if config_override:
            self.cfg = merge_canslim_config(config_override)
        asof_date = self.loader.resolve_asof_date(asof)
        market = self.check_market(asof_date)
        if market.get("enabled") and not market.get("ok"):
            return {
                "success": True,
                "asof": asof_date,
                "market": market,
                "total": 0,
                "data": [],
                "filters": self._active_filters_meta(),
                "message": market.get("reason") or "大盘未确认上升",
            }

        letter_keys = ("C", "A", "N", "S", "L")
        if not any(self._letter_enabled(k) for k in letter_keys):
            return {
                "success": True,
                "asof": asof_date,
                "market": market,
                "total": 0,
                "data": [],
                "filters": self._active_filters_meta(),
                "message": "请至少启用 C / A / N / S / L 中一项过滤条件",
            }

        need_c = self._letter_enabled("C")
        need_a = self._letter_enabled("A")
        need_n = self._letter_enabled("N")
        need_s = self._letter_enabled("S")
        need_l = self._letter_enabled("L")

        universe = self.loader.list_universe(exclude_st=bool((self.cfg.get("scan") or {}).get("exclude_st", True)))
        if codes:
            want = {str(c).strip().zfill(6) for c in codes}
            universe = [u for u in universe if u["code"] in want]

        code_list = [u["code"] for u in universe]
        name_map = {u["code"]: u for u in universe}
        # 展示列始终需要指标数据：财务 / RS / CUPB / 均量 一律加载；
        # 日K仅对通过前置过滤的候选再取，避免全市场无谓扫窗。
        fina_map = self.loader.load_latest_fina_by_codes(code_list)
        rs_map = self.loader.load_rs_map(asof_date)
        cupb_map = self.loader.load_cupb_codes(
            asof_date, (self.cfg.get("N") or {}).get("cupb_statuses") or ["forming", "confirmed"]
        )
        mavol_map = self.loader.load_mavol_map(asof_date, code_list)

        results: List[Dict[str, Any]] = []
        lookback = int((self.cfg.get("N") or {}).get("lookback_bars") or 252)
        use_qfq = bool((self.cfg.get("N") or {}).get("use_qfq", True))
        max_results = int((self.cfg.get("scan") or {}).get("max_results") or 0)

        for code in code_list:
            fina_rows = fina_map.get(code) or []
            c_eval = self.eval_C(fina_rows)
            if need_c and not c_eval.get("ok"):
                continue
            a_eval = self.eval_A(fina_rows)
            if need_a and not a_eval.get("ok"):
                continue
            l_eval = self.eval_L(rs_map.get(code))
            if need_l and not l_eval.get("ok"):
                continue

            bars = self.loader.load_quote_window(code, asof_date, lookback + 5)
            if use_qfq and bars:
                factors = self.loader.load_adj_factors(code)
                bars = _apply_qfq(bars, factors)
            n_eval = self.eval_N(bars, cupb_map.get(code))
            if need_n and not n_eval.get("ok"):
                continue
            last_bar = bars[-1] if bars else None
            s_eval = self.eval_S(
                (name_map.get(code) or {}).get("free_float_shares"),
                last_bar,
                mavol_map.get(code),
            )
            if need_s and not s_eval.get("ok"):
                continue

            c_res = self._letter_result("C", need_c, c_eval)
            a_res = self._letter_result("A", need_a, a_eval)
            n_res = self._letter_result("N", need_n, n_eval)
            s_res = self._letter_result("S", need_s, s_eval)
            l_res = self._letter_result("L", need_l, l_eval)

            info = name_map.get(code) or {}
            results.append(
                {
                    "code": code,
                    "name": info.get("name"),
                    "asof": asof_date,
                    "C": c_res,
                    "A": a_res,
                    "N": n_res,
                    "S": s_res,
                    "L": l_res,
                    "I": {"ok": None, "reason": "第一期未启用"},
                    "M": market,
                    "rs_rating": l_res.get("rs_rating"),
                    "near_high_pct": (
                        round(float(n_res["near_high_ratio"]) * 100, 2)
                        if n_res.get("near_high_ratio") is not None
                        else None
                    ),
                    "circ_shares_yi": s_res.get("circ_shares_yi"),
                    "volume_ratio": s_res.get("volume_ratio"),
                    "q_eps_yoy": c_res.get("q_eps_yoy"),
                    "roe": a_res.get("roe"),
                    "cupb_status": n_res.get("cupb_status"),
                }
            )
            if max_results > 0 and len(results) >= max_results:
                break

        # RS 降序
        results.sort(key=lambda x: (x.get("rs_rating") or 0), reverse=True)
        return {
            "success": True,
            "asof": asof_date,
            "market": market,
            "total": len(results),
            "data": results,
            "filters": self._active_filters_meta(),
            "message": None,
        }

    def _active_filters_meta(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in ("C", "A", "N", "S", "L", "M"):
            out[k] = {"enabled": self._letter_enabled(k)}
        return out
