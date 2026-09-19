# -*- coding: utf-8 -*-
"""A 股龙虎榜：优先同花顺 Fuyao，失败后回退 akshare 东方财富 stock_lhb_detail_em。"""

from __future__ import annotations

import logging
import math
import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])

BOARD_TYPES = ("all", "org", "hot_money")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EM_LOOKBACK_DAYS = 20


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace("%", "")
        if s in ("", "-", "--", "None", "nan", "NaN"):
            return None
        value = s
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _int(value: Any) -> Optional[int]:
    n = _num(value)
    if n is None:
        return None
    return int(n)


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "nan", "null"):
        return None
    return s


def norm_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix) and s[len(prefix) :].isdigit():
            s = s[len(prefix) :]
            break
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    if len(digits) <= 6:
        return digits.zfill(6)
    return digits[-6:]


def norm_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if hasattr(raw, "strftime"):
        try:
            return raw.strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(raw).strip()
    if not s or s.lower() in ("none", "nan", "nat"):
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    compact = s.replace("-", "").replace("/", "")[:8]
    if len(compact) == 8 and compact.isdigit():
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return None


def _pick(item: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item.get(key) not in (None, ""):
            return item.get(key)
    return None


def _pick_num(item: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key not in item:
            continue
        n = _num(item.get(key))
        if n is not None:
            return n
    return None


def _stock_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    code = norm_code(_pick(raw, "ticker", "code", "thscode", "代码", "SECURITY_CODE"))
    name = _text(_pick(raw, "name", "名称", "SECURITY_NAME_ABBR"))
    buy = _pick_num(raw, "buy_value", "龙虎榜买入额", "BILLBOARD_BUY_AMT")
    sell = _pick_num(raw, "sell_value", "龙虎榜卖出额", "BILLBOARD_SELL_AMT")
    net = _pick_num(raw, "net_value", "龙虎榜净买额", "BILLBOARD_NET_AMT", "hot_money_item_net_value")
    if net is None and buy is not None and sell is not None:
        net = buy - sell
    concepts = raw.get("concept_list")
    if isinstance(concepts, list):
        concepts_text = "、".join(str(x) for x in concepts if str(x).strip()) or None
    else:
        concepts_text = _text(concepts)
    return {
        "code": code,
        "name": name,
        "change_percent": _pick_num(raw, "change", "change_percent", "涨跌幅", "CHANGE_RATE"),
        "close": _pick_num(raw, "close", "close_price", "收盘价", "CLOSE_PRICE", "last_price"),
        "buy_value": buy,
        "sell_value": sell,
        "net_value": net,
        "net_rate": _pick_num(
            raw, "net_rate", "净买额占总成交比", "DEAL_NET_RATIO", "hot_money_net_rate", "hot_money_item_net_rate"
        ),
        "org_net_value": _pick_num(raw, "org_net_value"),
        "hot_money_net_value": _pick_num(raw, "hot_money_net_value"),
        "deal_value": _pick_num(raw, "deal_value", "amount", "龙虎榜成交额", "BILLBOARD_DEAL_AMT"),
        "market_turnover": _pick_num(raw, "market_turnover", "市场总成交额", "ACCUM_AMOUNT"),
        "turnover_rate": _pick_num(raw, "turnover_rate", "换手率", "TURNOVERRATE"),
        "reason": _text(_pick(raw, "limit_reason", "reason", "上榜原因", "EXPLANATION")),
        "interpretation": _text(_pick(raw, "interpretation", "解读", "EXPLAIN")),
        "range_days": _int(_pick(raw, "range_days")),
        "hot_rank": _int(_pick(raw, "hot_rank")),
        "concepts": concepts_text,
        "after_1d": _pick_num(raw, "after_1d", "上榜后1日", "D1_CLOSE_ADJCHRATE"),
        "after_2d": _pick_num(raw, "after_2d", "上榜后2日", "D2_CLOSE_ADJCHRATE"),
        "after_5d": _pick_num(raw, "after_5d", "上榜后5日", "D5_CLOSE_ADJCHRATE"),
    }


def _sort_by_net(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(row: Dict[str, Any]):
        v = row.get("net_value")
        if v is None:
            return (1, 0.0)
        return (0, -float(v))

    return sorted(items, key=key)


def normalize_fuyao_data(data: Dict[str, Any], *, board_type: str) -> Dict[str, Any]:
    raw_items = data.get("stock_items") if isinstance(data.get("stock_items"), list) else []
    items = [_stock_item(x) for x in raw_items if isinstance(x, dict)]
    hot_out: List[Dict[str, Any]] = []
    raw_hot = data.get("hot_money_items") if isinstance(data.get("hot_money_items"), list) else []
    for seat in raw_hot:
        if not isinstance(seat, dict):
            continue
        rows_raw = seat.get("rows") if isinstance(seat.get("rows"), list) else []
        stocks = [_stock_item(x) for x in rows_raw if isinstance(x, dict)]
        buy = _pick_num(seat, "buying", "buy_value")
        sell = _pick_num(seat, "sell_value")
        net = _pick_num(seat, "net_value")
        if buy is None:
            vals = [s["buy_value"] for s in stocks if s.get("buy_value") is not None]
            buy = sum(vals) if vals else None
        if sell is None:
            vals = [s["sell_value"] for s in stocks if s.get("sell_value") is not None]
            sell = sum(vals) if vals else None
        if net is None:
            vals = [s["net_value"] for s in stocks if s.get("net_value") is not None]
            net = sum(vals) if vals else None
        hot_out.append(
            {
                "name": _text(_pick(seat, "name", "hot_money_name")) or "未知席位",
                "buy_value": buy,
                "sell_value": sell,
                "net_value": net,
                "stocks": _sort_by_net(stocks),
            }
        )
    trade_date = norm_date(data.get("trade_date"))
    codes = {i["code"] for i in items if i.get("code")}
    return {
        "source": "fuyao",
        "source_label": "同花顺",
        "board_type": board_type,
        "trade_date": trade_date,
        "stock_count": int(data.get("stock_count") or len(codes) or len(items)),
        "count": len(items),
        "amount_unit": "yuan",
        "items": _sort_by_net(items),
        "hot_money_items": _sort_by_net(hot_out),
        "fallback_reason": None,
        "board_type_note": None,
    }


def records_to_em_payload(
    records: List[Dict[str, Any]],
    *,
    board_type: str,
    trade_date: Optional[str],
) -> Dict[str, Any]:
    dated: List[tuple] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        day = norm_date(_pick(row, "上榜日", "TRADE_DATE", "trade_date"))
        dated.append((day, row))
    chosen = trade_date
    if chosen:
        picked = [row for day, row in dated if day == chosen]
    else:
        days = [day for day, _ in dated if day]
        chosen = max(days) if days else None
        picked = [row for day, row in dated if (chosen is None or day == chosen)]
    items = [_stock_item(row) for row in picked]
    codes = {i["code"] for i in items if i.get("code")}
    note = None
    if board_type != "all":
        note = "东方财富龙虎榜详情不区分机构榜与游资榜，以下为当日全部上榜明细。"
    return {
        "source": "akshare_em",
        "source_label": "东方财富",
        "board_type": board_type,
        "trade_date": chosen,
        "stock_count": len(codes) or len(items),
        "count": len(items),
        "amount_unit": "yuan",
        "items": _sort_by_net(items),
        "hot_money_items": [],
        "fallback_reason": None,
        "board_type_note": note,
    }


def fetch_fuyao_dragon_tiger(board_type: str, trade_date: Optional[str]) -> Dict[str, Any]:
    from backend_api.utils.fuyao_client import fetch_dragon_tiger_list

    result = fetch_dragon_tiger_list(board_type, trade_date)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "fuyao_failed"}
    data = result.get("data") or {}
    payload = normalize_fuyao_data(data, board_type=board_type)
    if not payload["items"] and not payload["hot_money_items"]:
        return {"ok": False, "error": "empty_items"}
    return {"ok": True, "data": payload}


def _em_window(trade_date: Optional[str]) -> tuple:
    if trade_date:
        ymd = trade_date.replace("-", "")
        return ymd, ymd
    end = date.today()
    start = end - timedelta(days=_EM_LOOKBACK_DAYS)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_em_dragon_tiger(board_type: str, trade_date: Optional[str]) -> Dict[str, Any]:
    try:
        import akshare as ak
    except Exception as exc:
        logger.warning("akshare 导入失败: %s", type(exc).__name__)
        return {"ok": False, "error": f"akshare_import:{type(exc).__name__}"}

    start, end = _em_window(trade_date)
    try:
        df = ak.stock_lhb_detail_em(start_date=start, end_date=end)
    except Exception as exc:
        logger.warning("stock_lhb_detail_em 失败: %s", type(exc).__name__)
        return {"ok": False, "error": f"em_request:{type(exc).__name__}"}

    if df is None:
        return {"ok": False, "error": "empty_items"}
    try:
        empty = bool(getattr(df, "empty", False))
    except Exception:
        empty = False
    if empty:
        return {"ok": False, "error": "empty_items"}
    try:
        records = df.to_dict(orient="records")
    except Exception as exc:
        return {"ok": False, "error": f"em_parse:{type(exc).__name__}"}
    payload = records_to_em_payload(records, board_type=board_type, trade_date=trade_date)
    if not payload["items"]:
        return {"ok": False, "error": "empty_items", "data": payload}
    return {"ok": True, "data": payload}


def _fallback_text(error: Optional[str]) -> str:
    err = str(error or "")
    if err == "missing_api_key":
        return "未配置同花顺接口密钥，已改用东方财富"
    if err in ("empty_items", "fuyao_empty"):
        return "同花顺暂无龙虎榜，已改用东方财富"
    if err.startswith("request_error") or err.startswith("http_") or err.startswith("invalid_json"):
        return "同花顺接口请求失败，已改用东方财富"
    if err.startswith("biz_code") or err:
        return "同花顺接口不可用，已改用东方财富"
    return "已改用东方财富"


def load_dragon_tiger(
    board_type: str = "all",
    trade_date: Optional[str] = None,
    *,
    fuyao_loader: Optional[Callable[..., Dict[str, Any]]] = None,
    em_loader: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """统一出口。成功时 success=True 且 data 为归一化榜单。"""
    bt = (board_type or "all").strip().lower()
    if bt not in BOARD_TYPES:
        return {"success": False, "message": "board_type 应为 all、org 或 hot_money"}
    day = (trade_date or "").strip() or None
    if day and not _DATE_RE.match(day):
        return {"success": False, "message": "date 格式应为 YYYY-MM-DD"}

    fuyao_loader = fuyao_loader or fetch_fuyao_dragon_tiger
    em_loader = em_loader or fetch_em_dragon_tiger

    fuyao_err = None
    try:
        fuyao = fuyao_loader(bt, day)
    except Exception as exc:
        logger.exception("龙虎榜同花顺加载异常")
        fuyao = {"ok": False, "error": f"fuyao_exception:{type(exc).__name__}"}
    if fuyao.get("ok") and fuyao.get("data"):
        return {"success": True, "data": fuyao["data"]}
    fuyao_err = fuyao.get("error") or "fuyao_failed"

    try:
        em = em_loader(bt, day)
    except Exception as exc:
        logger.exception("龙虎榜东方财富加载异常")
        em = {"ok": False, "error": f"em_exception:{type(exc).__name__}"}
    if em.get("ok") and em.get("data"):
        data = dict(em["data"])
        data["fallback_reason"] = _fallback_text(fuyao_err)
        if data.get("board_type_note") and data["fallback_reason"]:
            data["board_type_note"] = f"{data['fallback_reason']}。{data['board_type_note']}"
            data["fallback_reason"] = data["board_type_note"]
        elif data.get("board_type_note"):
            data["fallback_reason"] = data["board_type_note"]
        return {"success": True, "data": data}

    em_err = em.get("error") or "em_failed"
    if fuyao_err == "empty_items" and em_err == "empty_items":
        empty = records_to_em_payload([], board_type=bt, trade_date=day)
        empty["source"] = "none"
        empty["source_label"] = ""
        empty["fallback_reason"] = "同花顺与东方财富均无龙虎榜数据"
        return {"success": True, "data": empty}

    return {
        "success": False,
        "message": f"龙虎榜获取失败（同花顺: {fuyao_err}；东方财富: {em_err}）",
    }


@router.get("/dragon-tiger")
async def get_dragon_tiger(
    board_type: str = Query("all", description="all | org | hot_money"),
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，省略为最新可用交易日"),
):
    """龙虎榜。优先同花顺 Fuyao，失败再走 akshare 东方财富详情。金额单位：元。"""
    out = load_dragon_tiger(board_type, date)
    if not out.get("success"):
        status = 400 if "格式" in str(out.get("message") or "") or "board_type" in str(out.get("message") or "") else 502
        return JSONResponse(out, status_code=status)
    return out
