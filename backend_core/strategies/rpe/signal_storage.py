"""RPE 信号落库。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def delete_traces_for_code_config(db, *, code: str, config_id: int, market_type: str = "CN") -> int:
    from backend_api.models import RPESignalTrace

    code_n = str(code or "").strip()
    if code_n.isdigit() and len(code_n) <= 6:
        code_n = code_n.zfill(6)
    n = (
        db.query(RPESignalTrace)
        .filter(
            RPESignalTrace.code == code_n,
            RPESignalTrace.config_id == int(config_id),
            RPESignalTrace.market_type == (market_type or "CN"),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: str,
) -> int:
    from backend_api.models import RPESignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or r.get("symbol") or "").strip()
        if not code:
            continue
        date_s = str(r.get("date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue
        existing = (
            db.query(RPESignalTrace)
            .filter(
                RPESignalTrace.code == code,
                RPESignalTrace.trade_date == d,
                RPESignalTrace.config_id == int(config_id),
                RPESignalTrace.market_type == (r.get("market_type") or "CN"),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            sector_id=r.get("sector_id"),
            sector_name=r.get("sector_name"),
            z_score=r.get("z_score"),
            ratio=r.get("ratio"),
            signal_type=r.get("signal_type"),
            entry_signal=bool(r.get("entry_signal")),
            watch_only=bool(r.get("watch_only")),
            trend_veto=bool(r.get("trend_veto")),
            sector_slope=r.get("sector_slope"),
            support_levels=r.get("support_levels") or [],
            resistance_levels=r.get("resistance_levels") or [],
            nearest_support=r.get("nearest_support"),
            nearest_resistance=r.get("nearest_resistance"),
            structure_valid=bool(r.get("structure_valid")),
            liquidity_ok=bool(r.get("liquidity_ok")),
            close_price=r.get("close"),
            detail=r.get("detail") or {},
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                RPESignalTrace(
                    code=code,
                    trade_date=d,
                    market_type=r.get("market_type") or "CN",
                    config_id=int(config_id),
                    created_at=datetime.now(),
                    **payload,
                )
            )
        n += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("RPE upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: int,
    entry_only: bool = False,
    signal_type: str = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from backend_api.models import RPESignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(RPESignalTrace).filter(
        RPESignalTrace.trade_date == d,
        RPESignalTrace.config_id == int(config_id),
    )
    if entry_only:
        q = q.filter(RPESignalTrace.entry_signal.is_(True))
    if signal_type:
        q = q.filter(RPESignalTrace.signal_type == signal_type)
    rows = (
        q.order_by(RPESignalTrace.entry_signal.desc(), RPESignalTrace.z_score.asc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else trade_date,
                "market_type": r.market_type,
                "sector_id": r.sector_id,
                "sector_name": r.sector_name,
                "z_score": r.z_score,
                "ratio": r.ratio,
                "signal_type": r.signal_type,
                "entry_signal": r.entry_signal,
                "watch_only": r.watch_only,
                "trend_veto": r.trend_veto,
                "sector_slope": r.sector_slope,
                "support_levels": r.support_levels or [],
                "resistance_levels": r.resistance_levels or [],
                "nearest_support": r.nearest_support,
                "nearest_resistance": r.nearest_resistance,
                "structure_valid": r.structure_valid,
                "liquidity_ok": r.liquidity_ok,
                "close": r.close_price,
                "detail": r.detail or {},
                "config_id": r.config_id,
            }
        )
    return out


def _panel_as_of(
    panel: Dict[str, List[Dict[str, Any]]], trade_date: str
) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for code, bars in panel.items():
        sliced = [b for b in bars if b.get("date") and b["date"] <= trade_date]
        if sliced:
            out[code] = sliced
    return out


def recompute_trace_for_stock(
    db,
    *,
    code: str,
    config_id: int,
    config: Optional[Dict[str, Any]] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    对单股按**固定主板块**按交易日滚动重算 RPE 信号，写入 rpe_signal_trace。

    - 先删除该 code + config_id 旧记录
    - 主板块：行业优先（成分最多）；无行业则概念；全程只用这一板块，避免追溯页按日跳变
    - 面板可拉全历史以便逐日 as-of；**每个评估日**内 Z/KDE/流动性仍只使用 config.lookback_days
      （与日终选股一致，避免全历史 KDE 带宽过大导致支撑缺失）
    - 每个可评交易日写入一行（含无入场信号日，便于追溯页查看 Z 序列）
    返回写入条数。
    """
    from .config import RPEConfigManager
    from .data_loader import RPEDataLoader, _norm_code
    from .sector_benchmark import compute_vwap_benchmark, sector_slope
    from .strategy_engine import RPEStrategyEngine

    code_n = _norm_code(code)
    cfg = config or RPEConfigManager().get_config(config_id)
    z_window = int(cfg.get("z_window", 40))
    slope_window = int(cfg.get("sector_slope_window", 60))
    min_members = int((cfg.get("scan") or {}).get("min_sector_members", 5))
    min_need = z_window + 5

    delete_traces_for_code_config(db, code=code_n, config_id=int(config_id))

    loader = RPEDataLoader(db)
    engine = RPEStrategyEngine(db_session=db, config=cfg)

    primary = loader.resolve_primary_board(code_n, board_kind="industry", allow_fallback=True)
    if not primary:
        logger.info("RPE 单股重算 %s 无所属板块，跳过", code_n)
        return 0

    kind = str(primary.get("board_kind") or "industry")
    boards = [
        {
            "board_code": primary["board_code"],
            "board_name": primary.get("board_name") or primary["board_code"],
        }
    ]

    target_bars = loader.load_bars(code_n, limit=None)
    if len(target_bars) < min_need:
        logger.info("RPE 单股重算 %s 历史不足 bars=%s need=%s", code_n, len(target_bars), min_need)
        return 0

    dates = [b["date"] for b in target_bars]
    eval_dates = dates[min_need - 1 :]
    if not eval_dates:
        return 0

    board_ctx: List[Dict[str, Any]] = []
    for b in boards:
        members = loader.load_board_members(b["board_code"], board_kind=kind)
        if len(members) < min_members:
            continue
        codes = [m["code"] for m in members]
        name_map = {m["code"]: m.get("name") for m in members}
        if code_n not in {_norm_code(c) for c in codes}:
            codes.append(code_n)
        panel = loader.load_sector_panel(codes, lookback=None)
        if code_n not in panel or len(panel) < min_members:
            continue
        board_ctx.append(
            {
                "board_code": b["board_code"],
                "board_name": b.get("board_name") or b["board_code"],
                "name_map": name_map,
                "panel": panel,
            }
        )

    if not board_ctx:
        logger.info("RPE 单股重算 %s 主板块成分不足，跳过 primary=%s", code_n, primary.get("board_code"))
        return 0

    logger.info(
        "RPE 单股全历史重算 %s config_id=%s primary_board=%s(%s) evaluable=%s",
        code_n,
        config_id,
        board_ctx[0]["board_code"],
        kind,
        len(eval_dates),
    )

    rows: List[Dict[str, Any]] = []
    total = len(eval_dates)
    batch_size = 80
    ctx = board_ctx[0]

    for idx, trade_date in enumerate(eval_dates):
        if progress_cb:
            progress_cb(idx + 1, total, f"正在计算 {trade_date}（{idx + 1}/{total}）")
        try:
            panel_d = _panel_as_of(ctx["panel"], trade_date)
            if code_n not in panel_d or len(panel_d[code_n]) < min_need:
                continue
            if len(panel_d) < min_members:
                continue
            date_members = loader.build_date_members(panel_d)
            benchmark = compute_vwap_benchmark(date_members)
            if len(benchmark) < min_need:
                continue
            slope = sector_slope(benchmark, slope_window)
            row = engine.evaluate_in_sector(
                code_n,
                sector_id=ctx["board_code"],
                sector_name=ctx["board_name"],
                panel=panel_d,
                benchmark=benchmark,
                slope=slope,
                trade_date=trade_date,
                config=cfg,
                name=ctx["name_map"].get(code_n),
            )
            if row:
                rows.append(row)
        except Exception as e:
            logger.debug(
                "RPE recompute skip %s board=%s day=%s: %s",
                code_n,
                ctx.get("board_code"),
                trade_date,
                e,
            )

        if len(rows) >= batch_size:
            upsert_signal_traces(db, rows, config_id=int(config_id), trade_date=trade_date)
            rows = []

    if rows:
        upsert_signal_traces(db, rows, config_id=int(config_id), trade_date=eval_dates[-1])

    from backend_api.models import RPESignalTrace

    written = (
        db.query(RPESignalTrace)
        .filter(RPESignalTrace.code == code_n, RPESignalTrace.config_id == int(config_id))
        .count()
    )
    if progress_cb:
        progress_cb(written, written, f"写入完成（{written}/{written}）")
    logger.info("RPE 单股重算完成 %s written=%s", code_n, written)
    return int(written)
