# -*- coding: utf-8 -*-
"""同花顺 Fuyao REST 客户端：行情快照等。

约定：
- Base URL: https://fuyao.aicubes.cn（可用 FUYAO_BASE_URL 覆盖）
- Header: X-api-key
- API Key 优先环境变量 HITHINK_FINANCE_API_KEY / FUYAO_API_KEY，
  其次 %APPDATA%/hithink-finance/credentials.env
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_FUYAO_BASE_URL = "https://fuyao.aicubes.cn"
SNAPSHOT_PATH = "/api/a-share/prices/snapshot"
DEFAULT_TIMEOUT = 8.0
A_SHARE_LOT_SIZE = 100  # A股1手=100股；Fuyao volume 为股，对外统一按手

_api_key_cache: Optional[str] = None
_api_key_loaded = False


def volume_shares_to_hands(volume_shares: Any) -> Optional[float]:
    """Fuyao 成交量（股）→ 系统口径（手）。"""
    try:
        if volume_shares is None:
            return None
        v = float(volume_shares)
        if v < 0:
            return None
        return v / A_SHARE_LOT_SIZE
    except (TypeError, ValueError):
        return None


def calc_turnover_rate_pct(
    volume_shares: Any,
    free_float_shares: Any,
) -> Optional[float]:
    """
    换手率(%) = 成交量(股) / 流通股本(股) * 100
    """
    try:
        if volume_shares is None or free_float_shares is None:
            return None
        vs = float(volume_shares)
        fs = float(free_float_shares)
        if vs < 0 or fs <= 0:
            return None
        return round(vs / fs * 100.0, 4)
    except (TypeError, ValueError):
        return None


def _credentials_env_path() -> Path:
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        return Path(appdata) / "hithink-finance" / "credentials.env"
    # 非 Windows 回退到用户主目录约定路径
    return Path.home() / "AppData" / "Roaming" / "hithink-finance" / "credentials.env"


def _parse_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("读取 Fuyao credentials 失败: %s", exc)
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def get_fuyao_api_key(*, force_reload: bool = False) -> Optional[str]:
    """获取 Fuyao API Key（不写日志明文）。"""
    global _api_key_cache, _api_key_loaded
    if _api_key_loaded and not force_reload:
        return _api_key_cache

    key = (
        (os.getenv("HITHINK_FINANCE_API_KEY") or "").strip()
        or (os.getenv("FUYAO_API_KEY") or "").strip()
    )
    if not key:
        env_map = _parse_env_file(_credentials_env_path())
        key = (
            (env_map.get("HITHINK_FINANCE_API_KEY") or "").strip()
            or (env_map.get("FUYAO_API_KEY") or "").strip()
            or (env_map.get("API_KEY") or "").strip()
        )

    _api_key_cache = key or None
    _api_key_loaded = True
    return _api_key_cache


def get_fuyao_base_url() -> str:
    return (os.getenv("FUYAO_BASE_URL") or DEFAULT_FUYAO_BASE_URL).rstrip("/")


def code_to_thscode(code: str) -> Optional[str]:
    """6 位 A 股代码 → thscode（如 000001.SZ / 600519.SH / 830799.BJ）。"""
    raw = str(code or "").strip().upper()
    if not raw:
        return None
    if "." in raw:
        # 已是 thscode / ts_code
        left, _, right = raw.partition(".")
        if left.isdigit() and right in ("SH", "SZ", "BJ"):
            return f"{left.zfill(6)}.{right}"
        return None
    for prefix in ("SH", "SZ", "BJ"):
        if raw.startswith(prefix) and raw[len(prefix) :].isdigit():
            return f"{raw[len(prefix):].zfill(6)}.{prefix}"
    digits = raw
    if not digits.isdigit():
        return None
    digits = digits.zfill(6)
    if digits.startswith(("6", "5", "9")):
        return f"{digits}.SH"
    if digits.startswith(("0", "1", "2", "3")):
        return f"{digits}.SZ"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    return f"{digits}.SH"


def fetch_a_share_price_snapshot(
    codes: List[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    调用 GET /api/a-share/prices/snapshot。

    Returns:
        {"ok": True, "items": [...], "raw": {...}} 或
        {"ok": False, "error": "...", "code": int|None}
    """
    api_key = get_fuyao_api_key()
    if not api_key:
        print("[fuyao_snapshot] 缺少 API Key，跳过同花顺实时接口")
        return {"ok": False, "error": "missing_api_key", "code": 2001}

    thscodes = []
    for c in codes:
        tc = code_to_thscode(c)
        if tc:
            thscodes.append(tc)
    if not thscodes:
        print(f"[fuyao_snapshot] 无效股票代码: {codes}")
        return {"ok": False, "error": "invalid_code", "code": None}

    url = f"{get_fuyao_base_url()}{SNAPSHOT_PATH}"
    headers = {"X-api-key": api_key, "Accept": "application/json"}
    params = {"thscodes": ",".join(thscodes)}
    print(f"[fuyao_snapshot] 请求 GET {url}?thscodes={params['thscodes']}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as exc:
        print(f"[fuyao_snapshot] 请求失败: {type(exc).__name__}: {exc}")
        logger.warning("Fuyao snapshot 请求失败: %s", type(exc).__name__)
        return {"ok": False, "error": f"request_error:{type(exc).__name__}", "code": None}

    print(f"[fuyao_snapshot] HTTP status={resp.status_code}")
    try:
        payload = resp.json()
    except ValueError:
        body_preview = (resp.text or "")[:500]
        print(f"[fuyao_snapshot] 非 JSON 响应 body={body_preview!r}")
        return {
            "ok": False,
            "error": f"invalid_json_http_{resp.status_code}",
            "code": None,
        }

    # 打印同花顺实时接口完整返回（不含请求头/API Key）
    print(f"[fuyao_snapshot] 同花顺实时接口返回: {payload}")

    biz_code = payload.get("code")
    if biz_code not in (0, "0", None):
        # 统一信封：业务错误也常 HTTP 200
        print(
            f"[fuyao_snapshot] 业务失败 code={biz_code} message={payload.get('message')}"
        )
        return {
            "ok": False,
            "error": payload.get("message") or f"biz_code_{biz_code}",
            "code": biz_code,
            "raw": payload,
        }

    data = payload.get("data") or {}
    items = data.get("item") or data.get("items") or []
    if not isinstance(items, list) or not items:
        print(f"[fuyao_snapshot] 返回空行情 items={items!r}")
        return {"ok": False, "error": "empty_items", "code": biz_code, "raw": payload}

    print(
        f"[fuyao_snapshot] 成功 items={len(items)} timestamp={data.get('timestamp')} "
        f"request_id={payload.get('request_id')}"
    )
    return {
        "ok": True,
        "items": items,
        "timestamp": data.get("timestamp"),
        "raw": payload,
    }


def snapshot_item_to_quote(
    item: Dict[str, Any],
    *,
    code: str,
    name: Optional[str] = None,
    free_float_shares: Optional[float] = None,
) -> Dict[str, Any]:
    """将 Fuyao snapshot item 映射为详情页 realtime_quote 字段。

    注意：
    - Fuyao ``volume`` 单位为股；系统对外成交量统一为「手」（÷100）
    - 换手率不直接用接口字段，按流通股本自行计算
    - 均价 = 成交额(元) / 成交量(股)
    """
    last = item.get("last_price")
    prev = item.get("prev_price")
    volume_shares = item.get("volume")
    turnover = item.get("turnover")

    volume_hands = volume_shares_to_hands(volume_shares)
    turnover_rate = calc_turnover_rate_pct(volume_shares, free_float_shares)

    average_price = None
    try:
        if turnover is not None and volume_shares is not None and float(volume_shares) > 0:
            average_price = float(turnover) / float(volume_shares)
    except (TypeError, ValueError):
        average_price = None

    ticker = str(item.get("ticker") or code).strip()
    print(
        f"[fuyao_snapshot] 单位换算 code={ticker or code} "
        f"volume_shares={volume_shares} → volume_hands={volume_hands} "
        f"free_float_shares={free_float_shares} turnover_rate={turnover_rate}"
    )
    return {
        "code": ticker or code,
        "name": name,
        "current_price": last,
        "change_amount": item.get("price_change"),
        "change_percent": item.get("price_change_ratio_pct"),
        "open": item.get("open_price"),
        "pre_close": prev,
        "high": item.get("high_price"),
        "low": item.get("low_price"),
        "volume": volume_hands,
        "turnover": turnover,
        "turnover_rate": turnover_rate,
        "pe_dynamic": item.get("pe_dynamic") or item.get("pe"),
        "average_price": average_price,
        "source": "fuyao",
    }


def fetch_realtime_quote_by_code(
    code: str,
    *,
    name: Optional[str] = None,
    free_float_shares: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """单只 A 股行情快照；失败返回 None。"""
    result = fetch_a_share_price_snapshot([code])
    if not result.get("ok"):
        logger.info("Fuyao snapshot 未命中 code=%s err=%s", code, result.get("error"))
        print(f"[fuyao_snapshot] 未命中 code={code} err={result.get('error')}")
        return None
    items = result.get("items") or []
    if not items:
        return None
    return snapshot_item_to_quote(
        items[0],
        code=code,
        name=name,
        free_float_shares=free_float_shares,
    )
