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


def _roe_raw(row: Optional[Dict[str, Any]]) -> Optional[float]:
    if not row:
        return None
    roe = row.get("roe_waa")
    if roe is None:
        roe = row.get("roe")
    try:
        return float(roe) if roe is not None else None
    except (TypeError, ValueError):
        return None


def _annualize_roe(roe: float, end_date: str) -> float:
    """东财摘要里的中报/季报 ROE 多为累计值，按报告期粗略年化后与年报门槛比较。"""
    s = str(end_date or "")
    if len(s) < 8:
        return float(roe)
    md = s[4:8]
    if md == "1231":
        return float(roe)
    if md == "0331":
        return float(roe) * 4.0
    if md == "0630":
        return float(roe) * 2.0
    if md == "0930":
        return float(roe) * (4.0 / 3.0)
    return float(roe)


def _pick_roe_for_a(
    fina_rows: List[Dict[str, Any]],
    *,
    source: str = "freshest_annualized",
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """
    返回 (用于门槛的 ROE, 报告期 end_date, 原始未年化 ROE)。
    fina_rows 约定按 end_date DESC。
    """
    src = (source or "freshest_annualized").strip().lower()
    if src in ("annual", "year", "latest_annual"):
        for r in fina_rows:
            if not _is_annual(r.get("end_date") or ""):
                continue
            raw = _roe_raw(r)
            if raw is not None:
                return raw, str(r.get("end_date") or "") or None, raw
        return None, None, None

    # freshest_annualized：最新一期有 ROE 的报告（含季报/中报，累计 ROE 年化）
    for r in fina_rows:
        raw = _roe_raw(r)
        if raw is None:
            continue
        end = str(r.get("end_date") or "")
        return _annualize_roe(raw, end), end or None, raw
    return None, None, None


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
        """展示用：优先最新报告期 ROE（中报/季报做年化），否则回退年报。"""
        roe, _, _ = _pick_roe_for_a(fina_rows, source="freshest_annualized")
        return roe

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
        require_growth = bool(acfg.get("require_annual_growth", True))
        roe_source = str(acfg.get("roe_source") or "freshest_annualized")
        annuals = [r for r in fina_rows if _is_annual(r.get("end_date") or "")]
        # fina_rows 已按 end_date DESC
        annuals = annuals[: max(years + 1, 4)]

        roe, roe_end, roe_raw = _pick_roe_for_a(fina_rows, source=roe_source)
        roe_ok = roe is not None and float(roe) >= roe_min

        # 仅 ROE：不要求年报期数与年增速
        if not require_growth:
            reason = (
                f"仅ROE {roe:.1f}%@{roe_end or '?'}≥{roe_min}%"
                if roe_ok and roe is not None
                else f"ROE {roe}@{roe_end} < {roe_min}%"
            )
            return {
                "ok": bool(roe_ok),
                "reason": reason,
                "annual_eps_yoys": [],
                "cagr": None,
                "roe": float(roe) if roe is not None else None,
                "roe_raw": float(roe_raw) if roe_raw is not None else None,
                "roe_end_date": roe_end,
                "end_dates": [],
                "require_annual_growth": False,
            }

        if len(annuals) < years:
            return {
                "ok": False,
                "reason": f"年报不足{years}期（有{len(annuals)}）",
                "roe": roe,
                "roe_raw": roe_raw,
                "roe_end_date": roe_end,
                "require_annual_growth": True,
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
            period = roe_end or "?"
            if roe_raw is not None and roe_end and not _is_annual(roe_end) and abs(float(roe) - float(roe_raw)) > 1e-6:
                reason_parts.append(
                    f"ROE(年化) {roe:.1f}%←{roe_raw:.1f}%@{period}≥{roe_min}%"
                )
            else:
                reason_parts.append(f"ROE {roe:.1f}%@{period}≥{roe_min}%")
        else:
            reason_parts.append(f"ROE {roe}@{roe_end} < {roe_min}%")
        return {
            "ok": bool(ok),
            "reason": "；".join(reason_parts),
            "annual_eps_yoys": yoys,
            "cagr": cagr_val,
            "roe": float(roe) if roe is not None else None,
            "roe_raw": float(roe_raw) if roe_raw is not None else None,
            "roe_end_date": roe_end,
            "end_dates": [r.get("end_date") for r in take],
            "require_annual_growth": True,
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
        need_quotes = need_n or need_s

        universe = self.loader.list_universe(exclude_st=bool((self.cfg.get("scan") or {}).get("exclude_st", True)))
        if codes:
            want = {str(c).strip().zfill(6) for c in codes}
            universe = [u for u in universe if u["code"] in want]

        code_list = [u["code"] for u in universe]
        name_map = {u["code"]: u for u in universe}
        fina_map = self.loader.load_latest_fina_by_codes(code_list)
        rs_map = self.loader.load_rs_map(asof_date)
        cupb_map = (
            self.loader.load_cupb_codes(
                asof_date, (self.cfg.get("N") or {}).get("cupb_statuses") or ["forming", "confirmed"]
            )
            if need_n
            else {}
        )
        # mavol 仅对过 C/A/L 的候选批量取，避免全市场扫表

        results: List[Dict[str, Any]] = []
        lookback = int((self.cfg.get("N") or {}).get("lookback_bars") or 252)
        use_qfq = bool((self.cfg.get("N") or {}).get("use_qfq", True))
        max_results = int((self.cfg.get("scan") or {}).get("max_results") or 0)

        # 漏斗统计（0 结果时回传，便于排查）
        stats = {
            "universe": len(code_list),
            "pass_c": 0,
            "pass_a": 0,
            "pass_l": 0,
            "pass_n": 0,
            "pass_s": 0,
            "fail_c": 0,
            "fail_a": 0,
            "fail_l": 0,
            "fail_n": 0,
            "fail_s": 0,
            "no_fina": 0,
            "quote_candidates": 0,
        }

        # 第一阶段：C/A/L（不读日 K）
        phase1: List[Dict[str, Any]] = []
        for code in code_list:
            fina_rows = fina_map.get(code) or []
            if not fina_rows:
                stats["no_fina"] += 1
            c_eval = self.eval_C(fina_rows)
            if need_c:
                if not c_eval.get("ok"):
                    stats["fail_c"] += 1
                    continue
                stats["pass_c"] += 1
            a_eval = self.eval_A(fina_rows)
            if need_a:
                if not a_eval.get("ok"):
                    stats["fail_a"] += 1
                    continue
                stats["pass_a"] += 1
            l_eval = self.eval_L(rs_map.get(code))
            if need_l:
                if not l_eval.get("ok"):
                    stats["fail_l"] += 1
                    continue
                stats["pass_l"] += 1
            phase1.append(
                {
                    "code": code,
                    "c_eval": c_eval,
                    "a_eval": a_eval,
                    "l_eval": l_eval,
                }
            )

        # 第二阶段：仅对候选批量取日 K / 量能，再评 N/S
        cand_codes = [p["code"] for p in phase1]
        stats["quote_candidates"] = len(cand_codes)
        quote_map: Dict[str, List[Dict[str, Any]]] = {}
        mavol_map: Dict[str, Dict[str, Any]] = {}
        if need_quotes and cand_codes:
            quote_map = self.loader.load_quote_windows_batch(cand_codes, asof_date, lookback + 5)
            if use_qfq:
                adj_map = self.loader.load_adj_factors_batch(cand_codes)
                for c in cand_codes:
                    bars = quote_map.get(c) or []
                    if bars:
                        quote_map[c] = _apply_qfq(bars, adj_map.get(c) or [])
            if need_s:
                mavol_map = self.loader.load_mavol_map(asof_date, cand_codes)

        for item in phase1:
            code = item["code"]
            c_eval = item["c_eval"]
            a_eval = item["a_eval"]
            l_eval = item["l_eval"]

            if need_quotes:
                bars = quote_map.get(code) or []
                n_eval = self.eval_N(bars, cupb_map.get(code))
                if need_n and not n_eval.get("ok"):
                    stats["fail_n"] += 1
                    continue
                if need_n:
                    stats["pass_n"] += 1
                last_bar = bars[-1] if bars else None
                s_eval = self.eval_S(
                    (name_map.get(code) or {}).get("free_float_shares"),
                    last_bar,
                    mavol_map.get(code),
                )
                if need_s and not s_eval.get("ok"):
                    stats["fail_s"] += 1
                    continue
                if need_s:
                    stats["pass_s"] += 1
            else:
                # N/S 均关闭：不扫日K
                ff = (name_map.get(code) or {}).get("free_float_shares")
                circ_yi = (float(ff) / 1e8) if ff else None
                n_eval = {
                    "ok": True,
                    "reason": "N 未启用",
                    "near_high_ratio": None,
                    "high_52w": None,
                    "close": None,
                    "cupb_status": None,
                    "near_high_ok": False,
                    "cupb_ok": False,
                }
                s_eval = {
                    "ok": True,
                    "reason": "S 未启用",
                    "circ_shares_yi": circ_yi,
                    "volume_ratio": None,
                }

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
                    "roe_end_date": a_res.get("roe_end_date"),
                    "cupb_status": n_res.get("cupb_status"),
                }
            )
            if max_results > 0 and len(results) >= max_results:
                break

        # RS 降序
        results.sort(key=lambda x: (x.get("rs_rating") or 0), reverse=True)
        message = None
        if not results:
            parts = [f"股票池{stats['universe']}"]
            if need_c:
                parts.append(f"过C {stats['pass_c']}（未过{stats['fail_c']}）")
            if need_a:
                parts.append(
                    f"过A {stats['pass_a']}（未过{stats['fail_a']}；A=近3年年报增速+ROE，不单是ROE）"
                )
            if need_l:
                parts.append(f"过L {stats['pass_l']}（未过{stats['fail_l']}）")
            if need_n:
                parts.append(f"过N {stats['pass_n']}（未过{stats['fail_n']}）")
            if need_s:
                parts.append(f"过S {stats['pass_s']}（未过{stats['fail_s']}）")
            if stats["no_fina"]:
                parts.append(f"无财务{stats['no_fina']}")
            message = "无符合条件的股票。漏斗：" + " → ".join(parts)

        return {
            "success": True,
            "asof": asof_date,
            "market": market,
            "total": len(results),
            "data": results,
            "filters": self._active_filters_meta(),
            "diagnostics": stats,
            "message": message,
        }

    def _active_filters_meta(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in ("C", "A", "N", "S", "L", "M"):
            out[k] = {"enabled": self._letter_enabled(k)}
        return out
