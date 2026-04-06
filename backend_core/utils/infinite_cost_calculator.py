"""
无穷成本均线（ic_price）：

1) **主口径（推荐）**：文档《无穷成本均线计算方法》中的 CYC∞ 递归——用换手率 HSL 作权重揉入当日成本：
   P_t = (1 - HSL_t) * P_{t-1} + HSL_t * P_t^*
   其中 P_t^* 优先为当日成交均价 amount/volume(股)；换手率列 turnover_rate 若 >1 视为百分数并 /100；
   超过 100% 时封顶（默认 1.0）。

2) **回退**：当行情无换手率列或当日换手整段均为空时，退化为自数据起点起的累计成交额/累计成交量（全历史 VWAP）。

非通达信筹码 COST。历史行情表 volume 为「手」时先 × SHARES_PER_LOT 再参与计算。
"""

from __future__ import annotations

import math
from typing import Any, List, Optional

import pandas as pd

# 日线 volume 为手时，换算为股的乘数（与 historical_turnover_rate.A_SHARE_LOT_SIZE 一致）
SHARES_PER_LOT = 100
# 换手率异常（如新股）封顶，避免 (1-HSL) 为负或权重失真
HSL_CAP = 1.0


def _norm_date(d: Any) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _normalize_hsl(x: Any, cap: float = HSL_CAP) -> float:
    """换手率为小数；若列整体像百分数（>1）在逐行已处理。单行 >1 视为百分数。"""
    v = _safe_float(x)
    if v is None or v < 0:
        return 0.0
    if v > 1.0:
        v = v / 100.0
    return min(v, cap)


def _day_trade_price(
    r: Any,
    vol_shares: Optional[float],
) -> Optional[float]:
    """当日成本价 P_t^*：优先 amount/volume(股)，否则典型价（无有效量时用收盘价）。"""
    amt = _safe_float(r.get("amount"))
    if (
        amt is not None
        and amt > 0
        and vol_shares is not None
        and vol_shares > 0
    ):
        return amt / vol_shares
    h = _safe_float(r.get("high")) or 0.0
    l = _safe_float(r.get("low")) or 0.0
    c = _safe_float(r.get("close")) or 0.0
    tp = (h + l + c) / 3.0
    if vol_shares is not None and vol_shares > 0:
        return tp
    return _safe_float(r.get("close")) if _safe_float(r.get("close")) is not None else (tp if tp > 0 else None)


def _should_use_cyc(df: pd.DataFrame) -> bool:
    if "turnover_rate" not in df.columns:
        return False
    s = df["turnover_rate"]
    if s is None or bool(s.isna().all()):
        return False
    return True


def _calculate_vwap_cumulative(
    work: pd.DataFrame,
    lot_to_share: float,
) -> List[dict]:
    cum_amt = 0.0
    cum_vol = 0.0
    rows_out: List[dict] = []

    for _, r in work.iterrows():
        vol_raw = _safe_float(r.get("volume"))
        vol = vol_raw * lot_to_share if vol_raw is not None else None
        if vol is None or vol <= 0:
            ic = (cum_amt / cum_vol) if cum_vol > 0 else None
            rows_out.append(
                {
                    "date": r["date"],
                    "ic_price": ic,
                    "cum_amount": cum_amt,
                    "cum_volume": cum_vol,
                }
            )
            continue

        amt = _safe_float(r.get("amount"))
        if amt is not None and amt > 0:
            day_amt = amt
        else:
            h = _safe_float(r.get("high")) or 0.0
            l = _safe_float(r.get("low")) or 0.0
            c = _safe_float(r.get("close")) or 0.0
            tp = (h + l + c) / 3.0
            day_amt = tp * vol

        cum_amt += day_amt
        cum_vol += vol
        ic = cum_amt / cum_vol if cum_vol > 0 else None
        rows_out.append(
            {
                "date": r["date"],
                "ic_price": ic,
                "cum_amount": cum_amt,
                "cum_volume": cum_vol,
            }
        )

    return rows_out


def _calculate_cyc_turnover(
    work: pd.DataFrame,
    lot_to_share: float,
) -> List[dict]:
    """CYC∞：P_t = (1-HSL_t)*P_{t-1} + HSL_t*P_t^*；cum_* 仍为累计成交额/股数（审计）。"""
    cum_amt = 0.0
    cum_vol = 0.0
    p_inf: Optional[float] = None
    rows_out: List[dict] = []

    for _, r in work.iterrows():
        vol_raw = _safe_float(r.get("volume"))
        vol = vol_raw * lot_to_share if vol_raw is not None else None

        # 先更新累计额量（与 VWAP 分支同一规则，便于对账）
        day_amt_for_cum = 0.0
        if vol is not None and vol > 0:
            amt = _safe_float(r.get("amount"))
            if amt is not None and amt > 0:
                day_amt_for_cum = amt
            else:
                h = _safe_float(r.get("high")) or 0.0
                l = _safe_float(r.get("low")) or 0.0
                c = _safe_float(r.get("close")) or 0.0
                day_amt_for_cum = ((h + l + c) / 3.0) * vol
            cum_amt += day_amt_for_cum
            cum_vol += vol

        price_star = _day_trade_price(r, vol)
        hsl = _normalize_hsl(r.get("turnover_rate"))

        if p_inf is None:
            p_inf = price_star if price_star is not None else _safe_float(r.get("close"))
        else:
            if price_star is None:
                price_star = _safe_float(r.get("close"))
            if price_star is None:
                price_star = p_inf
            p_inf = (1.0 - hsl) * p_inf + hsl * float(price_star)

        rows_out.append(
            {
                "date": r["date"],
                "ic_price": p_inf,
                "cum_amount": cum_amt,
                "cum_volume": cum_vol,
            }
        )

    return rows_out


def calculate_infinite_cost_for_dataframe(
    df: pd.DataFrame,
    *,
    volume_in_lots: bool = True,
    shares_per_lot: float = SHARES_PER_LOT,
    use_turnover_recursion: Optional[bool] = None,
) -> pd.DataFrame:
    """
    输入列需含：date, high, low, close, volume；可选 amount、turnover_rate。

    - use_turnover_recursion=False：强制全历史 VWAP（累计 amount/累计 volume）。
    - 否则：若存在 turnover_rate 且不全为空，采用 CYC∞；否则 VWAP。

    volume_in_lots：为 True 时 volume 按「手」先换算为股。

    返回列：date, ic_price, cum_amount, cum_volume（cum_volume 为累计股数）
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "ic_price", "cum_amount", "cum_volume"])

    work = df.copy()
    if "date" not in work.columns:
        raise ValueError("DataFrame 需包含 date 列")
    work = work.sort_values("date").reset_index(drop=True)

    lot_to_share = float(shares_per_lot) if volume_in_lots else 1.0

    if use_turnover_recursion is False:
        rows_out = _calculate_vwap_cumulative(work, lot_to_share)
    elif _should_use_cyc(work):
        rows_out = _calculate_cyc_turnover(work, lot_to_share)
    else:
        rows_out = _calculate_vwap_cumulative(work, lot_to_share)

    out = pd.DataFrame(rows_out)
    return out


def icost_rows_for_db(df_result: pd.DataFrame) -> List[dict]:
    """将计算结果转为可写入 DB 的行：date 规范为 YYYY-MM-DD 字符串。"""
    result: List[dict] = []
    for _, r in df_result.iterrows():
        result.append(
            {
                "date": _norm_date(r.get("date")),
                "ic_price": _safe_float(r.get("ic_price")),
                "cum_amount": _safe_float(r.get("cum_amount")),
                "cum_volume": _safe_float(r.get("cum_volume")),
            }
        )
    return result
