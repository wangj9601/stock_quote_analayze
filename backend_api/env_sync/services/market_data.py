# -*- coding: utf-8 -*-
"""行情 / 股票基本信息 / 板块成分股 export·import。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import String, cast, text
from sqlalchemy.orm import Session

from backend_api.env_sync.bundle import (
    empty_result,
    json_safe,
    make_bundle,
    parse_date,
    parse_dt,
)
from backend_api.models import HistoricalQuotes, HistoricalQuotesHK, StockBasicInfo, StockBasicInfoHK

QUOTE_TABLES = ("historical_quotes", "historical_quotes_hk")
BASIC_TABLES = ("stock_basic_info", "stock_basic_info_hk")
BOARD_TABLES = (
    "industry_board_basic_info",
    "industry_board_constituents",
    "concept_board_basic_info",
    "concept_board_constituents",
)

DEFAULT_QUOTE_MAX_DAYS = 366
UPSERT_CHUNK = 800


def _max_quote_days() -> int:
    import os

    try:
        return max(1, int(os.getenv("ENV_SYNC_QUOTE_MAX_DAYS") or DEFAULT_QUOTE_MAX_DAYS))
    except ValueError:
        return DEFAULT_QUOTE_MAX_DAYS


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    *,
    require: bool = False,
) -> Dict[str, Optional[date]]:
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if require or sd or ed:
        if not sd or not ed:
            raise ValueError("同步行情数据时必须指定 start_date 与 end_date（YYYY-MM-DD）")
        if sd > ed:
            raise ValueError("start_date 不能晚于 end_date")
        span = (ed - sd).days + 1
        lim = _max_quote_days()
        if span > lim:
            raise ValueError(f"行情日期跨度 {span} 天超过上限 {lim} 天，请缩小范围后分批同步")
    return {"start": sd, "end": ed}


def _row_dict(row: Any, fields: List[str]) -> Dict[str, Any]:
    return {f: json_safe(getattr(row, f, None)) for f in fields}


def export_stock_basic(db: Session, *, tables: Optional[Set[str]] = None, env_label: str = "local") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    want = tables or set(BASIC_TABLES)
    if "stock_basic_info" in want:
        fields = [
            "code",
            "name",
            "industry",
            "listing_date",
            "total_shares",
            "free_float_shares",
            "shares_updated_at",
            "collect_enabled",
        ]
        items["stock_basic_info"] = [
            _row_dict(r, fields) for r in db.query(StockBasicInfo).order_by(StockBasicInfo.code).all()
        ]
    if "stock_basic_info_hk" in want:
        fields = [
            "code",
            "name",
            "create_date",
            "industry",
            "listing_date",
            "total_shares",
            "free_float_shares",
            "shares_updated_at",
            "collect_enabled",
        ]
        items["stock_basic_info_hk"] = [
            _row_dict(r, fields) for r in db.query(StockBasicInfoHK).order_by(StockBasicInfoHK.code).all()
        ]
    return make_bundle(module="stock_basic", items=items, env_label=env_label)


def import_stock_basic(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    want = tables or set(BASIC_TABLES)

    def upsert_cn(rows: List[Dict]):
        for raw in rows:
            code = str(raw.get("code") or "").strip()
            if not code:
                result["skipped"] += 1
                continue
            try:
                with db.begin_nested():
                    existing = db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
                    payload = {
                        "name": raw.get("name") or code,
                        "industry": raw.get("industry"),
                        "listing_date": raw.get("listing_date"),
                        "total_shares": raw.get("total_shares"),
                        "free_float_shares": raw.get("free_float_shares"),
                        "shares_updated_at": parse_dt(raw.get("shares_updated_at")),
                        "collect_enabled": raw.get("collect_enabled")
                        if raw.get("collect_enabled") is not None
                        else True,
                    }
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                        result["updated"] += 1
                    else:
                        db.add(StockBasicInfo(code=code, **payload))
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"stock_basic_info/{code}: {e}")

    def upsert_hk(rows: List[Dict]):
        for raw in rows:
            code = str(raw.get("code") or "").strip()
            if not code:
                result["skipped"] += 1
                continue
            try:
                with db.begin_nested():
                    existing = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
                    payload = {
                        "name": raw.get("name") or code,
                        "create_date": parse_dt(raw.get("create_date")),
                        "industry": raw.get("industry"),
                        "listing_date": raw.get("listing_date"),
                        "total_shares": raw.get("total_shares"),
                        "free_float_shares": raw.get("free_float_shares"),
                        "shares_updated_at": parse_dt(raw.get("shares_updated_at")),
                        "collect_enabled": raw.get("collect_enabled")
                        if raw.get("collect_enabled") is not None
                        else True,
                    }
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                        result["updated"] += 1
                    else:
                        db.add(StockBasicInfoHK(code=code, **payload))
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"stock_basic_info_hk/{code}: {e}")

    if "stock_basic_info" in want:
        upsert_cn(items.get("stock_basic_info") or [])
    if "stock_basic_info_hk" in want:
        upsert_hk(items.get("stock_basic_info_hk") or [])
    db.commit()
    return result


def _board_basic_cols(conn) -> List[str]:
    # 兼容不同迁移阶段的列
    preferred = [
        "board_code",
        "board_name",
        "create_date",
        "trade_observe_flag",
        "frontend_visible_flag",
        "board_code_source",
    ]
    existing = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:t
                """
            ),
            {"t": "industry_board_basic_info"},
        )
    }
    # SQLite tests: information_schema may be empty — fall back
    if not existing:
        return ["board_code", "board_name", "create_date", "trade_observe_flag"]
    return [c for c in preferred if c in existing]


def export_board_data(db: Session, *, tables: Optional[Set[str]] = None, env_label: str = "local") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    want = tables or set(BOARD_TABLES)

    def fetch_all(sql: str) -> List[Dict[str, Any]]:
        rows = db.execute(text(sql)).mappings().all()
        return [json_safe(dict(r)) for r in rows]

    # board basic via raw SQL (no ORM)
    if "industry_board_basic_info" in want:
        try:
            cols = _board_basic_cols(db.connection())
            col_sql = ", ".join(cols)
            items["industry_board_basic_info"] = fetch_all(
                f"SELECT {col_sql} FROM industry_board_basic_info ORDER BY board_code"
            )
        except Exception as e:
            items["industry_board_basic_info"] = []
            items["_errors"] = items.get("_errors") or []
            items["_errors"].append(f"industry_board_basic_info export: {e}")

    if "concept_board_basic_info" in want:
        try:
            # reuse column discovery against concept table
            preferred = [
                "board_code",
                "board_name",
                "create_date",
                "trade_observe_flag",
                "frontend_visible_flag",
                "board_code_source",
            ]
            existing = {
                r[0]
                for r in db.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema='public' AND table_name='concept_board_basic_info'
                        """
                    )
                )
            }
            cols = [c for c in preferred if c in existing] if existing else preferred[:4]
            col_sql = ", ".join(cols)
            items["concept_board_basic_info"] = fetch_all(
                f"SELECT {col_sql} FROM concept_board_basic_info ORDER BY board_code"
            )
        except Exception as e:
            items["concept_board_basic_info"] = []
            items["_errors"] = items.get("_errors") or []
            items["_errors"].append(f"concept_board_basic_info export: {e}")

    if "industry_board_constituents" in want:
        items["industry_board_constituents"] = fetch_all(
            "SELECT board_code, stock_code, stock_name, updated_at "
            "FROM industry_board_constituents ORDER BY board_code, stock_code"
        )
    if "concept_board_constituents" in want:
        items["concept_board_constituents"] = fetch_all(
            "SELECT board_code, stock_code, stock_name, updated_at "
            "FROM concept_board_constituents ORDER BY board_code, stock_code"
        )

    bundle = make_bundle(module="board_data", items={k: v for k, v in items.items() if not k.startswith("_")}, env_label=env_label)
    if items.get("_errors"):
        bundle["export_warnings"] = items["_errors"]
    return bundle


def import_board_data(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    want = tables or set(BOARD_TABLES)

    def upsert_basic(table: str, rows: List[Dict]):
        for raw in rows:
            code = str(raw.get("board_code") or "").strip()
            if not code:
                result["skipped"] += 1
                continue
            try:
                with db.begin_nested():
                    name = raw.get("board_name")
                    trade_flag = bool(raw.get("trade_observe_flag") or False)
                    visible = raw.get("frontend_visible_flag")
                    if visible is None:
                        visible = True
                    source = raw.get("board_code_source")
                    # 尽量兼容缺列
                    db.execute(
                        text(
                            f"""
                            INSERT INTO {table} (board_code, board_name, trade_observe_flag)
                            VALUES (:board_code, :board_name, :trade_observe_flag)
                            ON CONFLICT (board_code) DO UPDATE SET
                              board_name = EXCLUDED.board_name,
                              trade_observe_flag = EXCLUDED.trade_observe_flag
                            """
                        ),
                        {
                            "board_code": code,
                            "board_name": name,
                            "trade_observe_flag": trade_flag,
                        },
                    )
                    # 可选列尽力更新
                    try:
                        db.execute(
                            text(
                                f"""
                                UPDATE {table}
                                SET frontend_visible_flag = :v,
                                    board_code_source = COALESCE(:s, board_code_source)
                                WHERE board_code = :c
                                """
                            ),
                            {"v": bool(visible), "s": source, "c": code},
                        )
                    except Exception:
                        pass
                    result["updated"] += 1
            except Exception as e:
                # SQLite ON CONFLICT / 缺表
                try:
                    with db.begin_nested():
                        exists = db.execute(
                            text(f"SELECT 1 FROM {table} WHERE board_code = :c"),
                            {"c": code},
                        ).first()
                        if exists:
                            db.execute(
                                text(
                                    f"UPDATE {table} SET board_name=:n, trade_observe_flag=:f WHERE board_code=:c"
                                ),
                                {"n": name, "f": trade_flag, "c": code},
                            )
                            result["updated"] += 1
                        else:
                            db.execute(
                                text(
                                    f"INSERT INTO {table} (board_code, board_name, trade_observe_flag) "
                                    f"VALUES (:c,:n,:f)"
                                ),
                                {"c": code, "n": name, "f": trade_flag},
                            )
                            result["created"] += 1
                except Exception as e2:
                    result["errors"].append(f"{table}/{code}: {e2 or e}")

    def upsert_const(table: str, rows: List[Dict]):
        for raw in rows:
            bc = str(raw.get("board_code") or "").strip()
            sc = str(raw.get("stock_code") or "").strip()
            if not bc or not sc:
                result["skipped"] += 1
                continue
            try:
                with db.begin_nested():
                    sn = raw.get("stock_name")
                    ua = parse_dt(raw.get("updated_at")) or datetime.now()
                    exists = db.execute(
                        text(
                            f"SELECT 1 FROM {table} WHERE board_code=:b AND stock_code=:s"
                        ),
                        {"b": bc, "s": sc},
                    ).first()
                    if exists:
                        db.execute(
                            text(
                                f"UPDATE {table} SET stock_name=:n, updated_at=:u "
                                f"WHERE board_code=:b AND stock_code=:s"
                            ),
                            {"n": sn, "u": ua, "b": bc, "s": sc},
                        )
                        result["updated"] += 1
                    else:
                        db.execute(
                            text(
                                f"INSERT INTO {table} (board_code, stock_code, stock_name, updated_at) "
                                f"VALUES (:b,:s,:n,:u)"
                            ),
                            {"b": bc, "s": sc, "n": sn, "u": ua},
                        )
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"{table}/{bc}/{sc}: {e}")

    if "industry_board_basic_info" in want:
        upsert_basic("industry_board_basic_info", items.get("industry_board_basic_info") or [])
    if "concept_board_basic_info" in want:
        upsert_basic("concept_board_basic_info", items.get("concept_board_basic_info") or [])
    if "industry_board_constituents" in want:
        upsert_const("industry_board_constituents", items.get("industry_board_constituents") or [])
    if "concept_board_constituents" in want:
        upsert_const("concept_board_constituents", items.get("concept_board_constituents") or [])

    db.commit()
    return result


CN_QUOTE_FIELDS = [
    "code",
    "ts_code",
    "name",
    "market",
    "date",
    "open",
    "close",
    "high",
    "low",
    "pre_close",
    "volume",
    "amount",
    "amplitude",
    "change_percent",
    "change",
    "turnover_rate",
    "collected_source",
    "collected_date",
    "cumulative_change_percent",
    "five_day_change_percent",
    "ten_day_change_percent",
    "thirty_day_change_percent",
    "sixty_day_change_percent",
    "remarks",
]

HK_QUOTE_FIELDS = [
    "code",
    "ts_code",
    "name",
    "english_name",
    "date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "volume",
    "amount",
    "change_amount",
    "amplitude",
    "turnover_rate",
    "change_percent",
    "five_day_change_percent",
    "ten_day_change_percent",
    "sixty_day_change_percent",
    "thirty_day_change_percent",
]


def export_quotes(
    db: Session,
    *,
    start: date,
    end: date,
    tables: Optional[Set[str]] = None,
    env_label: str = "local",
) -> Dict[str, Any]:
    want = tables or set(QUOTE_TABLES)
    items: Dict[str, Any] = {}
    meta = {"start_date": start.isoformat(), "end_date": end.isoformat()}
    # A股 historical_quotes.date 在生产 PG 常为 TEXT；ORM 标 Date 时直接与 date 比较会生成
    # `text >= date` 报错。统一 CAST 成字符串再按 YYYY-MM-DD 字典序比较（与 URT/GMS 一致）。
    sd, ed = start.isoformat(), end.isoformat()
    cn_date_text = cast(HistoricalQuotes.date, String)

    if "historical_quotes" in want:
        q = (
            db.query(HistoricalQuotes)
            .filter(cn_date_text >= sd, cn_date_text <= ed)
            .order_by(cn_date_text, HistoricalQuotes.code)
        )
        items["historical_quotes"] = [_row_dict(r, CN_QUOTE_FIELDS) for r in q.all()]

    if "historical_quotes_hk" in want:
        # 港股 date 为 TEXT，按 YYYY-MM-DD 字符串区间即可
        q = (
            db.query(HistoricalQuotesHK)
            .filter(HistoricalQuotesHK.date >= sd, HistoricalQuotesHK.date <= ed)
            .order_by(HistoricalQuotesHK.date, HistoricalQuotesHK.code)
        )
        items["historical_quotes_hk"] = [_row_dict(r, HK_QUOTE_FIELDS) for r in q.all()]

    bundle = make_bundle(module="quotes", items=items, env_label=env_label)
    bundle["date_range"] = meta
    return bundle


def import_quotes(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    want = tables or set(QUOTE_TABLES)

    def upsert_cn(rows: List[Dict]):
        for raw in rows:
            code = str(raw.get("code") or "").strip()
            d = parse_date(raw.get("date"))
            if not code or not d:
                result["skipped"] += 1
                continue
            d_key = d.isoformat()
            try:
                with db.begin_nested():
                    existing = (
                        db.query(HistoricalQuotes)
                        .filter(
                            HistoricalQuotes.code == code,
                            cast(HistoricalQuotes.date, String) == d_key,
                        )
                        .first()
                    )
                    payload = {f: raw.get(f) for f in CN_QUOTE_FIELDS if f not in ("code", "date")}
                    payload["collected_date"] = parse_dt(raw.get("collected_date"))
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                        result["updated"] += 1
                    else:
                        db.add(HistoricalQuotes(code=code, date=d, **payload))
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"historical_quotes/{code}/{d_key}: {e}")

    def upsert_hk(rows: List[Dict]):
        for raw in rows:
            code = str(raw.get("code") or "").strip()
            d = str(raw.get("date") or "").strip()[:10]
            if not code or not d:
                result["skipped"] += 1
                continue
            try:
                with db.begin_nested():
                    existing = (
                        db.query(HistoricalQuotesHK)
                        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date == d)
                        .first()
                    )
                    payload = {f: raw.get(f) for f in HK_QUOTE_FIELDS if f not in ("code", "date")}
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                        result["updated"] += 1
                    else:
                        db.add(HistoricalQuotesHK(code=code, date=d, **payload))
                        result["created"] += 1
            except Exception as e:
                result["errors"].append(f"historical_quotes_hk/{code}/{d}: {e}")

    if "historical_quotes" in want:
        upsert_cn(items.get("historical_quotes") or [])
    if "historical_quotes_hk" in want:
        upsert_hk(items.get("historical_quotes_hk") or [])
    db.commit()
    return result
