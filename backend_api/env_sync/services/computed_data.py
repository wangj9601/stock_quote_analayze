# -*- coding: utf-8 -*-
"""预计算 / 复盘结果表 export·import（须日期范围）。

含：RS、策略 signal_trace、指数日线、板块资金流、涨停池、复盘、推荐简报。
信号表带 config_name，导入时按配置名解析本地 config_id（建议先同步策略配置）。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from sqlalchemy import Date as SADate
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.env_sync.bundle import (
    empty_result,
    json_safe,
    make_bundle,
    parse_date,
    parse_dt,
    table_exists,
)
from backend_api.models import (
    BoardFundFlowDaily,
    CSBSignalTrace,
    CSBStrategyConfig,
    GMSSignalTrace,
    GMSStrategyConfig,
    IndexHistoricalQuotes,
    RPESignalTrace,
    RPEStrategyConfig,
    RSRatings,
    SBBRSignalTrace,
    SBBRStrategyConfig,
    StockRecommendBrief,
    URTSignalTrace,
    URTStrategyConfig,
)

logger = logging.getLogger(__name__)

DEFAULT_COMPUTED_MAX_DAYS = 366
UPSERT_CHUNK = 500

COMPUTED_TABLES = (
    "rs_ratings",
    "gms_signal_trace",
    "urt_signal_trace",
    "csb_signal_trace",
    "sbbr_signal_trace",
    "rpe_signal_trace",
    "index_historical_quotes",
    "board_fund_flow_daily",
    "stock_zt_pool_daily",
    "market_daily_review",
    "market_daily_mainline_hits",
    "stock_recommend_brief",
)

ZT_POOL_FIELDS = [
    "code",
    "trade_date",
    "name",
    "change_percent",
    "price",
    "amount",
    "float_mv",
    "total_mv",
    "turnover_rate",
    "seal_fund",
    "first_seal_time",
    "last_seal_time",
    "break_count",
    "limit_stats",
    "board_count",
    "industry",
    "source",
    "collected_at",
]

REVIEW_FIELDS = [
    "trade_date",
    "vol_trillion",
    "limit_up_count",
    "cb_count",
    "height",
    "prev_cb_return",
    "lo_value",
    "hi_value",
    "sp_value",
    "lo_percentile",
    "hi_percentile",
    "sp_percentile",
    "limit_source",
    "hard_gates",
    "season",
    "season_detail",
    "rules_json",
    "mainline_json",
    "viewpoint_md",
    "advice_md",
    "viewpoint_override",
    "advice_override",
    "computed_at",
    "updated_at",
]

MAINLINE_FIELDS = [
    "trade_date",
    "board_type",
    "board_code",
    "board_name",
    "hit",
    "hit_reasons",
    "change_percent",
    "limit_up_count",
    "net_inflow",
    "created_at",
]

# PostgreSQL jsonb 列：绑定参数须 json 文本 + CAST(... AS jsonb)
# （与 backend_core.market_review.compute 写入路径一致；dict/list 不能直接适配）
REVIEW_JSON_FIELDS = frozenset(
    {"hard_gates", "season_detail", "rules_json", "mainline_json"}
)
MAINLINE_JSON_FIELDS = frozenset({"hit_reasons"})


def _json_bind(value: Any) -> Any:
    """将 dict/list 序列化为 JSON 字符串，供 CAST(:x AS jsonb) 使用。"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def max_computed_sync_days() -> int:
    try:
        return max(
            1,
            int(os.getenv("ENV_SYNC_COMPUTED_MAX_DAYS") or DEFAULT_COMPUTED_MAX_DAYS),
        )
    except ValueError:
        return DEFAULT_COMPUTED_MAX_DAYS


def _model_fields(model: Type) -> List[str]:
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def _row_dict(row: Any, fields: List[str]) -> Dict[str, Any]:
    return {f: json_safe(getattr(row, f, None)) for f in fields}


def _cfg_name_by_id(db: Session, model: Type) -> Dict[int, str]:
    tname = getattr(model, "__tablename__", "") or ""
    if tname and not table_exists(db, tname):
        return {}
    return {int(r.id): str(r.name) for r in db.query(model.id, model.name).all()}


def _cfg_id_by_name(db: Session, model: Type) -> Dict[str, int]:
    tname = getattr(model, "__tablename__", "") or ""
    if tname and not table_exists(db, tname):
        return {}
    return {str(r.name): int(r.id) for r in db.query(model.id, model.name).all()}


def _resolve_config_id(
    raw: Dict[str, Any],
    name_map: Dict[str, int],
    *,
    table: str,
    result: Dict[str, Any],
) -> Optional[int]:
    name = (raw.get("config_name") or "").strip()
    if name and name in name_map:
        return name_map[name]
    # 回退：同环境同 id（不推荐跨环境）
    cid = raw.get("config_id")
    if cid is not None and not name:
        try:
            return int(cid)
        except (TypeError, ValueError):
            pass
    result["skipped"] += 1
    result["errors"].append(
        f"{table}: 无法解析 config_name={name!r} config_id={cid!r}（请先同步对应策略配置）"
    )
    return None


def _export_orm_range(
    db: Session,
    model: Type,
    *,
    date_attr: str,
    start: date,
    end: date,
    fields: List[str],
    extra_filter=None,
) -> List[Dict[str, Any]]:
    tname = getattr(model, "__tablename__", "") or ""
    if tname and not table_exists(db, tname):
        logger.warning("env_sync export skip missing table: %s", tname)
        return []
    col = getattr(model, date_attr)
    # Date 列用 date；String/Text 列用 ISO 字符串
    col_type = col.property.columns[0].type
    if isinstance(col_type, SADate):
        lo, hi = start, end
    else:
        lo, hi = start.isoformat(), end.isoformat()
    q = db.query(model).filter(col >= lo, col <= hi)
    if extra_filter is not None:
        q = q.filter(extra_filter)
    q = q.order_by(col)
    return [_row_dict(r, fields) for r in q.all()]


def _export_raw(
    db: Session,
    table: str,
    *,
    date_col: str,
    start: date,
    end: date,
    fields: List[str],
) -> List[Dict[str, Any]]:
    if not table_exists(db, table):
        logger.warning("env_sync export skip missing table: %s", table)
        return []
    cols = ", ".join(fields)
    sql = text(
        f"""
        SELECT {cols} FROM {table}
        WHERE {date_col} >= :sd AND {date_col} <= :ed
        ORDER BY {date_col}
        """
    )
    rows = db.execute(
        sql, {"sd": start.isoformat(), "ed": end.isoformat()}
    ).mappings().all()
    return [{k: json_safe(r.get(k)) for k in fields} for r in rows]


def export_computed_results(
    db: Session,
    *,
    start: date,
    end: date,
    tables: Optional[Set[str]] = None,
    env_label: str = "local",
) -> Dict[str, Any]:
    want = tables or set(COMPUTED_TABLES)
    items: Dict[str, Any] = {}
    meta = {"start_date": start.isoformat(), "end_date": end.isoformat()}

    gms_names = _cfg_name_by_id(db, GMSStrategyConfig)
    urt_names = _cfg_name_by_id(db, URTStrategyConfig)
    csb_names = _cfg_name_by_id(db, CSBStrategyConfig)
    sbbr_names = _cfg_name_by_id(db, SBBRStrategyConfig)
    rpe_names = _cfg_name_by_id(db, RPEStrategyConfig)

    if "rs_ratings" in want:
        fields = _model_fields(RSRatings)
        items["rs_ratings"] = _export_orm_range(
            db, RSRatings, date_attr="date", start=start, end=end, fields=fields
        )

    if "gms_signal_trace" in want:
        fields = _model_fields(GMSSignalTrace)
        rows = _export_orm_range(
            db,
            GMSSignalTrace,
            date_attr="date",
            start=start,
            end=end,
            fields=fields,
            extra_filter=GMSSignalTrace.market_type == "CN",
        )
        for r in rows:
            cid = r.get("config_id")
            if cid is not None:
                r["config_name"] = gms_names.get(int(cid))
        items["gms_signal_trace"] = rows

    if "urt_signal_trace" in want:
        fields = _model_fields(URTSignalTrace)
        rows = _export_orm_range(
            db, URTSignalTrace, date_attr="date", start=start, end=end, fields=fields
        )
        for r in rows:
            cid = r.get("config_id")
            if cid is not None:
                r["config_name"] = urt_names.get(int(cid))
        items["urt_signal_trace"] = rows

    if "csb_signal_trace" in want:
        fields = _model_fields(CSBSignalTrace)
        rows = _export_orm_range(
            db, CSBSignalTrace, date_attr="trade_date", start=start, end=end, fields=fields
        )
        for r in rows:
            cid = r.get("config_id")
            if cid is not None:
                r["config_name"] = csb_names.get(int(cid))
        items["csb_signal_trace"] = rows

    if "sbbr_signal_trace" in want:
        fields = _model_fields(SBBRSignalTrace)
        rows = _export_orm_range(
            db,
            SBBRSignalTrace,
            date_attr="trade_date",
            start=start,
            end=end,
            fields=fields,
            extra_filter=SBBRSignalTrace.market_type == "CN",
        )
        for r in rows:
            cid = r.get("config_id")
            if cid is not None:
                r["config_name"] = sbbr_names.get(int(cid))
        items["sbbr_signal_trace"] = rows

    if "rpe_signal_trace" in want:
        fields = _model_fields(RPESignalTrace)
        rows = _export_orm_range(
            db,
            RPESignalTrace,
            date_attr="trade_date",
            start=start,
            end=end,
            fields=fields,
            extra_filter=RPESignalTrace.market_type == "CN",
        )
        for r in rows:
            cid = r.get("config_id")
            if cid is not None:
                r["config_name"] = rpe_names.get(int(cid))
        items["rpe_signal_trace"] = rows

    if "index_historical_quotes" in want:
        fields = _model_fields(IndexHistoricalQuotes)
        items["index_historical_quotes"] = _export_orm_range(
            db,
            IndexHistoricalQuotes,
            date_attr="trade_date",
            start=start,
            end=end,
            fields=fields,
        )

    if "board_fund_flow_daily" in want:
        fields = _model_fields(BoardFundFlowDaily)
        items["board_fund_flow_daily"] = _export_orm_range(
            db,
            BoardFundFlowDaily,
            date_attr="trade_date",
            start=start,
            end=end,
            fields=fields,
        )

    if "stock_zt_pool_daily" in want:
        items["stock_zt_pool_daily"] = _export_raw(
            db,
            "stock_zt_pool_daily",
            date_col="trade_date",
            start=start,
            end=end,
            fields=ZT_POOL_FIELDS,
        )

    if "market_daily_review" in want:
        items["market_daily_review"] = _export_raw(
            db,
            "market_daily_review",
            date_col="trade_date",
            start=start,
            end=end,
            fields=REVIEW_FIELDS,
        )

    if "market_daily_mainline_hits" in want:
        items["market_daily_mainline_hits"] = _export_raw(
            db,
            "market_daily_mainline_hits",
            date_col="trade_date",
            start=start,
            end=end,
            fields=MAINLINE_FIELDS,
        )

    if "stock_recommend_brief" in want:
        fields = _model_fields(StockRecommendBrief)
        items["stock_recommend_brief"] = _export_orm_range(
            db,
            StockRecommendBrief,
            date_attr="asof_date",
            start=start,
            end=end,
            fields=fields,
        )

    bundle = make_bundle(module="computed_results", items=items, env_label=env_label)
    bundle["date_range"] = meta
    return bundle


def _upsert_orm(
    db: Session,
    model: Type,
    *,
    pk_fields: Tuple[str, ...],
    rows: List[Dict[str, Any]],
    result: Dict[str, Any],
    skip_fields: Optional[Set[str]] = None,
) -> None:
    skip = set(skip_fields or ()) | {"id", "config_name"}
    fields = [f for f in _model_fields(model) if f not in skip]
    for raw in rows:
        pk = {}
        ok = True
        for k in pk_fields:
            v = raw.get(k)
            if k in ("trade_date", "asof_date") or (
                k == "date" and model in (CSBSignalTrace, SBBRSignalTrace, RPESignalTrace)
            ):
                # Date PK columns
                if k in ("trade_date", "asof_date"):
                    v = parse_date(v)
            if v is None or v == "":
                ok = False
                break
            pk[k] = v
        if not ok:
            result["skipped"] += 1
            continue
        try:
            with db.begin_nested():
                q = db.query(model)
                for k, v in pk.items():
                    q = q.filter(getattr(model, k) == v)
                existing = q.first()
                payload: Dict[str, Any] = {}
                for f in fields:
                    if f in pk_fields:
                        continue
                    if f not in raw:
                        continue
                    val = raw.get(f)
                    if f.endswith("_at") or f in ("computed_at", "updated_at", "generated_at", "collected_at"):
                        val = parse_dt(val)
                    elif f in ("trade_date", "asof_date"):
                        val = parse_date(val)
                    payload[f] = val
                if existing:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    result["updated"] += 1
                else:
                    db.add(model(**{**pk, **payload}))
                    result["created"] += 1
        except Exception as e:
            result["errors"].append(f"{model.__tablename__}/{pk}: {e}")


def _import_raw_upsert(
    db: Session,
    table: str,
    *,
    conflict_cols: List[str],
    fields: List[str],
    rows: List[Dict[str, Any]],
    result: Dict[str, Any],
    json_fields: Optional[Set[str]] = None,
) -> None:
    if not table_exists(db, table):
        result["errors"].append(f"{table}: 目标库缺少表，请先执行迁移")
        return
    if not rows:
        return

    json_cols = set(json_fields or ())
    bind = db.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    prepared: List[Dict[str, Any]] = []
    for raw in rows:
        row = {}
        ok = True
        for f in fields:
            v = raw.get(f)
            if f in conflict_cols and (v is None or v == ""):
                ok = False
                break
            if f.endswith("_at") or f in ("computed_at", "updated_at", "collected_at"):
                v = parse_dt(v)
            elif f in json_cols:
                v = _json_bind(v)
            row[f] = v
        if not ok:
            result["skipped"] += 1
            continue
        prepared.append(row)

    if not prepared:
        return

    def _ph(f: str) -> str:
        if dialect == "postgresql" and f in json_cols:
            return f"CAST(:{f} AS jsonb)"
        return f":{f}"

    if dialect == "postgresql":
        col_list = ", ".join(fields)
        placeholders = ", ".join(_ph(f) for f in fields)
        updates = [f for f in fields if f not in conflict_cols]
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates) if updates else ""
        conflict = ", ".join(conflict_cols)
        sql = text(
            f"""
            INSERT INTO {table} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({conflict}) DO UPDATE SET {set_clause}
            """
            if set_clause
            else f"""
            INSERT INTO {table} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({conflict}) DO NOTHING
            """
        )
        for i in range(0, len(prepared), UPSERT_CHUNK):
            chunk = prepared[i : i + UPSERT_CHUNK]
            try:
                db.connection().execute(sql, chunk)
                result["updated"] += len(chunk)
                db.commit()
            except Exception as e:
                db.rollback()
                result["errors"].append(f"{table} bulk@{i}: {e}")
        return

    # SQLite / 其它：逐行（json 列存文本）
    for row in prepared:
        try:
            with db.begin_nested():
                where = " AND ".join(f"{c} = :{c}" for c in conflict_cols)
                exists = db.execute(
                    text(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1"),
                    {c: row[c] for c in conflict_cols},
                ).fetchone()
                if exists:
                    sets = ", ".join(f"{f} = :{f}" for f in fields if f not in conflict_cols)
                    if sets:
                        db.execute(
                            text(
                                f"UPDATE {table} SET {sets} WHERE {where}"
                            ),
                            row,
                        )
                    result["updated"] += 1
                else:
                    cols = ", ".join(fields)
                    ph = ", ".join(f":{f}" for f in fields)
                    db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({ph})"), row)
                    result["created"] += 1
        except Exception as e:
            result["errors"].append(f"{table}/{row}: {e}")
    db.commit()


def import_computed_results(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    result = empty_result()
    items = (bundle or {}).get("items") or {}
    want = tables or set(COMPUTED_TABLES)

    gms_ids = _cfg_id_by_name(db, GMSStrategyConfig)
    urt_ids = _cfg_id_by_name(db, URTStrategyConfig)
    csb_ids = _cfg_id_by_name(db, CSBStrategyConfig)
    sbbr_ids = _cfg_id_by_name(db, SBBRStrategyConfig)
    rpe_ids = _cfg_id_by_name(db, RPEStrategyConfig)

    if "rs_ratings" in want:
        rows = items.get("rs_ratings") or []
        prepared = []
        for raw in rows:
            code = str(raw.get("code") or "").strip()
            d = str(raw.get("date") or "").strip()[:10]
            mt = str(raw.get("market_type") or "CN").strip() or "CN"
            if not code or not d:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "code": code, "date": d, "market_type": mt})
        _upsert_orm(
            db,
            RSRatings,
            pk_fields=("code", "date", "market_type"),
            rows=prepared,
            result=result,
        )
        db.commit()

    if "gms_signal_trace" in want:
        prepared = []
        for raw in items.get("gms_signal_trace") or []:
            cid = _resolve_config_id(raw, gms_ids, table="gms_signal_trace", result=result)
            if cid is None:
                continue
            code = str(raw.get("code") or "").strip()
            d = str(raw.get("date") or "").strip()[:10]
            mt = str(raw.get("market_type") or "CN").strip() or "CN"
            if not code or not d:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "code": code, "date": d, "market_type": mt, "config_id": cid})
        _upsert_orm(
            db,
            GMSSignalTrace,
            pk_fields=("code", "date", "market_type", "config_id"),
            rows=prepared,
            result=result,
        )
        db.commit()

    if "urt_signal_trace" in want:
        prepared = []
        for raw in items.get("urt_signal_trace") or []:
            cid = _resolve_config_id(raw, urt_ids, table="urt_signal_trace", result=result)
            if cid is None:
                continue
            code = str(raw.get("code") or "").strip()
            d = str(raw.get("date") or "").strip()[:10]
            if not code or not d:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "code": code, "date": d, "config_id": cid})
        _upsert_orm(
            db,
            URTSignalTrace,
            pk_fields=("code", "date", "config_id"),
            rows=prepared,
            result=result,
        )
        db.commit()

    if "csb_signal_trace" in want:
        prepared = []
        for raw in items.get("csb_signal_trace") or []:
            cid = _resolve_config_id(raw, csb_ids, table="csb_signal_trace", result=result)
            if cid is None:
                continue
            code = str(raw.get("code") or "").strip()
            td = parse_date(raw.get("trade_date"))
            st = str(raw.get("signal_type") or "").strip()
            if not code or not td or not st:
                result["skipped"] += 1
                continue
            prepared.append(
                {**raw, "code": code, "trade_date": td, "config_id": cid, "signal_type": st}
            )
        _upsert_orm(
            db,
            CSBSignalTrace,
            pk_fields=("code", "trade_date", "config_id", "signal_type"),
            rows=prepared,
            result=result,
            skip_fields={"id"},
        )
        db.commit()

    if "sbbr_signal_trace" in want:
        prepared = []
        for raw in items.get("sbbr_signal_trace") or []:
            cid = _resolve_config_id(raw, sbbr_ids, table="sbbr_signal_trace", result=result)
            if cid is None:
                continue
            code = str(raw.get("code") or "").strip()
            td = parse_date(raw.get("trade_date"))
            if not code or not td:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "code": code, "trade_date": td, "config_id": cid})
        _upsert_orm(
            db,
            SBBRSignalTrace,
            pk_fields=("code", "trade_date", "config_id"),
            rows=prepared,
            result=result,
            skip_fields={"id"},
        )
        db.commit()

    if "rpe_signal_trace" in want:
        prepared = []
        for raw in items.get("rpe_signal_trace") or []:
            cid = _resolve_config_id(raw, rpe_ids, table="rpe_signal_trace", result=result)
            if cid is None:
                continue
            code = str(raw.get("code") or "").strip()
            td = parse_date(raw.get("trade_date"))
            mt = str(raw.get("market_type") or "CN").strip() or "CN"
            if not code or not td:
                result["skipped"] += 1
                continue
            prepared.append(
                {**raw, "code": code, "trade_date": td, "market_type": mt, "config_id": cid}
            )
        _upsert_orm(
            db,
            RPESignalTrace,
            pk_fields=("code", "trade_date", "market_type", "config_id"),
            rows=prepared,
            result=result,
            skip_fields={"id"},
        )
        db.commit()

    if "index_historical_quotes" in want:
        prepared = []
        for raw in items.get("index_historical_quotes") or []:
            ts = str(raw.get("ts_code") or "").strip()
            td = parse_date(raw.get("trade_date"))
            if not ts or not td:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "ts_code": ts, "trade_date": td})
        _upsert_orm(
            db,
            IndexHistoricalQuotes,
            pk_fields=("ts_code", "trade_date"),
            rows=prepared,
            result=result,
        )
        db.commit()

    if "board_fund_flow_daily" in want:
        prepared = []
        for raw in items.get("board_fund_flow_daily") or []:
            kind = str(raw.get("board_kind") or "").strip()
            src = str(raw.get("board_code_source") or "tonghuashun").strip()
            code = str(raw.get("board_code") or "").strip()
            td = parse_date(raw.get("trade_date"))
            if not kind or not code or not td:
                result["skipped"] += 1
                continue
            prepared.append(
                {
                    **raw,
                    "board_kind": kind,
                    "board_code_source": src,
                    "board_code": code,
                    "trade_date": td,
                }
            )
        _upsert_orm(
            db,
            BoardFundFlowDaily,
            pk_fields=("board_kind", "board_code_source", "board_code", "trade_date"),
            rows=prepared,
            result=result,
        )
        db.commit()

    if "stock_zt_pool_daily" in want:
        _import_raw_upsert(
            db,
            "stock_zt_pool_daily",
            conflict_cols=["code", "trade_date"],
            fields=ZT_POOL_FIELDS,
            rows=items.get("stock_zt_pool_daily") or [],
            result=result,
        )

    if "market_daily_review" in want:
        _import_raw_upsert(
            db,
            "market_daily_review",
            conflict_cols=["trade_date"],
            fields=REVIEW_FIELDS,
            rows=items.get("market_daily_review") or [],
            result=result,
            json_fields=set(REVIEW_JSON_FIELDS),
        )

    if "market_daily_mainline_hits" in want:
        _import_raw_upsert(
            db,
            "market_daily_mainline_hits",
            conflict_cols=["trade_date", "board_type", "board_code"],
            fields=MAINLINE_FIELDS,
            rows=items.get("market_daily_mainline_hits") or [],
            result=result,
            json_fields=set(MAINLINE_JSON_FIELDS),
        )

    if "stock_recommend_brief" in want:
        prepared = []
        for raw in items.get("stock_recommend_brief") or []:
            hz = str(raw.get("horizon") or "").strip()
            ad = parse_date(raw.get("asof_date"))
            if not hz or not ad:
                result["skipped"] += 1
                continue
            prepared.append({**raw, "horizon": hz, "asof_date": ad})
        _upsert_orm(
            db,
            StockRecommendBrief,
            pk_fields=("horizon", "asof_date"),
            rows=prepared,
            result=result,
            skip_fields={"id"},
        )
        db.commit()

    return result


def iter_computed_results_push_chunks(
    bundle: Dict[str, Any],
    *,
    chunk_rows: int,
) -> List[Dict[str, Any]]:
    """按表、按行切开 computed_results bundle。"""
    chunk_rows = max(1, int(chunk_rows))
    items = (bundle or {}).get("items") or {}
    base = {k: v for k, v in bundle.items() if k != "items"}

    parts: List[tuple] = []
    for key in COMPUTED_TABLES:
        rows = list(items.get(key) or [])
        if not rows:
            continue
        for i in range(0, len(rows), chunk_rows):
            parts.append((key, rows[i : i + chunk_rows], i, len(rows)))

    if not parts:
        return [bundle]

    out: List[Dict[str, Any]] = []
    for idx, (key, rows, offset, total) in enumerate(parts):
        part = dict(base)
        part["items"] = {key: rows}
        part["chunk"] = {
            "table": key,
            "offset": offset,
            "size": len(rows),
            "total": total,
            "part": idx + 1,
            "parts": len(parts),
        }
        out.append(part)
    return out
