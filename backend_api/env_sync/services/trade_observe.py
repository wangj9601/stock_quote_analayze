# -*- coding: utf-8 -*-
"""交易观察 / 正式交易 / 储备箱 export/import（username 对齐）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Session

from backend_api.env_sync.bundle import (
    empty_result,
    json_safe,
    make_bundle,
    merge_results,
    parse_date,
    parse_dt,
    table_exists,
)
from backend_api.models import (
    GmsFormalTrade,
    GmsTradeObserveHistory,
    GmsTradeObserveStock,
    RPEFormalTrade,
    RPETradeObserveHistory,
    RPETradeObserveStock,
    SBBRFormalTrade,
    SBBRReserveBox,
    SBBRTradeObserveStock,
    UrtFormalTrade,
    UrtTradeObserveHistory,
    UrtTradeObserveStock,
    User,
    URTStrategyConfig,
)

import logging

logger = logging.getLogger(__name__)


def _username_map(db: Session) -> Dict[int, str]:
    return {int(u.id): str(u.username) for u in db.query(User.id, User.username).all()}


def _user_id_by_username(db: Session) -> Dict[str, int]:
    return {str(u.username): int(u.id) for u in db.query(User.id, User.username).all()}


def export_trade_observe(
    db: Session,
    *,
    env_label: str = "local",
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = set(tables) if tables else None
    umap = _username_map(db)
    urt_cfg_names: Dict[int, Any] = {}
    if table_exists(db, "urt_strategy_configs"):
        urt_cfg_names = {
            int(c.id): c.name
            for c in db.query(URTStrategyConfig.id, URTStrategyConfig.name).all()
        }

    def pack_observe(model: Type, with_urt_cfg: bool = False) -> List[Dict]:
        tname = getattr(model, "__tablename__", "") or ""
        if tname and not table_exists(db, tname):
            logger.warning("env_sync export skip missing table: %s", tname)
            return []
        out = []
        for r in db.query(model).all():
            uname = umap.get(int(r.user_id))
            if not uname:
                continue
            d = {
                "username": uname,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "signal_snapshot_json": json_safe(r.signal_snapshot_json),
                "signal_date": json_safe(getattr(r, "signal_date", None)),
                "created_at": json_safe(getattr(r, "created_at", None)),
                "updated_at": json_safe(getattr(r, "updated_at", None)),
                "_source_id": r.id,
            }
            if hasattr(r, "key_focus_flag"):
                d["key_focus_flag"] = bool(r.key_focus_flag)
            if hasattr(r, "latest_close_price"):
                d["latest_close_price"] = r.latest_close_price
                d["latest_close_date"] = json_safe(r.latest_close_date)
            if with_urt_cfg and getattr(r, "config_id", None):
                d["config_id"] = r.config_id
                d["config_name"] = urt_cfg_names.get(int(r.config_id))
            out.append(d)
        return out

    def pack_history(model: Type, with_urt_cfg: bool = False) -> List[Dict]:
        tname = getattr(model, "__tablename__", "") or ""
        if tname and not table_exists(db, tname):
            logger.warning("env_sync export skip missing table: %s", tname)
            return []
        out = []
        for r in db.query(model).all():
            uname = umap.get(int(r.user_id))
            if not uname:
                continue
            d = {
                "username": uname,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "signal_snapshot_json": json_safe(r.signal_snapshot_json),
                "signal_date": json_safe(getattr(r, "signal_date", None)),
                "observe_created_at": json_safe(getattr(r, "observe_created_at", None)),
                "observe_updated_at": json_safe(getattr(r, "observe_updated_at", None)),
                "source_observe_id": getattr(r, "source_observe_id", None),
                "removed_at": json_safe(r.removed_at),
                "_source_id": r.id,
            }
            if with_urt_cfg and getattr(r, "config_id", None):
                d["config_id"] = r.config_id
                d["config_name"] = urt_cfg_names.get(int(r.config_id))
            out.append(d)
        return out

    def pack_formal(model: Type, extra_fields: List[str]) -> List[Dict]:
        tname = getattr(model, "__tablename__", "") or ""
        if tname and not table_exists(db, tname):
            logger.warning("env_sync export skip missing table: %s", tname)
            return []
        out = []
        for r in db.query(model).all():
            uname = umap.get(int(r.user_id))
            if not uname:
                continue
            d = {
                "username": uname,
                "market": r.market,
                "code": r.code,
                "name": r.name,
                "source_observe_id": r.source_observe_id,
                "entry_price": r.entry_price,
                "exit_price": r.exit_price,
                "status": r.status,
                "signal_date": json_safe(r.signal_date),
                "signal_snapshot_json": json_safe(r.signal_snapshot_json),
                "notes": r.notes,
                "entry_at": json_safe(r.entry_at),
                "exit_at": json_safe(r.exit_at),
                "pnl_amount": r.pnl_amount,
                "pnl_percent": r.pnl_percent,
                "created_at": json_safe(r.created_at),
                "updated_at": json_safe(r.updated_at),
                "_source_id": r.id,
                "external_key": f"{uname}|{r.market}|{r.code}|{json_safe(r.entry_at)}|{r.status}",
            }
            for f in extra_fields:
                if hasattr(r, f):
                    d[f] = json_safe(getattr(r, f))
            out.append(d)
        return out

    reserves = []
    if table_exists(db, "sbbr_reserve_box"):
        for r in db.query(SBBRReserveBox).all():
            uname = umap.get(int(r.user_id))
            if not uname:
                continue
            reserves.append(
                {
                    "username": uname,
                    "stock_code": r.stock_code,
                    "stock_name": r.stock_name,
                    "industry_note": r.industry_note,
                    "status": r.status,
                    "created_at": json_safe(r.created_at),
                    "updated_at": json_safe(r.updated_at),
                    "_source_id": r.id,
                }
            )
    else:
        logger.warning("env_sync export skip missing table: sbbr_reserve_box")

    items = {
        "gms_trade_observe_stocks": pack_observe(GmsTradeObserveStock),
        "gms_trade_observe_history": pack_history(GmsTradeObserveHistory),
        "gms_formal_trades": pack_formal(GmsFormalTrade, ["position_lots"]),
        "urt_trade_observe_stocks": pack_observe(UrtTradeObserveStock, with_urt_cfg=True),
        "urt_trade_observe_history": pack_history(UrtTradeObserveHistory, with_urt_cfg=True),
        "urt_formal_trades": pack_formal(UrtFormalTrade, ["position_lots"]),
        "rpe_trade_observe_stocks": pack_observe(RPETradeObserveStock),
        "rpe_trade_observe_history": pack_history(RPETradeObserveHistory),
        "rpe_formal_trades": pack_formal(
            RPEFormalTrade,
            ["structure_support", "structure_resistance", "exit_reason", "last_eval_json"],
        ),
        "sbbr_trade_observe_stocks": pack_observe(SBBRTradeObserveStock),
        "sbbr_formal_trades": pack_formal(
            SBBRFormalTrade,
            [
                "stage",
                "budget_total",
                "allocated_pct",
                "defense_anchor_low",
                "defense_buffer_pct",
                "exit_reason",
                "last_eval_json",
            ],
        ),
        "sbbr_reserve_box": reserves,
    }
    if selected is not None:
        items = {k: v for k, v in items.items() if k in selected}
    return make_bundle(module="trade_observe", items=items, env_label=env_label)


def _resolve_urt_config_id(db: Session, raw: Dict[str, Any]) -> Optional[int]:
    name = (raw.get("config_name") or "").strip()
    if name:
        row = db.query(URTStrategyConfig).filter(URTStrategyConfig.name == name).first()
        if row:
            return int(row.id)
    return None


def _upsert_observe(
    db: Session,
    model: Type,
    rows: List[Dict],
    user_map: Dict[str, int],
    *,
    with_urt_cfg: bool = False,
    gms_extra: bool = False,
) -> Dict[str, Any]:
    result = empty_result()
    for raw in rows:
        uname = str(raw.get("username") or "").strip()
        uid = user_map.get(uname)
        if not uid:
            result["skipped"] += 1
            result["errors"].append(f"user missing: {uname}")
            continue
        market = str(raw.get("market") or "CN").strip().upper() or "CN"
        code = str(raw.get("code") or "").strip()
        if not code:
            result["skipped"] += 1
            continue
        try:
            existing = (
                db.query(model)
                .filter(
                    model.user_id == uid,
                    model.market == market,
                    model.code == code,
                )
                .first()
            )
            fields = {
                "name": raw.get("name"),
                "signal_snapshot_json": raw.get("signal_snapshot_json"),
                "signal_date": parse_date(raw.get("signal_date")),
            }
            if gms_extra:
                fields["key_focus_flag"] = bool(raw.get("key_focus_flag") or False)
                fields["latest_close_price"] = raw.get("latest_close_price")
                fields["latest_close_date"] = parse_date(raw.get("latest_close_date"))
            if with_urt_cfg:
                fields["config_id"] = _resolve_urt_config_id(db, raw)
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                if hasattr(existing, "updated_at"):
                    existing.updated_at = datetime.now()
                result["updated"] += 1
            else:
                obj = model(user_id=uid, market=market, code=code, **fields)
                if raw.get("created_at") and hasattr(obj, "created_at"):
                    dt = parse_dt(raw.get("created_at"))
                    if dt:
                        obj.created_at = dt
                db.add(obj)
                result["created"] += 1
        except Exception as e:
            result["errors"].append(f"observe {uname}/{market}/{code}: {e}")
    return result


def _import_history(
    db: Session,
    model: Type,
    rows: List[Dict],
    user_map: Dict[str, int],
    *,
    with_urt_cfg: bool = False,
) -> Dict[str, Any]:
    result = empty_result()
    for raw in rows:
        uname = str(raw.get("username") or "").strip()
        uid = user_map.get(uname)
        if not uid:
            result["skipped"] += 1
            result["errors"].append(f"user missing: {uname}")
            continue
        market = str(raw.get("market") or "CN").strip().upper() or "CN"
        code = str(raw.get("code") or "").strip()
        removed_at = parse_dt(raw.get("removed_at")) or datetime.now()
        try:
            existing = (
                db.query(model)
                .filter(
                    model.user_id == uid,
                    model.market == market,
                    model.code == code,
                    model.removed_at == removed_at,
                )
                .first()
            )
            if existing:
                result["skipped"] += 1
                continue
            kwargs: Dict[str, Any] = {
                "user_id": uid,
                "market": market,
                "code": code,
                "name": raw.get("name"),
                "signal_snapshot_json": raw.get("signal_snapshot_json"),
                "signal_date": parse_date(raw.get("signal_date")),
                "source_observe_id": raw.get("source_observe_id"),
                "removed_at": removed_at,
            }
            if hasattr(model, "observe_created_at"):
                kwargs["observe_created_at"] = parse_dt(raw.get("observe_created_at"))
                kwargs["observe_updated_at"] = parse_dt(raw.get("observe_updated_at"))
            if with_urt_cfg and hasattr(model, "config_id"):
                kwargs["config_id"] = _resolve_urt_config_id(db, raw)
            db.add(model(**kwargs))
            result["created"] += 1
        except Exception as e:
            result["errors"].append(f"history {uname}/{code}: {e}")
    return result


def _formal_match(db: Session, model: Type, uid: int, raw: Dict) -> Any:
    market = str(raw.get("market") or "CN").strip().upper() or "CN"
    code = str(raw.get("code") or "").strip()
    status = str(raw.get("status") or "open")
    entry_at = parse_dt(raw.get("entry_at"))
    q = db.query(model).filter(
        model.user_id == uid,
        model.market == market,
        model.code == code,
        model.status == status,
    )
    if entry_at:
        q = q.filter(model.entry_at == entry_at)
    return q.first()


def _import_formal(
    db: Session,
    model: Type,
    rows: List[Dict],
    user_map: Dict[str, int],
    extra_fields: List[str],
) -> Dict[str, Any]:
    result = empty_result()
    for raw in rows:
        uname = str(raw.get("username") or "").strip()
        uid = user_map.get(uname)
        if not uid:
            result["skipped"] += 1
            result["errors"].append(f"user missing: {uname}")
            continue
        try:
            existing = _formal_match(db, model, uid, raw)
            base = {
                "name": raw.get("name"),
                "source_observe_id": None,  # 跨环境 observe id 不可靠，清空
                "entry_price": float(raw.get("entry_price") or 0),
                "exit_price": raw.get("exit_price"),
                "status": str(raw.get("status") or "open"),
                "signal_date": parse_date(raw.get("signal_date")),
                "signal_snapshot_json": raw.get("signal_snapshot_json"),
                "notes": raw.get("notes"),
                "entry_at": parse_dt(raw.get("entry_at")) or datetime.now(),
                "exit_at": parse_dt(raw.get("exit_at")),
                "pnl_amount": raw.get("pnl_amount"),
                "pnl_percent": raw.get("pnl_percent"),
            }
            for f in extra_fields:
                if f in raw:
                    base[f] = raw.get(f)
            market = str(raw.get("market") or "CN").strip().upper() or "CN"
            code = str(raw.get("code") or "").strip()
            if existing:
                for k, v in base.items():
                    setattr(existing, k, v)
                if hasattr(existing, "updated_at"):
                    existing.updated_at = datetime.now()
                result["updated"] += 1
            else:
                db.add(
                    model(
                        user_id=uid,
                        market=market,
                        code=code,
                        **base,
                    )
                )
                result["created"] += 1
        except Exception as e:
            result["errors"].append(f"formal {uname}/{raw.get('code')}: {e}")
    return result


def import_trade_observe(
    db: Session,
    bundle: Dict[str, Any],
    *,
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    items = (bundle or {}).get("items") or {}
    user_map = _user_id_by_username(db)
    result = empty_result()
    selected = set(tables) if tables else None

    def want(key: str) -> bool:
        return selected is None or key in selected

    if want("gms_trade_observe_stocks"):
        result = merge_results(
            result,
            _upsert_observe(
                db,
                GmsTradeObserveStock,
                items.get("gms_trade_observe_stocks") or [],
                user_map,
                gms_extra=True,
            ),
        )
    if want("gms_trade_observe_history"):
        result = merge_results(
            result,
            _import_history(
                db,
                GmsTradeObserveHistory,
                items.get("gms_trade_observe_history") or [],
                user_map,
            ),
        )
    if want("gms_formal_trades"):
        result = merge_results(
            result,
            _import_formal(
                db,
                GmsFormalTrade,
                items.get("gms_formal_trades") or [],
                user_map,
                ["position_lots"],
            ),
        )
    if want("urt_trade_observe_stocks"):
        result = merge_results(
            result,
            _upsert_observe(
                db,
                UrtTradeObserveStock,
                items.get("urt_trade_observe_stocks") or [],
                user_map,
                with_urt_cfg=True,
            ),
        )
    if want("urt_trade_observe_history"):
        result = merge_results(
            result,
            _import_history(
                db,
                UrtTradeObserveHistory,
                items.get("urt_trade_observe_history") or [],
                user_map,
                with_urt_cfg=True,
            ),
        )
    if want("urt_formal_trades"):
        result = merge_results(
            result,
            _import_formal(
                db,
                UrtFormalTrade,
                items.get("urt_formal_trades") or [],
                user_map,
                ["position_lots"],
            ),
        )
    if want("rpe_trade_observe_stocks"):
        result = merge_results(
            result,
            _upsert_observe(
                db,
                RPETradeObserveStock,
                items.get("rpe_trade_observe_stocks") or [],
                user_map,
            ),
        )
    if want("rpe_trade_observe_history"):
        result = merge_results(
            result,
            _import_history(
                db,
                RPETradeObserveHistory,
                items.get("rpe_trade_observe_history") or [],
                user_map,
            ),
        )
    if want("rpe_formal_trades"):
        result = merge_results(
            result,
            _import_formal(
                db,
                RPEFormalTrade,
                items.get("rpe_formal_trades") or [],
                user_map,
                ["structure_support", "structure_resistance", "exit_reason", "last_eval_json"],
            ),
        )
    if want("sbbr_trade_observe_stocks"):
        result = merge_results(
            result,
            _upsert_observe(
                db,
                SBBRTradeObserveStock,
                items.get("sbbr_trade_observe_stocks") or [],
                user_map,
            ),
        )
    if want("sbbr_formal_trades"):
        result = merge_results(
            result,
            _import_formal(
                db,
                SBBRFormalTrade,
                items.get("sbbr_formal_trades") or [],
                user_map,
                [
                    "stage",
                    "budget_total",
                    "allocated_pct",
                    "defense_anchor_low",
                    "defense_buffer_pct",
                    "exit_reason",
                    "last_eval_json",
                ],
            ),
        )

    if want("sbbr_reserve_box"):
        for raw in items.get("sbbr_reserve_box") or []:
            uname = str(raw.get("username") or "").strip()
            uid = user_map.get(uname)
            if not uid:
                result["skipped"] += 1
                result["errors"].append(f"user missing: {uname}")
                continue
            code = str(raw.get("stock_code") or "").strip()
            if not code:
                continue
            try:
                existing = (
                    db.query(SBBRReserveBox)
                    .filter(SBBRReserveBox.user_id == uid, SBBRReserveBox.stock_code == code)
                    .first()
                )
                fields = {
                    "stock_name": raw.get("stock_name"),
                    "industry_note": raw.get("industry_note"),
                    "status": raw.get("status") or "watching",
                }
                if existing:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    existing.updated_at = datetime.now()
                    result["updated"] += 1
                else:
                    db.add(SBBRReserveBox(user_id=uid, stock_code=code, **fields))
                    result["created"] += 1
            except Exception as e:
                result["errors"].append(f"reserve {uname}/{code}: {e}")

    db.commit()
    return result
