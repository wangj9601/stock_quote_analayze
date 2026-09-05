"""行业板块成分股查询工具。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.models import IndustryBoardConstituent
from backend_api.utils.bk_board_code import is_valid_bk_board_code
from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    LEGACY_DEFAULT_BOARD_CODE_SOURCE,
    board_code_source_label,
    resolve_board_code_source,
)


def resolve_board_for_roles(
    db: Session,
    board_type: str,
    board_code: str,
    board_code_source: Optional[str] = None,
    board_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    校验 basic_info 中的 (board_code, board_code_source)，供龙头/中军取成分。

    默认来源为同花顺。精确匹配失败且目标为同花顺时，可按板块名称映射到同花顺板码；
    不静默回退到东财成分。
    """
    btype = str(board_type or "").strip().lower()
    if btype not in ("industry", "concept"):
        return None
    code = str(board_code or "").strip()
    if not code:
        return None
    source = resolve_board_code_source(
        board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
    )
    table = (
        "industry_board_basic_info"
        if btype == "industry"
        else "concept_board_basic_info"
    )

    def _row_to_meta(row: Any) -> Dict[str, Any]:
        src = resolve_board_code_source(
            row[2], fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
        )
        return {
            "board_type": btype,
            "board_code": str(row[0]).strip(),
            "board_name": str(row[1] or row[0]).strip(),
            "board_code_source": src,
            "board_code_source_label": board_code_source_label(src),
        }

    row = db.execute(
        text(
            f"""
            SELECT board_code, board_name, board_code_source
            FROM {table}
            WHERE TRIM(board_code) = :code
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source
            LIMIT 1
            """
        ),
        {
            "code": code,
            "source": source,
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchone()
    if row:
        return _row_to_meta(row)

    # 先查持久化代码映射（东财码 → 同花顺码等）
    try:
        from backend_api.utils.industry_board_code_map import resolve_peer_board_code

        peer = resolve_peer_board_code(db, code, board_kind=btype)
        if peer:
            peer_row = db.execute(
                text(
                    f"""
                    SELECT board_code, board_name, board_code_source
                    FROM {table}
                    WHERE TRIM(board_code) = :code
                      AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source
                    LIMIT 1
                    """
                ),
                {
                    "code": peer,
                    "source": source,
                    "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
                },
            ).fetchone()
            if peer_row:
                return _row_to_meta(peer_row)
            # 目标为同花顺时，对端行本身可能就是同花顺码
            if source == DEFAULT_BOARD_CODE_SOURCE:
                peer_any = db.execute(
                    text(
                        f"""
                        SELECT board_code, board_name, board_code_source
                        FROM {table}
                        WHERE TRIM(board_code) = :code
                        LIMIT 1
                        """
                    ),
                    {"code": peer},
                ).fetchone()
                if peer_any:
                    peer_src = resolve_board_code_source(
                        peer_any[2], fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
                    )
                    if peer_src == DEFAULT_BOARD_CODE_SOURCE:
                        return _row_to_meta(peer_any)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # 默认同花顺：用名称（或东财同码行的名称）映射到同花顺板
    if source != DEFAULT_BOARD_CODE_SOURCE:
        return None

    name = str(board_name or "").strip()
    if not name:
        name_row = db.execute(
            text(
                f"""
                SELECT board_name
                FROM {table}
                WHERE TRIM(board_code) = :code
                ORDER BY CASE
                    WHEN COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :em
                    THEN 0 ELSE 1 END
                LIMIT 1
                """
            ),
            {
                "code": code,
                "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
                "em": "eastmoney",
            },
        ).fetchone()
        name = str(name_row[0] or "").strip() if name_row else ""

    if not name:
        return None

    mapped = db.execute(
        text(
            f"""
            SELECT board_code, board_name, board_code_source
            FROM {table}
            WHERE TRIM(board_name) = :name
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source
            ORDER BY board_code
            LIMIT 1
            """
        ),
        {
            "name": name,
            "source": DEFAULT_BOARD_CODE_SOURCE,
            "legacy": LEGACY_DEFAULT_BOARD_CODE_SOURCE,
        },
    ).fetchone()
    return _row_to_meta(mapped) if mapped else None


def list_board_constituent_codes(
    db: Session, board_type: str, board_code: str
) -> List[Dict[str, str]]:
    """按板码取成分股（行业/概念），不含来源混用。"""
    btype = str(board_type or "").strip().lower()
    code = str(board_code or "").strip()
    if not code or btype not in ("industry", "concept"):
        return []
    if btype == "industry":
        rows = (
            db.query(IndustryBoardConstituent)
            .filter(IndustryBoardConstituent.board_code == code)
            .all()
        )
        return [
            {
                "code": _normalize_code(c.stock_code),
                "name": str(c.stock_name or "").strip(),
            }
            for c in rows
            if c.stock_code
        ]
    rows = db.execute(
        text(
            """
            SELECT stock_code, stock_name
            FROM concept_board_constituents
            WHERE board_code = :board_code
            """
        ),
        {"board_code": code},
    ).fetchall()
    return [
        {
            "code": _normalize_code(r[0]),
            "name": str(r[1] or "").strip(),
        }
        for r in rows
        if r[0]
    ]


def _catalog_stock_count(raw: Any) -> int:
    if not isinstance(raw, dict):
        return 0
    for key in ("stock_count", "member_count"):
        if key not in raw:
            continue
        try:
            return max(0, int(raw.get(key) or 0))
        except (TypeError, ValueError):
            continue
    return 0


def _catalog_dedupe_rank(entry: Dict[str, Any]) -> Tuple[int, str]:
    """同名同来源去重排序：东财优先 BK；同花顺优先 881 等非 BK（避免误标 BK 挤掉真·同花顺码）。"""
    code = str(entry.get("board_code") or "")
    source = resolve_board_code_source(
        entry.get("board_code_source"),
        fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE,
    )
    is_bk = is_valid_bk_board_code(code)
    if source == "tonghuashun":
        # 同花顺行业码多为 881xxx；BK 多为东财码误写入同花顺来源
        return (1 if is_bk else 0, code)
    return (0 if is_bk else 1, code)


def dedupe_industry_board_catalog(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同名同来源只保留一条；不同来源可并存。

    东财：优先 BK 编码；同花顺：优先非 BK（如 881xxx）。合并 trade_observe_flag，
    stock_count 取组内最大。
    """
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for raw in items:
        code = str(raw.get("board_code") or "").strip()
        if not code:
            continue
        name = str(raw.get("board_name") or "").strip() or code
        source = resolve_board_code_source(
            raw.get("board_code_source"),
            fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE,
        )
        stock_count = _catalog_stock_count(raw)
        entry = {
            "board_code": code,
            "board_name": name,
            "trade_observe_flag": bool(raw.get("trade_observe_flag")),
            "board_code_source": source,
            "board_code_source_label": board_code_source_label(source),
            "stock_count": stock_count,
            "member_count": stock_count,
        }
        buckets.setdefault((name, source), []).append(entry)

    out: List[Dict[str, Any]] = []
    for _key, group in buckets.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(key=_catalog_dedupe_rank)
        chosen = dict(group[0])
        chosen["trade_observe_flag"] = any(bool(x.get("trade_observe_flag")) for x in group)
        chosen["stock_count"] = max(int(x.get("stock_count") or 0) for x in group)
        chosen["member_count"] = chosen["stock_count"]
        out.append(chosen)
    out.sort(key=lambda x: (x["board_name"], x["board_code_source"], x["board_code"]))
    return out


def _fetch_board_catalog(
    db: Session,
    *,
    board_kind: str = "industry",
    frontend_only: bool = True,
    board_code_source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """行业/概念板 catalog：basic_info + 成分股数量；同名不同代码来源可并存。"""
    kind = (board_kind or "industry").strip().lower()
    if kind == "concept":
        basic_table = "concept_board_basic_info"
        cons_table = "concept_board_constituents"
    else:
        basic_table = "industry_board_basic_info"
        cons_table = "industry_board_constituents"
    visible_filter = (
        "AND COALESCE(b.frontend_visible_flag, TRUE) = TRUE"
        if frontend_only
        else ""
    )
    source_filter = ""
    params: Dict[str, Any] = {}
    if board_code_source is not None:
        src = resolve_board_code_source(
            board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        source_filter = (
            "AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source"
        )
        params["source"] = src
        params["legacy"] = LEGACY_DEFAULT_BOARD_CODE_SOURCE
    rows = db.execute(
        text(
            f"""
            SELECT b.board_code, b.board_name,
                   COALESCE(b.trade_observe_flag, FALSE) AS trade_observe_flag,
                   b.board_code_source,
                   COALESCE(cnt.n, 0) AS stock_count
            FROM {basic_table} b
            LEFT JOIN (
                SELECT board_code, COUNT(*) AS n
                FROM {cons_table}
                GROUP BY board_code
            ) cnt ON cnt.board_code = b.board_code
            WHERE b.board_code IS NOT NULL AND TRIM(b.board_code) <> ''
              {visible_filter}
              {source_filter}
            ORDER BY b.board_name NULLS LAST, b.board_code
            """
        ),
        params or None,
    ).fetchall()
    items = []
    for r in rows:
        try:
            stock_count = int(r[4] or 0)
        except (TypeError, ValueError):
            stock_count = 0
        items.append(
            {
                "board_code": str(r[0]),
                "board_name": r[1],
                "trade_observe_flag": bool(r[2]),
                "board_code_source": r[3],
                "stock_count": stock_count,
                "member_count": stock_count,
            }
        )
    return dedupe_industry_board_catalog(items)


def fetch_industry_board_catalog(
    db: Session,
    *,
    frontend_only: bool = True,
    board_code_source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """GMS 等行业板块选择器：basic_info + 成分股数量；同名不同代码来源可并存。

    board_code_source 非空时仅返回该来源（如 tonghuashun）。
    """
    return _fetch_board_catalog(
        db,
        board_kind="industry",
        frontend_only=frontend_only,
        board_code_source=board_code_source,
    )


def fetch_concept_board_catalog(
    db: Session,
    *,
    frontend_only: bool = True,
    board_code_source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """概念板块选择器/行情列表 catalog（默认同花顺）。"""
    return _fetch_board_catalog(
        db,
        board_kind="concept",
        frontend_only=frontend_only,
        board_code_source=board_code_source,
    )


def _json_safe_value(value: Any) -> Any:
    """将 DB/ORM 常见类型转为 JSON 可序列化值。"""
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return value


def looks_like_board_index_price(
    latest_price: Any,
    change_amount: Any = None,
    *,
    min_index_points: float = 100.0,
) -> bool:
    """判断 latest_price 是否更像东财行业板指数点位（而非同花顺成分均价）。

    东财「最新价」常见数百~上万且常带涨跌额；同花顺「均价」多为 <100 且涨跌额为空。
    """
    if latest_price is None:
        return False
    try:
        px = abs(float(latest_price))
    except (TypeError, ValueError):
        return False
    if px >= float(min_index_points):
        return True
    # 少数指数可能暂时 <100，但东财行通常有涨跌额
    if change_amount is not None:
        try:
            float(change_amount)
            return True
        except (TypeError, ValueError):
            return False
    return False


def _quote_fields_from_row(row: Any) -> Dict[str, Any]:
    """将 realtime_quotes 行映射为列表/详情字段（缺列则跳过）。"""
    if row is None:
        return {}
    # Row 可能是 ORM、tuple 或 Mapping
    if hasattr(row, "_mapping"):
        m = dict(row._mapping)
    elif hasattr(row, "__table__"):
        m = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    elif isinstance(row, dict):
        m = row
    else:
        return {}
    out: Dict[str, Any] = {}
    for key in (
        "latest_price",
        "change_amount",
        "change_percent",
        "total_market_value",
        "volume",
        "amount",
        "turnover_rate",
        "up_count",
        "down_count",
        "leading_stock_name",
        "leading_stock_code",
        "leading_stock_change_percent",
        "update_time",
    ):
        if key in m:
            out[key] = _json_safe_value(m.get(key))
    # 均价残留不得作为「指数」展示（如 31.34）
    if not looks_like_board_index_price(out.get("latest_price"), out.get("change_amount")):
        out["latest_price"] = None
    quote_code = m.get("board_code")
    if quote_code:
        out["quote_board_code"] = str(quote_code).strip()
    return out


def _parse_quote_update_ts(raw: Any) -> float:
    """将 update_time 解析为可比较时间戳；无法解析则为 0。"""
    if raw is None:
        return 0.0
    if isinstance(raw, datetime):
        return raw.timestamp()
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day).timestamp()
    s = str(raw).strip()
    if not s:
        return 0.0
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:26], fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _quote_index_score(fields: Optional[Dict[str, Any]]) -> Tuple[int, float, float]:
    """行情行优先分：(指数质量, 更新时间, 指数点位)。

    东财行业板「最新价」为指数点（常见数百~上万），且通常带涨跌额；
    同花顺一览误写入的「均价」多为个位数~百以内、涨跌额为空。
    质量相同时优先更新时间更新的一条，避免旧同花顺行因 |涨跌幅| 更大而压过新东财行。
    """
    if not fields:
        return (0, 0.0, 0.0)
    has_change_amt = 1 if fields.get("change_amount") is not None else 0
    try:
        px = abs(float(fields.get("latest_price"))) if fields.get("latest_price") is not None else 0.0
    except (TypeError, ValueError):
        px = 0.0
    index_like = 1 if looks_like_board_index_price(fields.get("latest_price"), fields.get("change_amount")) else 0
    freshness = _parse_quote_update_ts(fields.get("update_time"))
    return (has_change_amt + index_like, freshness, px)


def _prefer_board_quote(
    primary: Optional[Dict[str, Any]],
    secondary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """在多路行情候选中，优先选用更像板块指数、且更新更近的一条。"""
    a = primary or {}
    b = secondary or {}
    if not a:
        return dict(b) if b else {}
    if not b:
        return dict(a)
    if _quote_index_score(b) > _quote_index_score(a):
        return dict(b)
    return dict(a)


def _pick_best_board_quote(*candidates: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从多个候选行情中折叠选出最优一条。"""
    best: Dict[str, Any] = {}
    for c in candidates:
        if not c:
            continue
        best = _prefer_board_quote(best, c) if best else dict(c)
    return best


def _resolve_industry_board_quote(
    by_code: Dict[str, Dict[str, Any]],
    by_name: Dict[str, Dict[str, Any]],
    *,
    board_code: str,
    board_name: str,
    ths_to_em: Optional[Dict[str, str]] = None,
    em_to_ths: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """按 本码 / 映射对端码 / 同名 三路解析行业板实时行情。"""
    code = str(board_code or "").strip()
    name = str(board_name or "").strip()
    peer = None
    if code and ths_to_em and code in ths_to_em:
        peer = ths_to_em.get(code)
    elif code and em_to_ths and code in em_to_ths:
        peer = em_to_ths.get(code)
    return _pick_best_board_quote(
        by_code.get(code) if code else None,
        by_code.get(peer) if peer else None,
        by_name.get(name) if name else None,
    )


def _load_industry_realtime_quote_indexes(
    db: Session,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """加载实时行情索引：按 board_code、按 board_name（各取最新一条；同名再择更像指数者）。"""
    by_code: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (board_code)
                       board_code, board_name, latest_price, change_amount,
                       change_percent, total_market_value, volume, amount,
                       turnover_rate, up_count, down_count,
                       leading_stock_name, leading_stock_code,
                       leading_stock_change_percent, update_time
                FROM industry_board_realtime_quotes
                ORDER BY board_code,
                         /* 优先带涨跌额/指数量级的行，避免同花顺均价或空指数覆盖东财点位 */
                         (CASE WHEN change_amount IS NOT NULL THEN 1 ELSE 0 END
                          + CASE WHEN latest_price IS NOT NULL AND latest_price >= 100
                                 THEN 1 ELSE 0 END) DESC,
                         update_time DESC NULLS LAST
                """
            )
        ).fetchall()
    except Exception:
        # PostgreSQL 事务 abort 后需 rollback，避免拖垮后续 catalog/斜率查询
        try:
            db.rollback()
        except Exception:
            pass
        return by_code, by_name
    for r in rows:
        fields = _quote_fields_from_row(r)
        code = str(r[0] or "").strip()
        name = str(r[1] or "").strip()
        if code:
            by_code[code] = fields
        if not name:
            continue
        prev = by_name.get(name)
        if prev is None or _quote_index_score(fields) > _quote_index_score(prev):
            by_name[name] = fields
    return by_code, by_name


def _attach_slope_fields(item: Dict[str, Any], slope: Optional[Dict[str, Any]]) -> None:
    if not slope:
        item["sector_slope"] = None
        item["sector_slope_window"] = None
        item["slope_asof_date"] = None
        item["member_count_used"] = None
        item["slope_transform"] = "log"
        return
    item["sector_slope"] = slope.get("sector_slope")
    item["sector_slope_window"] = slope.get("sector_slope_window")
    item["slope_transform"] = slope.get("slope_transform") or "log"
    asof = slope.get("slope_asof_date")
    if hasattr(asof, "isoformat"):
        item["slope_asof_date"] = asof.isoformat()
    else:
        item["slope_asof_date"] = str(asof)[:10] if asof else None
    item["member_count_used"] = slope.get("member_count_used")


def _attach_window_slope_fields(
    item: Dict[str, Any],
    slope: Optional[Dict[str, Any]],
    *,
    window: int,
    field_suffix: str,
    use_realtime_fallback: bool = False,
    change_percent: Any = None,
) -> None:
    """附加指定窗口斜率与环境字段（suffix 如 '120'/'20'/'5'/'short'）。"""
    from backend_core.board_metrics.sector_slope_store import (
        slope_strong_threshold_for_window,
    )
    from backend_core.strategies.gms.board_resonance import evaluate_board_environment

    slope_key = f"sector_slope_{field_suffix}"
    window_key = f"sector_slope_{field_suffix}_window"
    asof_key = f"slope_{field_suffix}_asof_date"
    env_key = f"board_env_{field_suffix}"
    env_label_key = f"board_env_{field_suffix}_label"
    strong_key = f"board_strong_{field_suffix}"
    weak_key = f"board_weak_{field_suffix}"
    th_key = f"slope_{field_suffix}_strong_threshold"
    strong_th = slope_strong_threshold_for_window(window)

    if not slope:
        item[slope_key] = None
        item[window_key] = int(window)
        item[asof_key] = None
        item[env_key] = "unknown"
        item[env_label_key] = "--"
        item[strong_key] = False
        item[weak_key] = False
        item[th_key] = strong_th
        return

    item[slope_key] = slope.get("sector_slope")
    item[window_key] = slope.get("sector_slope_window") or int(window)
    asof = slope.get("slope_asof_date")
    if hasattr(asof, "isoformat"):
        item[asof_key] = asof.isoformat()
    else:
        item[asof_key] = str(asof)[:10] if asof else None

    try:
        slope_f = float(item[slope_key]) if item.get(slope_key) is not None else None
    except (TypeError, ValueError):
        slope_f = None
    cp = None
    if use_realtime_fallback:
        cp = change_percent if change_percent is not None else item.get("change_percent")
        try:
            cp = float(cp) if cp is not None else None
        except (TypeError, ValueError):
            cp = None
    env = evaluate_board_environment(
        sector_slope_v=slope_f,
        board_change_percent=cp,
        slope_strong_threshold=strong_th,
        use_realtime_fallback=bool(use_realtime_fallback),
    )
    item[weak_key] = env["board_weak"]
    item[strong_key] = env["board_strong"]
    item[env_key] = env["board_env"]
    item[env_label_key] = env["board_env_label"]
    item[th_key] = env["slope_strong_threshold"]


def _attach_short_slope_fields(
    item: Dict[str, Any],
    slope: Optional[Dict[str, Any]],
    *,
    change_percent: Any = None,
) -> None:
    """附加短线斜率与短线环境（默认近 10 日，不回退实时涨跌）。

    兼容旧字段名 sector_slope_short / board_env_short。
    """
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
    )

    _attach_window_slope_fields(
        item,
        slope,
        window=DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        field_suffix="short",
        use_realtime_fallback=False,
        change_percent=change_percent,
    )


def _attach_extra_window_slope_fields(
    item: Dict[str, Any],
    slopes_by_window: Dict[int, Dict[str, Any]],
    *,
    board_code: str,
    change_percent: Any = None,
) -> None:
    """附加 120/20/5 日斜率字段（列表/详情共用）。"""
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_LONG_WINDOW,
        DEFAULT_SECTOR_SLOPE_MID_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_ULTRA_SHORT_WINDOW,
    )

    for win, suffix in (
        (DEFAULT_SECTOR_SLOPE_LONG_WINDOW, "120"),
        (DEFAULT_SECTOR_SLOPE_MID_SHORT_WINDOW, "20"),
        (DEFAULT_SECTOR_SLOPE_ULTRA_SHORT_WINDOW, "5"),
    ):
        bucket = slopes_by_window.get(win) or {}
        _attach_window_slope_fields(
            item,
            bucket.get(board_code),
            window=win,
            field_suffix=suffix,
            use_realtime_fallback=False,
            change_percent=change_percent,
        )


def _load_slopes_by_windows(
    db: Session,
    codes: List[str],
    *,
    board_kind: str,
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """批量读取默认多窗口斜率；失败返回空桶。"""
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SLOPE_WINDOWS,
        load_board_sector_slopes_multi,
    )

    if not codes:
        return {int(w): {} for w in DEFAULT_SLOPE_WINDOWS}
    try:
        return (
            load_board_sector_slopes_multi(
                db, codes, board_kind=board_kind, windows=DEFAULT_SLOPE_WINDOWS
            )
            or {int(w): {} for w in DEFAULT_SLOPE_WINDOWS}
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return {int(w): {} for w in DEFAULT_SLOPE_WINDOWS}


def _attach_board_env_fields(item: Dict[str, Any], change_percent: Any = None) -> None:
    """列表/详情附加走弱/走强展示字段（ln 斜率口径）。"""
    from backend_core.strategies.gms.board_resonance import evaluate_board_environment

    try:
        slope_f = float(item["sector_slope"]) if item.get("sector_slope") is not None else None
    except (TypeError, ValueError):
        slope_f = None
    cp = change_percent if change_percent is not None else item.get("change_percent")
    try:
        cp_f = float(cp) if cp is not None else None
    except (TypeError, ValueError):
        cp_f = None
    env = evaluate_board_environment(
        sector_slope_v=slope_f,
        board_change_percent=cp_f,
    )
    item["board_weak"] = env["board_weak"]
    item["board_strong"] = env["board_strong"]
    item["board_env"] = env["board_env"]
    item["board_env_label"] = env["board_env_label"]
    item["board_weak_reason"] = env["board_weak_reason"]
    item["board_weak_summary"] = env["board_weak_summary"]
    item["slope_weak_threshold"] = env["slope_weak_threshold"]
    item["slope_strong_threshold"] = env["slope_strong_threshold"]
    item["slope_transform"] = env.get("slope_transform") or item.get("slope_transform") or "log"


def fetch_industry_board_list_with_metrics(
    db: Session,
    *,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
    frontend_only: bool = True,
) -> List[Dict[str, Any]]:
    """行情页行业板列表：默认同花顺全量 + 实时行情 + 成分数 + 批量斜率。"""
    src = resolve_board_code_source(
        board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
    )
    catalog = fetch_industry_board_catalog(
        db, frontend_only=frontend_only, board_code_source=src
    )
    by_code, by_name = _load_industry_realtime_quote_indexes(db)
    ths_to_em: Dict[str, str] = {}
    em_to_ths: Dict[str, str] = {}
    try:
        from backend_api.utils.industry_board_code_map import load_active_code_maps

        ths_to_em, em_to_ths = load_active_code_maps(db, board_kind="industry")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    codes = [str(x.get("board_code") or "").strip() for x in catalog if x.get("board_code")]
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_WINDOW,
    )

    slopes_by_win = _load_slopes_by_windows(db, codes, board_kind="industry")
    slopes = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_WINDOW) or {}
    slopes_short = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_SHORT_WINDOW) or {}

    out: List[Dict[str, Any]] = []
    for raw in catalog:
        code = str(raw.get("board_code") or "").strip()
        name = str(raw.get("board_name") or "").strip() or code
        source = resolve_board_code_source(
            raw.get("board_code_source"), fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
        )
        item: Dict[str, Any] = {
            "board_code": code,
            "board_name": name,
            "board_kind": "industry",
            "board_code_source": source,
            "board_code_source_label": board_code_source_label(source),
            "trade_observe_flag": bool(raw.get("trade_observe_flag")),
            "stock_count": int(raw.get("stock_count") or 0),
            "member_count": int(raw.get("member_count") or raw.get("stock_count") or 0),
        }
        quote = _resolve_industry_board_quote(
            by_code,
            by_name,
            board_code=code,
            board_name=name,
            ths_to_em=ths_to_em,
            em_to_ths=em_to_ths,
        )
        if code and ths_to_em.get(code):
            item["mapped_em_board_code"] = ths_to_em[code]
        elif code and em_to_ths.get(code):
            item["mapped_ths_board_code"] = em_to_ths[code]
        item.update(quote)
        _attach_slope_fields(item, slopes.get(code))
        _attach_short_slope_fields(
            item, slopes_short.get(code), change_percent=item.get("change_percent")
        )
        _attach_extra_window_slope_fields(
            item,
            slopes_by_win,
            board_code=code,
            change_percent=item.get("change_percent"),
        )
        _attach_board_env_fields(item, item.get("change_percent"))
        out.append(item)

    # 走强优先，同档内按板块斜率降序；无斜率靠后
    def _sort_key(x: Dict[str, Any]) -> Tuple[int, int, float, str]:
        env = str(x.get("board_env") or "")
        if env == "strong" or x.get("board_strong"):
            env_rank = 0
        elif env == "neutral":
            env_rank = 1
        elif env == "weak" or x.get("board_weak"):
            env_rank = 2
        else:
            env_rank = 3
        slope = x.get("sector_slope")
        if slope is None:
            return (env_rank, 1, 0.0, str(x.get("board_name") or ""))
        try:
            return (env_rank, 0, -float(slope), str(x.get("board_name") or ""))
        except (TypeError, ValueError):
            return (env_rank, 1, 0.0, str(x.get("board_name") or ""))

    out.sort(key=_sort_key)
    return out


def fetch_concept_board_list_with_metrics(
    db: Session,
    *,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
    frontend_only: bool = True,
) -> List[Dict[str, Any]]:
    """行情页概念板列表：同花顺全量 + 成分数 + 批量斜率。

    概念板暂无独立实时行情表，指数/涨跌/成交等字段为空（详情可走角色估算涨跌）。
    """
    src = resolve_board_code_source(
        board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
    )
    catalog = fetch_concept_board_catalog(
        db, frontend_only=frontend_only, board_code_source=src
    )
    ths_to_em: Dict[str, str] = {}
    em_to_ths: Dict[str, str] = {}
    try:
        from backend_api.utils.industry_board_code_map import load_active_code_maps

        ths_to_em, em_to_ths = load_active_code_maps(db, board_kind="concept")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    codes = [str(x.get("board_code") or "").strip() for x in catalog if x.get("board_code")]
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_WINDOW,
    )

    slopes_by_win = _load_slopes_by_windows(db, codes, board_kind="concept")
    slopes = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_WINDOW) or {}
    slopes_short = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_SHORT_WINDOW) or {}

    out: List[Dict[str, Any]] = []
    for raw in catalog:
        code = str(raw.get("board_code") or "").strip()
        name = str(raw.get("board_name") or "").strip() or code
        source = resolve_board_code_source(
            raw.get("board_code_source"), fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
        )
        item: Dict[str, Any] = {
            "board_code": code,
            "board_name": name,
            "board_kind": "concept",
            "board_code_source": source,
            "board_code_source_label": board_code_source_label(source),
            "trade_observe_flag": bool(raw.get("trade_observe_flag")),
            "stock_count": int(raw.get("stock_count") or 0),
            "member_count": int(raw.get("member_count") or raw.get("stock_count") or 0),
        }
        if code and ths_to_em.get(code):
            item["mapped_em_board_code"] = ths_to_em[code]
        elif code and em_to_ths.get(code):
            item["mapped_ths_board_code"] = em_to_ths[code]
        _attach_slope_fields(item, slopes.get(code))
        _attach_short_slope_fields(
            item, slopes_short.get(code), change_percent=item.get("change_percent")
        )
        _attach_extra_window_slope_fields(
            item,
            slopes_by_win,
            board_code=code,
            change_percent=item.get("change_percent"),
        )
        _attach_board_env_fields(item, item.get("change_percent"))
        out.append(item)

    def _sort_key(x: Dict[str, Any]) -> Tuple[int, int, float, str]:
        env = str(x.get("board_env") or "")
        if env == "strong" or x.get("board_strong"):
            env_rank = 0
        elif env == "neutral":
            env_rank = 1
        elif env == "weak" or x.get("board_weak"):
            env_rank = 2
        else:
            env_rank = 3
        slope = x.get("sector_slope")
        if slope is None:
            return (env_rank, 1, 0.0, str(x.get("board_name") or ""))
        try:
            return (env_rank, 0, -float(slope), str(x.get("board_name") or ""))
        except (TypeError, ValueError):
            return (env_rank, 1, 0.0, str(x.get("board_name") or ""))

    out.sort(key=_sort_key)
    return out


def fetch_industry_board_detail(
    db: Session,
    board_code: str,
    *,
    board_code_source: Optional[str] = None,
    board_name: Optional[str] = None,
    include_roles: bool = True,
    compute_slope_if_missing: bool = True,
) -> Optional[Dict[str, Any]]:
    """行业板详情。"""
    return fetch_board_detail(
        db,
        board_code,
        board_kind="industry",
        board_code_source=board_code_source,
        board_name=board_name,
        include_roles=include_roles,
        compute_slope_if_missing=compute_slope_if_missing,
    )


def fetch_concept_board_detail(
    db: Session,
    board_code: str,
    *,
    board_code_source: Optional[str] = None,
    board_name: Optional[str] = None,
    include_roles: bool = True,
    compute_slope_if_missing: bool = True,
) -> Optional[Dict[str, Any]]:
    """概念板详情（斜率/龙头中军；无独立实时行情表时指数类字段为空）。"""
    return fetch_board_detail(
        db,
        board_code,
        board_kind="concept",
        board_code_source=board_code_source,
        board_name=board_name,
        include_roles=include_roles,
        compute_slope_if_missing=compute_slope_if_missing,
    )


def fetch_board_detail(
    db: Session,
    board_code: str,
    *,
    board_kind: str = "industry",
    board_code_source: Optional[str] = None,
    board_name: Optional[str] = None,
    include_roles: bool = True,
    compute_slope_if_missing: bool = True,
) -> Optional[Dict[str, Any]]:
    """行业/概念板详情：基本信息、可选行情、斜率、走弱/走强、龙头/中军。"""
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_WINDOW,
        ensure_board_sector_slope,
        is_allowed_slope_board_source,
    )
    from backend_core.board_roles.service import (
        extract_leader_mid_from_payload,
        fetch_board_roles_payload,
    )
    from backend_core.strategies.gms.board_resonance import evaluate_board_environment

    kind = (board_kind or "industry").strip().lower()
    if kind not in ("industry", "concept"):
        kind = "industry"
    cons_table = (
        "concept_board_constituents" if kind == "concept" else "industry_board_constituents"
    )

    meta = resolve_board_for_roles(
        db,
        kind,
        board_code,
        board_code_source=board_code_source or DEFAULT_BOARD_CODE_SOURCE,
        board_name=board_name,
    )
    if not meta:
        return None

    code = str(meta["board_code"]).strip()
    name = str(meta.get("board_name") or code).strip()
    source = meta.get("board_code_source") or DEFAULT_BOARD_CODE_SOURCE

    stock_count = 0
    try:
        cnt_row = db.execute(
            text(f"SELECT COUNT(*) FROM {cons_table} WHERE board_code = :code"),
            {"code": code},
        ).fetchone()
        stock_count = int(cnt_row[0] or 0) if cnt_row else 0
    except Exception:
        stock_count = 0

    quote: Dict[str, Any] = {}
    mapped_em: Optional[str] = None
    mapped_ths: Optional[str] = None
    ths_to_em: Dict[str, str] = {}
    em_to_ths: Dict[str, str] = {}
    try:
        from backend_api.utils.industry_board_code_map import load_active_code_maps

        ths_to_em, em_to_ths = load_active_code_maps(db, board_kind=kind)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    mapped_em = ths_to_em.get(code)
    mapped_ths = em_to_ths.get(code)
    if kind == "industry":
        by_code, by_name = _load_industry_realtime_quote_indexes(db)
        quote = _resolve_industry_board_quote(
            by_code,
            by_name,
            board_code=code,
            board_name=name,
            ths_to_em=ths_to_em,
            em_to_ths=em_to_ths,
        )

    slopes_by_win = _load_slopes_by_windows(db, [code], board_kind=kind)
    slopes = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_WINDOW) or {}
    slopes_short = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_SHORT_WINDOW) or {}
    slope = slopes.get(code) or {}
    slope_short = slopes_short.get(code) or {}
    slope_filled_on_demand = False

    change_percent = quote.get("change_percent")
    try:
        change_percent_f = float(change_percent) if change_percent is not None else None
    except (TypeError, ValueError):
        change_percent_f = None

    sector_slope = slope.get("sector_slope")
    try:
        sector_slope_f = float(sector_slope) if sector_slope is not None else None
    except (TypeError, ValueError):
        sector_slope_f = None

    if (
        compute_slope_if_missing
        and sector_slope_f is None
        and is_allowed_slope_board_source(source)
    ):
        try:
            filled = ensure_board_sector_slope(
                db,
                code,
                board_kind=kind,
                board_code_source=source,
                member_limit=None,
                commit=True,
            )
            if filled and filled.get("sector_slope") is not None:
                slope = filled
                slope_filled_on_demand = True
                try:
                    sector_slope_f = float(filled["sector_slope"])
                except (TypeError, ValueError):
                    sector_slope_f = None
                slopes_by_win = _load_slopes_by_windows(db, [code], board_kind=kind)
                slopes_short = slopes_by_win.get(DEFAULT_SECTOR_SLOPE_SHORT_WINDOW) or {}
                slope_short = slopes_short.get(code) or {}
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    judgment = evaluate_board_environment(
        sector_slope_v=sector_slope_f,
        board_change_percent=change_percent_f,
    )

    detail: Dict[str, Any] = {
        "board_code": code,
        "board_name": name,
        "board_kind": kind,
        "board_code_source": source,
        "board_code_source_label": meta.get("board_code_source_label")
        or board_code_source_label(source),
        "stock_count": stock_count,
        "member_count": stock_count,
        **quote,
        "board_weak": judgment["board_weak"],
        "board_strong": judgment["board_strong"],
        "board_env": judgment["board_env"],
        "board_env_label": judgment["board_env_label"],
        "board_weak_reason": judgment["board_weak_reason"],
        "board_weak_summary": judgment["board_weak_summary"],
        "slope_weak_threshold": judgment["slope_weak_threshold"],
        "slope_strong_threshold": judgment["slope_strong_threshold"],
        "slope_transform": judgment.get("slope_transform") or "log",
        "use_realtime_change_fallback": judgment["use_realtime_change_fallback"],
        "slope_filled_on_demand": slope_filled_on_demand,
        "leaders": [],
        "mids": [],
        "leader": None,
        "mid": None,
        "roles": None,
    }
    if mapped_em:
        detail["mapped_em_board_code"] = mapped_em
    if mapped_ths:
        detail["mapped_ths_board_code"] = mapped_ths
    _attach_slope_fields(detail, slope if slope else None)
    _attach_short_slope_fields(
        detail, slope_short if slope_short else None, change_percent=change_percent
    )
    _attach_extra_window_slope_fields(
        detail,
        slopes_by_win,
        board_code=code,
        change_percent=change_percent,
    )

    if include_roles:
        try:
            payload = fetch_board_roles_payload(
                db,
                board_type=kind,
                board_code=code,
                board_code_source=source,
                board_name=name,
                limit=None,
            )
            roles = extract_leader_mid_from_payload(payload)
            leaders = list(roles.get("leaders") or [])
            mids = list(roles.get("mids") or [])
            detail["leaders"] = leaders
            detail["mids"] = mids
            detail["leader"] = leaders[0] if leaders else None
            detail["mid"] = mids[0] if mids else None
            detail["roles"] = roles
            if roles.get("board_change_percent_est") is not None:
                detail["board_change_percent_est"] = roles.get("board_change_percent_est")
                # 概念板无实时行情时，用角色估算涨跌作环境旁证展示
                if detail.get("change_percent") is None:
                    try:
                        est = float(roles["board_change_percent_est"])
                        detail["change_percent"] = est
                        env2 = evaluate_board_environment(
                            sector_slope_v=sector_slope_f,
                            board_change_percent=est,
                        )
                        detail["board_weak"] = env2["board_weak"]
                        detail["board_strong"] = env2["board_strong"]
                        detail["board_env"] = env2["board_env"]
                        detail["board_env_label"] = env2["board_env_label"]
                        detail["board_weak_reason"] = env2["board_weak_reason"]
                        detail["board_weak_summary"] = env2["board_weak_summary"]
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass
    return detail


def _normalize_code(code: str) -> str:
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def get_stock_codes_by_board_codes(
    db: Session, board_codes: List[str]
) -> Set[str]:
    """按板块代码列表取成分股代码并集（行业 + 概念）。"""
    if not board_codes:
        return set()
    codes = [str(c).strip() for c in board_codes if c and str(c).strip()]
    if not codes:
        return set()
    out: Set[str] = set()
    normalized = [str(c).strip() for c in codes if c and str(c).strip()]
    if not normalized:
        return set()
    rows = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(IndustryBoardConstituent.board_code.in_(normalized))
        .distinct()
        .all()
    )
    out |= {str(r[0]).strip() for r in rows if r[0]}
    rows_con = db.execute(
        text(
            """
            SELECT DISTINCT stock_code
            FROM concept_board_constituents
            WHERE board_code = ANY(:codes)
            """
        ),
        {"codes": normalized},
    ).fetchall()
    out |= {str(r[0]).strip() for r in rows_con if r[0]}
    return {_normalize_code(c) for c in out if c}


def _dedupe_membership_boards(rows: List[Dict]) -> List[Dict]:
    """按 board_type+board_code 去重；同类型同名仅保留首次。"""
    out: List[Dict] = []
    seen_code: Set[Tuple[str, str]] = set()
    seen_name: Set[Tuple[str, str]] = set()
    for b in rows:
        btype = str(b.get("board_type") or "industry").strip().lower() or "industry"
        code = str(b.get("board_code") or "").strip()
        name = str(b.get("board_name") or code).strip()
        code_key = (btype, code)
        name_key = (btype, name.lower())
        if code and code_key in seen_code:
            continue
        if name and name_key in seen_name:
            continue
        if code:
            seen_code.add(code_key)
        if name:
            seen_name.add(name_key)
        out.append(b)
    return out


def get_boards_by_stock_code(
    db: Session,
    stock_code: str,
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> List[Dict]:
    """反查股票所属行业/概念板块（含板块名称）。

    默认仅返回 ``board_code_source=tonghuashun`` 的板块；传 ``None`` 不过滤来源。
    """
    code = _normalize_code(stock_code)
    if not code:
        return []
    params: Dict[str, Any] = {"stock_code": code}
    if board_code_source is not None:
        src = resolve_board_code_source(
            board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        params["source"] = src
        params["legacy"] = LEGACY_DEFAULT_BOARD_CODE_SOURCE
        source_filter = (
            "AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source"
        )
        # 按来源过滤时必须能关联到 basic_info
        ind_join = "INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code"
        con_join = "INNER JOIN concept_board_basic_info b ON b.board_code = c.board_code"
        source_select = (
            "COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) AS board_code_source"
        )
    else:
        source_filter = ""
        ind_join = "LEFT JOIN industry_board_basic_info b ON b.board_code = c.board_code"
        con_join = "LEFT JOIN concept_board_basic_info b ON b.board_code = c.board_code"
        source_select = "b.board_code_source AS board_code_source"

    sql = text(
        f"""
        SELECT c.board_code,
               COALESCE(b.board_name, c.board_code) AS board_name,
               c.updated_at,
               'industry' AS board_type,
               {source_select}
        FROM industry_board_constituents c
        {ind_join}
        WHERE c.stock_code = :stock_code
          {source_filter}
        UNION ALL
        SELECT c.board_code,
               COALESCE(b.board_name, c.board_code) AS board_name,
               c.updated_at,
               'concept' AS board_type,
               {source_select}
        FROM concept_board_constituents c
        {con_join}
        WHERE c.stock_code = :stock_code
          {source_filter}
        ORDER BY board_type, board_name NULLS LAST, board_code
        """
    )
    rows = db.execute(sql, params).fetchall()
    items: List[Dict] = []
    for r in rows:
        raw_src = r[4] if len(r) > 4 else None
        src = (
            resolve_board_code_source(raw_src, fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE)
            if raw_src is not None and str(raw_src).strip()
            else (
                resolve_board_code_source(
                    board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
                )
                if board_code_source is not None
                else LEGACY_DEFAULT_BOARD_CODE_SOURCE
            )
        )
        items.append(
            {
                "board_code": str(r[0]),
                "board_name": str(r[1]) if r[1] else str(r[0]),
                "updated_at": (
                    r[2].isoformat()
                    if hasattr(r[2], "isoformat")
                    else str(r[2])
                    if r[2]
                    else None
                ),
                "board_type": str(r[3]) if len(r) > 3 else "industry",
                "board_code_source": src,
                "board_code_source_label": board_code_source_label(src),
            }
        )
    return _dedupe_membership_boards(items)


def get_stock_membership_boards(
    db: Session,
    stock_code: str,
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, Any]:
    """个股所属行业/概念板块分组（默认同花顺口径）。"""
    code = _normalize_code(stock_code)
    boards = get_boards_by_stock_code(
        db, code, board_code_source=board_code_source
    )
    industry = [b for b in boards if str(b.get("board_type") or "") == "industry"]
    concept = [b for b in boards if str(b.get("board_type") or "") == "concept"]
    src = (
        resolve_board_code_source(board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE)
        if board_code_source is not None
        else None
    )
    return {
        "stock_code": code,
        "board_code_source": src,
        "board_code_source_label": board_code_source_label(src) if src else None,
        "industry_boards": industry,
        "concept_boards": concept,
        "boards": boards,
    }


def get_board_names_by_stock_code(
    db: Session,
    stock_code: str,
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> List[str]:
    boards = get_boards_by_stock_code(
        db, stock_code, board_code_source=board_code_source
    )
    return [b["board_name"] for b in boards if b.get("board_name")]


def get_industry_board_name_by_stock_code(
    db: Session,
    stock_code: str,
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> Optional[str]:
    """A 股：从行业板块成分股 + 基本信息表取板块名称（不含概念板块）。

    默认仅取 ``board_code_source=tonghuashun`` 的行业板；传 ``None`` 不过滤来源。
    """
    code = _normalize_code(stock_code)
    if not code:
        return None
    source_filter = ""
    params: Dict[str, Any] = {"stock_code": code}
    if board_code_source is not None:
        src = resolve_board_code_source(
            board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        source_filter = (
            "AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source"
        )
        params["source"] = src
        params["legacy"] = LEGACY_DEFAULT_BOARD_CODE_SOURCE
    sql = text(
        f"""
        SELECT c.board_code, b.board_name
        FROM industry_board_constituents c
        INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code = :stock_code
          {source_filter}
        ORDER BY b.board_name NULLS LAST, c.board_code
        """
    )
    try:
        rows = db.execute(sql, params).fetchall()
    except Exception:
        return None
    names: List[str] = []
    name_map = _load_industry_board_name_map(db, board_code_source=board_code_source)
    for board_code, board_name in rows:
        display = _resolve_industry_board_display_name(board_code, board_name, name_map)
        if display and display not in names:
            names.append(display)
    return ",".join(names) if names else None


def batch_industry_board_names_by_stock_codes(
    db: Session,
    stock_codes: List[str],
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, str]:
    """批量 A 股行业板块名称（stock_code -> 逗号分隔的可读板块名，不含 BK 编码）。

    默认仅取同花顺（``tonghuashun``）来源行业板；传 ``None`` 不过滤来源。
    """
    if not stock_codes:
        return {}
    codes = list(dict.fromkeys(_normalize_code(c) for c in stock_codes if c and str(c).strip()))
    if not codes:
        return {}
    source_filter = ""
    params: Dict[str, Any] = {"codes": codes}
    if board_code_source is not None:
        src = resolve_board_code_source(
            board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        source_filter = (
            "AND COALESCE(NULLIF(TRIM(b.board_code_source), ''), :legacy) = :source"
        )
        params["source"] = src
        params["legacy"] = LEGACY_DEFAULT_BOARD_CODE_SOURCE
    stmt = text(
        f"""
        SELECT c.stock_code, c.board_code, b.board_name
        FROM industry_board_constituents c
        INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
        WHERE c.stock_code IN :codes
          {source_filter}
        ORDER BY c.stock_code, b.board_name NULLS LAST, c.board_code
        """
    ).bindparams(bindparam("codes", expanding=True))
    try:
        board_rows = db.execute(stmt, params).fetchall()
    except Exception:
        return {}
    name_map = _load_industry_board_name_map(db, board_code_source=board_code_source)
    grouped: Dict[str, List[str]] = {}
    for stock_code, board_code, board_name in board_rows:
        sc = _normalize_code(str(stock_code))
        display = _resolve_industry_board_display_name(board_code, board_name, name_map)
        if not display:
            continue
        bucket = grouped.setdefault(sc, [])
        if display not in bucket:
            bucket.append(display)
    return {code: ",".join(names) for code, names in grouped.items() if names}


def sync_a_stock_industry_from_boards(
    db: Session,
    *,
    only_empty: bool = True,
    stock_codes: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    将行业板块成分映射写回 stock_basic_info.industry（A 股）。
    only_empty=True 时仅更新 industry 为空/无效占位的记录。
    """
    params: Dict[str, Any] = {}
    code_filter = ""
    if stock_codes:
        codes = list(dict.fromkeys(_normalize_code(c) for c in stock_codes if c and str(c).strip()))
        if not codes:
            return {"updated": 0, "matched": 0}
        params["codes"] = codes
        code_filter = "AND c.stock_code IN :codes"

    empty_filter = ""
    if only_empty:
        empty_filter = """
            AND (
                s.industry IS NULL
                OR TRIM(s.industry) = ''
                OR LOWER(TRIM(s.industry)) IN ('nan', 'none', 'null', '<na>', 'nat')
            )
        """

    sql = text(
        f"""
        WITH dedup AS (
            SELECT DISTINCT
                c.stock_code,
                TRIM(b.board_name) AS board_name
            FROM industry_board_constituents c
            INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
            WHERE TRIM(COALESCE(b.board_name, '')) <> ''
              AND UPPER(TRIM(b.board_name)) NOT LIKE 'BK%%'
              {code_filter}
        ),
        board_agg AS (
            SELECT
                stock_code,
                string_agg(board_name, ',' ORDER BY board_name) AS industry_name
            FROM dedup
            GROUP BY stock_code
        )
        UPDATE stock_basic_info AS s
        SET industry = board_agg.industry_name
        FROM board_agg
        WHERE LPAD(CAST(s.code AS TEXT), 6, '0') = board_agg.stock_code
          {empty_filter}
        """
    )
    if stock_codes:
        sql = sql.bindparams(bindparam("codes", expanding=True))

    try:
        matched = db.execute(
            text(
                f"""
                SELECT COUNT(DISTINCT c.stock_code)
                FROM industry_board_constituents c
                WHERE 1 = 1 {code_filter}
                """
            ).bindparams(bindparam("codes", expanding=True)) if stock_codes else text(
                "SELECT COUNT(DISTINCT stock_code) FROM industry_board_constituents"
            ),
            params,
        ).scalar() or 0
        result = db.execute(sql, params)
        db.commit()
        return {"updated": int(result.rowcount or 0), "matched": int(matched)}
    except Exception:
        db.rollback()
        raise


def normalize_industry_text(value: Any) -> Optional[str]:
    """过滤 None、空串及 nan/none 等无效占位。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.lower() in ("nan", "none", "null", "<na>", "nat"):
        return None
    return s


def is_board_code_display_token(value: Any) -> bool:
    """BK 板块编码不应作为「所属行业」展示。"""
    s = str(value or "").strip()
    if not s:
        return True
    return is_valid_bk_board_code(s)


def _load_industry_board_name_map(
    db: Session,
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, str]:
    """board_code -> 可读板块名称；默认仅加载同花顺来源。"""
    source_filter = ""
    params: Dict[str, Any] = {}
    if board_code_source is not None:
        src = resolve_board_code_source(
            board_code_source, fallback=DEFAULT_BOARD_CODE_SOURCE
        )
        source_filter = (
            "AND COALESCE(NULLIF(TRIM(board_code_source), ''), :legacy) = :source"
        )
        params["source"] = src
        params["legacy"] = LEGACY_DEFAULT_BOARD_CODE_SOURCE
    try:
        rows = db.execute(
            text(
                f"""
                SELECT board_code, board_name
                FROM industry_board_basic_info
                WHERE board_code IS NOT NULL AND TRIM(board_code) <> ''
                  {source_filter}
                """
            ),
            params,
        ).fetchall()
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for code, name in rows:
        c = str(code or "").strip()
        n = normalize_industry_text(name)
        if c and n and not is_board_code_display_token(n):
            out[c] = n
    return out


def _resolve_industry_board_display_name(
    board_code: Any,
    raw_name: Any,
    name_map: Dict[str, str],
) -> Optional[str]:
    """将成分股行的板块编码/名称解析为可展示的行业名。"""
    code = str(board_code or "").strip()
    candidate = normalize_industry_text(raw_name)
    if candidate and not is_board_code_display_token(candidate):
        return candidate
    if code:
        mapped = normalize_industry_text(name_map.get(code))
        if mapped and not is_board_code_display_token(mapped):
            return mapped
    return None


def clean_industry_display_text(value: Any) -> Optional[str]:
    """展示用行业：去掉 BK 编码，仅保留可读名称（支持逗号拼接的历史脏数据）。"""
    base = normalize_industry_text(value)
    if not base:
        return None
    parts = [p.strip() for p in base.split(",") if p.strip()]
    names: List[str] = []
    for part in parts:
        if is_board_code_display_token(part):
            continue
        if part not in names:
            names.append(part)
    return ",".join(names) if names else None


def resolve_cn_industry_display(
    stored: Optional[str], board_industry: Optional[str]
) -> Optional[str]:
    """A 股列表展示：优先行业板块名称，其次库内 industry；均过滤 BK 编码。"""
    board = clean_industry_display_text(board_industry)
    if board:
        return board
    return clean_industry_display_text(stored)


def stock_matches_industry_filter(
    db: Session,
    stock_code: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> bool:
    """include/exclude 可填 board_code 或 board_name。"""
    boards = get_boards_by_stock_code(db, stock_code)
    if not boards:
        return not bool(include)
    keys = set()
    for b in boards:
        keys.add(b["board_code"])
        keys.add(b["board_name"])
    if include:
        inc = set(include)
        if not keys.intersection(inc):
            return False
    if exclude:
        exc = set(exclude)
        if keys.intersection(exc):
            return False
    return True


def lookup_leading_code_from_constituents(
    db: Session, board_code: str, leading_stock_name: str
) -> Optional[str]:
    """在成分股表中按名称匹配领涨股代码。"""
    if not leading_stock_name or not str(leading_stock_name).strip():
        return None
    name = str(leading_stock_name).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name == name,
        )
        .first()
    )
    if row:
        return str(row[0]).strip()
    row = (
        db.query(IndustryBoardConstituent.stock_code)
        .filter(
            IndustryBoardConstituent.board_code == board_code,
            IndustryBoardConstituent.stock_name.like(f"%{name}%"),
        )
        .first()
    )
    return str(row[0]).strip() if row else None
