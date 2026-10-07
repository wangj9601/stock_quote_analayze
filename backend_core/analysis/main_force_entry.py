# -*- coding: utf-8 -*-
"""主力入场判定：东财主力净流入窗口 + 净流入加权均价 + Volume Profile 旁证。

口径：主力 = 东财按成交额分档推断的主力净流入（≈超大单+大单），非账户归属。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.analysis.volume_profile import compute_volume_profile_from_bars

DEFAULT_LOOKBACK_DAYS = 60
PARTICIPATION_MIN = 0.03  # 主力净流入 / 成交额
MIN_STREAK_DAYS = 2
ROLL_WINDOW = 5
ROLL_MIN_ENTRY_DAYS = 3
HIGH_CATCH_PCT = 0.03  # 成本重心高于末收盘超过 3% → high_catch

DISCLAIMER = (
    "订单分档代理，非机构身份；价位为加权均价近似，非筹码分布"
)

VERDICT_LABELS = {
    "accumulating": "放量建仓",
    "high_catch": "高位承接",
    "pulse": "脉冲流入",
    "net_outflow": "净流出",
    "insufficient_data": "数据不足",
}


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def vwap_from_bar(bar: Dict[str, Any]) -> Optional[float]:
    """amount / volume / 100；volume 为手。"""
    amount = _f(bar.get("amount"))
    volume = _f(bar.get("volume"))
    if amount is None or volume is None or volume <= 0:
        # 回退 close / current_price
        return _f(bar.get("close")) or _f(bar.get("current_price"))
    return amount / volume / 100.0


def is_entry_day(
    main_net: Optional[float],
    turnover: Optional[float],
    *,
    participation_min: float = PARTICIPATION_MIN,
) -> bool:
    if main_net is None or main_net <= 0:
        return False
    if turnover is None or turnover <= 0:
        # 无成交额时仅要求主力净流入为正
        return True
    return (main_net / turnover) >= participation_min


def find_entry_windows(
    dates: Sequence[str],
    main_nets: Sequence[Optional[float]],
    entry_flags: Sequence[bool],
) -> List[Dict[str, Any]]:
    n = len(dates)
    covered = [False] * n
    windows: List[Dict[str, Any]] = []

    # 1) 连续入场日
    i = 0
    while i < n:
        if not entry_flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and entry_flags[j + 1]:
            j += 1
        if j - i + 1 >= MIN_STREAK_DAYS:
            windows.append({"start_i": i, "end_i": j, "kind": "streak"})
            for k in range(i, j + 1):
                covered[k] = True
        i = j + 1

    # 2) 滚动窗口
    for end in range(n):
        start = max(0, end - ROLL_WINDOW + 1)
        nets = [_f(main_nets[k]) or 0.0 for k in range(start, end + 1)]
        entries = sum(1 for k in range(start, end + 1) if entry_flags[k])
        if sum(nets) > 0 and entries >= ROLL_MIN_ENTRY_DAYS:
            # 避免与已覆盖 streak 完全重叠的琐碎窗
            if any(not covered[k] for k in range(start, end + 1) if entry_flags[k]):
                windows.append({"start_i": start, "end_i": end, "kind": "roll"})
                for k in range(start, end + 1):
                    covered[k] = covered[k] or entry_flags[k]

    # 合并重叠窗
    if not windows:
        return []
    windows.sort(key=lambda w: (w["start_i"], w["end_i"]))
    merged: List[Dict[str, Any]] = [dict(windows[0])]
    for w in windows[1:]:
        last = merged[-1]
        if w["start_i"] <= last["end_i"] + 1:
            last["end_i"] = max(last["end_i"], w["end_i"])
        else:
            merged.append(dict(w))
    return merged


def compute_cost_center(
    indices: Sequence[int],
    main_nets: Sequence[Optional[float]],
    vwaps: Sequence[Optional[float]],
    highs: Sequence[Optional[float]],
    lows: Sequence[Optional[float]],
) -> Dict[str, Optional[float]]:
    num = 0.0
    den = 0.0
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    for i in indices:
        mn = _f(main_nets[i])
        vw = _f(vwaps[i])
        if mn is None or mn <= 0 or vw is None:
            continue
        num += mn * vw
        den += mn
        lo = _f(lows[i])
        hi = _f(highs[i])
        if lo is not None:
            price_low = lo if price_low is None else min(price_low, lo)
        if hi is not None:
            price_high = hi if price_high is None else max(price_high, hi)
    cost = (num / den) if den > 0 else None
    return {
        "cost_center": cost,
        "price_low": price_low,
        "price_high": price_high,
        "main_net_sum": den if den > 0 else 0.0,
    }


def classify_verdict(
    *,
    windows: Sequence[Dict[str, Any]],
    entry_flags: Sequence[bool],
    main_nets: Sequence[Optional[float]],
    closes: Sequence[Optional[float]],
    volumes: Sequence[Optional[float]],
    cost_center: Optional[float],
    last_close: Optional[float],
) -> str:
    nets = [_f(x) or 0.0 for x in main_nets]
    if not main_nets or all(_f(x) is None for x in main_nets):
        return "insufficient_data"
    total = sum(nets)
    entry_count = sum(1 for f in entry_flags if f)

    if not windows:
        if entry_count == 1 and total > 0:
            return "pulse"
        if total <= 0:
            return "net_outflow"
        if entry_count == 0:
            return "net_outflow" if total <= 0 else "pulse"
        return "pulse"

    # 有窗口
    if (
        cost_center is not None
        and last_close is not None
        and last_close > 0
        and (cost_center - last_close) / last_close >= HIGH_CATCH_PCT
    ):
        return "high_catch"

    w = windows[-1]
    si, ei = w["start_i"], w["end_i"]
    c0 = _f(closes[si])
    c1 = _f(closes[ei])
    vol_slice = [_f(volumes[k]) or 0.0 for k in range(si, ei + 1)]
    vol_up = False
    if len(vol_slice) >= 2:
        mid = len(vol_slice) // 2
        vol_up = (sum(vol_slice[mid:]) / max(1, len(vol_slice) - mid)) > (
            sum(vol_slice[:mid]) / max(1, mid)
        )
    if c0 is not None and c1 is not None and c1 >= c0 and vol_up:
        return "accumulating"
    if c0 is not None and c1 is not None and c1 >= c0:
        return "accumulating"
    return "high_catch" if cost_center and last_close and cost_center > last_close else "accumulating"


def compute_main_force_entry(
    *,
    code: str,
    em_rows: Sequence[Dict[str, Any]],
    quote_rows: Sequence[Dict[str, Any]],
    ths_net_by_date: Optional[Dict[str, float]] = None,
    board_main_nets: Optional[Sequence[float]] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    participation_min: float = PARTICIPATION_MIN,
) -> Dict[str, Any]:
    """
    em_rows: 需含 trade_date, main_net_inflow；可选 close_price
    quote_rows: 需含 trade_date/date, amount, volume, high, low, close
    """
    lb = max(5, int(lookback_days or DEFAULT_LOOKBACK_DAYS))
    # 对齐为按日期升序的联合序列（以 em 为主）
    em_sorted = sorted(
        [r for r in em_rows if r.get("trade_date") or r.get("date")],
        key=lambda r: str(r.get("trade_date") or r.get("date"))[:10],
    )
    if len(em_sorted) > lb:
        em_sorted = em_sorted[-lb:]

    qmap: Dict[str, Dict[str, Any]] = {}
    for r in quote_rows:
        d = str(r.get("trade_date") or r.get("date") or "")[:10]
        if d:
            qmap[d] = r

    dates: List[str] = []
    main_nets: List[Optional[float]] = []
    turnovers: List[Optional[float]] = []
    vwaps: List[Optional[float]] = []
    highs: List[Optional[float]] = []
    lows: List[Optional[float]] = []
    closes: List[Optional[float]] = []
    volumes: List[Optional[float]] = []
    bars_for_vp: List[Dict[str, Any]] = []

    for r in em_sorted:
        d = str(r.get("trade_date") or r.get("date"))[:10]
        q = qmap.get(d) or {}
        mn = _f(r.get("main_net_inflow"))
        amount = _f(q.get("amount"))
        vol = _f(q.get("volume"))
        close = _f(q.get("close")) or _f(r.get("close_price"))
        high = _f(q.get("high")) or close
        low = _f(q.get("low")) or close
        dates.append(d)
        main_nets.append(mn)
        turnovers.append(amount)
        bar = {
            "trade_date": d,
            "date": d,
            "amount": amount,
            "volume": vol,
            "high": high,
            "low": low,
            "close": close,
        }
        vwaps.append(vwap_from_bar(bar))
        highs.append(high)
        lows.append(low)
        closes.append(close)
        volumes.append(vol)
        bars_for_vp.append(bar)

    entry_flags = [
        is_entry_day(main_nets[i], turnovers[i], participation_min=participation_min)
        for i in range(len(dates))
    ]
    windows_idx = find_entry_windows(dates, main_nets, entry_flags)

    latest_window: Optional[Dict[str, Any]] = None
    cost_center = None
    if windows_idx:
        w = windows_idx[-1]
        si, ei = w["start_i"], w["end_i"]
        pos_idx = [k for k in range(si, ei + 1) if entry_flags[k]]
        cc = compute_cost_center(pos_idx, main_nets, vwaps, highs, lows)
        cost_center = cc["cost_center"]
        last_close = closes[ei] if closes else None
        vs_pct = None
        if cost_center is not None and last_close is not None and last_close > 0:
            vs_pct = (last_close - cost_center) / cost_center * 100.0

        # VP 需要足够 K 线：窗口不足 5 根时用整段回看作旁证
        vp_bars = bars_for_vp[si : ei + 1]
        if len(vp_bars) < 5:
            vp_bars = bars_for_vp
        vp = compute_volume_profile_from_bars(
            vp_bars,
            last_close=last_close,
            lookback=max(5, len(vp_bars)),
        )
        vp_poc = vp.get("poc") if vp.get("ok") else None
        vp_vah = vp.get("vah") if vp.get("ok") else None
        vp_val = vp.get("val") if vp.get("ok") else None
        cost_vs_poc = None
        if cost_center is not None and vp_poc is not None and vp_poc > 0:
            cost_vs_poc = (cost_center - float(vp_poc)) / float(vp_poc) * 100.0

        latest_window = {
            "start_date": dates[si],
            "end_date": dates[ei],
            "main_net_sum": cc["main_net_sum"],
            "cost_center": cost_center,
            "price_low": cc["price_low"],
            "price_high": cc["price_high"],
            "vs_last_close_pct": vs_pct,
            "vp_poc": vp_poc,
            "vp_vah": vp_vah,
            "vp_val": vp_val,
            "cost_vs_poc_pct": cost_vs_poc,
            "entry_days": len(pos_idx),
            "kind": w.get("kind"),
        }

    last_close = closes[-1] if closes else None
    verdict = classify_verdict(
        windows=windows_idx,
        entry_flags=entry_flags,
        main_nets=main_nets,
        closes=closes,
        volumes=volumes,
        cost_center=cost_center,
        last_close=last_close,
    )

    # 旁证
    ths_aligned = None
    if ths_net_by_date and latest_window:
        s, e = latest_window["start_date"], latest_window["end_date"]
        ths_sum = 0.0
        any_ths = False
        for d, v in ths_net_by_date.items():
            if s <= d <= e and v is not None:
                ths_sum += float(v)
                any_ths = True
        if any_ths and latest_window.get("main_net_sum"):
            ths_aligned = (ths_sum > 0) == (float(latest_window["main_net_sum"]) > 0)

    board_resonance = None
    if board_main_nets:
        vals = [float(x) for x in board_main_nets if x is not None]
        if vals and latest_window and latest_window.get("main_net_sum"):
            board_resonance = (sum(vals) > 0) == (
                float(latest_window["main_net_sum"]) > 0
            )

    inflow_days = sum(1 for x in main_nets if (x or 0) > 0)
    outflow_days = sum(1 for x in main_nets if (x or 0) < 0)
    main_net_sum = sum((_f(x) or 0.0) for x in main_nets)

    return {
        "code": code,
        "lookback_days": lb,
        "days_used": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, verdict),
        "latest_window": latest_window,
        "windows": [
            {
                "start_date": dates[w["start_i"]],
                "end_date": dates[w["end_i"]],
                "kind": w.get("kind"),
            }
            for w in windows_idx
        ],
        "series_summary": {
            "main_net_sum": main_net_sum,
            "inflow_days": inflow_days,
            "outflow_days": outflow_days,
            "entry_days": sum(1 for f in entry_flags if f),
        },
        "ths_net_aligned": ths_aligned,
        "board_resonance": board_resonance,
        "participation_min": participation_min,
        "disclaimer": DISCLAIMER,
    }
