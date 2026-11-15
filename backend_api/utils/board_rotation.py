"""同花顺行业相对轮动（RRG）。

相对强弱 RS = 行业收盘 / 基准收盘（默认沪深300）。
RS-Ratio = 100 × RS / SMA(RS, window)
RS-Momentum = 100 × RS-Ratio / SMA(RS-Ratio, window)

100 是中轴。右上领先、右下转弱、左下落后、左上改善。
拖尾和回放由前端按返回的日序列切片，不在这里截断。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _sma(values: Sequence[Optional[float]], window: int, index: int) -> Optional[float]:
    if index + 1 < window:
        return None
    chunk = values[index + 1 - window : index + 1]
    if len(chunk) < window or any(item is None for item in chunk):
        return None
    return sum(chunk) / window


def quadrant(rs_ratio: float, rs_momentum: float, eps: float = 0.05) -> str:
    if abs(rs_ratio - 100) <= eps and abs(rs_momentum - 100) <= eps:
        return "neutral"
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "leading"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "weakening"
    if rs_ratio < 100 and rs_momentum < 100:
        return "lagging"
    return "improving"


def compute_rrg(
    closes: Sequence[Optional[float]],
    benchmark: Sequence[Optional[float]],
    window: int,
) -> List[Dict[str, Optional[float]]]:
    """与基准等长的序列。缺口日记成空，不向前填充。"""
    if window < 2:
        raise ValueError("window 至少为 2")
    if len(closes) != len(benchmark):
        raise ValueError("行业与基准长度必须一致")
    rs: List[Optional[float]] = []
    for price, base in zip(closes, benchmark):
        if price is None or base is None or base == 0:
            rs.append(None)
        else:
            rs.append(price / base)
    ratios: List[Optional[float]] = []
    for index in range(len(rs)):
        mean = _sma(rs, window, index)
        if mean is None or rs[index] is None or mean == 0:
            ratios.append(None)
        else:
            ratios.append(100.0 * rs[index] / mean)
    points: List[Dict[str, Optional[float]]] = []
    for index, ratio in enumerate(ratios):
        mean = _sma(ratios, window, index)
        if ratio is None or mean is None or mean == 0:
            points.append({"rs_ratio": None, "rs_momentum": None, "quadrant": None})
            continue
        momentum = 100.0 * ratio / mean
        points.append(
            {
                "rs_ratio": round(ratio, 2),
                "rs_momentum": round(momentum, 2),
                "quadrant": quadrant(ratio, momentum),
            }
        )
    return points


def _date_text(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def build_rotation(
    benchmark_bars: Sequence[Dict[str, Any]],
    board_rows: Iterable[Dict[str, Any]],
    window: int,
    *,
    benchmark_code: str = "000300",
    benchmark_name: str = "沪深300",
    board_kind: str = "industry",
) -> Dict[str, Any]:
    """benchmark_bars 按日期升序，元素含 date、close。"""
    ordered = []
    for bar in benchmark_bars:
        close = _float(bar.get("close"))
        date = _date_text(bar.get("date") or bar.get("trade_date") or "")
        if not date or close is None:
            continue
        ordered.append((date, close))
    dates = [item[0] for item in ordered]
    bench = [item[1] for item in ordered]
    date_set = set(dates)
    by_board: Dict[str, Dict[str, Any]] = {}
    for raw in board_rows:
        code = str(raw.get("board_code") or "").strip()
        if not code:
            continue
        date = _date_text(raw.get("date") or raw.get("trade_date") or "")
        close = _float(raw.get("close"))
        if not date or close is None or date not in date_set:
            continue
        slot = by_board.setdefault(
            code,
            {
                "board_code": code,
                "board_name": str(raw.get("board_name") or code),
                "name_date": "",
                "closes": {},
            },
        )
        name = str(raw.get("board_name") or "").strip()
        if name and date >= slot["name_date"]:
            slot["board_name"] = name
            slot["name_date"] = date
        slot["closes"][date] = close

    date_index = {date: index for index, date in enumerate(dates)}
    boards: List[Dict[str, Any]] = []
    covered = set()
    for code in sorted(by_board):
        slot = by_board[code]
        series: List[Optional[float]] = [slot["closes"].get(date) for date in dates]
        if sum(1 for price in series if price is not None) < window * 2:
            continue
        computed = compute_rrg(series, bench, window)
        points = []
        for date, point in zip(dates, computed):
            if point["rs_ratio"] is None:
                continue
            points.append({"trade_date": date, **point})
            covered.add(date_index[date])
        if points:
            boards.append(
                {
                    "board_code": code,
                    "board_name": slot["board_name"],
                    "points": points,
                }
            )
    valid_dates = [dates[index] for index in range(len(dates)) if index in covered]
    kind = board_kind if board_kind in ("industry", "concept") else "industry"
    label = "概念" if kind == "concept" else "行业"
    note = ""
    if len(bench) < window * 2:
        note = "基准日线不足，无法计算相对轮动。"
    elif not boards:
        note = f"{label}日线不足，无法计算相对轮动。"
    return {
        "benchmark_code": benchmark_code,
        "benchmark_name": benchmark_name,
        "board_kind": kind,
        "window": window,
        "dates": valid_dates,
        "boards": boards,
        "board_count": len(boards),
        "note": note,
    }


_ROTATION_TABLES = {
    "industry": "industry_board_historical_quotes",
    "concept": "concept_board_historical_quotes",
}


def fetch_industry_rotation(
    db: Session,
    *,
    benchmark: str = "000300",
    window: int = 10,
    lookback: int = 120,
    board_kind: str = "industry",
) -> Dict[str, Any]:
    """行业或概念指数日 K 对沪深300。lookback 是基准交易日根数。"""
    from backend_core.analysis.index_bars import load_index_ohlc_asc

    kind = board_kind if board_kind in _ROTATION_TABLES else "industry"
    table = _ROTATION_TABLES[kind]
    code = str(benchmark or "000300").strip() or "000300"
    bars = load_index_ohlc_asc(db, code, lookback=int(lookback))
    bench_name = "沪深300" if code.endswith("000300") or code == "000300" else code
    if not bars:
        return build_rotation(
            [],
            [],
            window,
            benchmark_code=code,
            benchmark_name=bench_name,
            board_kind=kind,
        )
    start = bars[0]["date"]
    end = bars[-1]["date"]
    rows = db.execute(
        text(
            f"""
            SELECT board_code, board_name, trade_date, close
            FROM {table}
            WHERE trade_date >= CAST(:start AS date)
              AND trade_date <= CAST(:end AS date)
              AND close IS NOT NULL
              AND close > 0
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    board_rows = [
        {
            "board_code": row["board_code"],
            "board_name": row["board_name"],
            "trade_date": row["trade_date"],
            "close": row["close"],
        }
        for row in rows
    ]
    return build_rotation(
        bars,
        board_rows,
        window,
        benchmark_code="000300" if code in ("000300", "000300.SH") else code,
        benchmark_name=bench_name,
        board_kind=kind,
    )
