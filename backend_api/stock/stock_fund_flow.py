from fastapi import APIRouter, Query, BackgroundTasks, File, Form, UploadFile, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional

import akshare as ak

from backend_api.database import get_db
from backend_api.utils.equity_code import is_hk_equity_code, normalize_equity_code
from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
    analyze_fund_flow_series,
    collect_ths_fund_flow_daily,
    normalize_ths_code,
)

router = APIRouter(prefix="/api/stock_fund_flow", tags=["stock_fund_flow"])


def safe_float(value):
    try:
        if value in [None, "", "-"]:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


@router.get("/history")
async def get_history(code: str = Query(None, description="股票代码")):
    print(f"[get_history] 输入参数: code={code}")
    if not code:
        print("[get_history] 缺少参数code")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        print(f"[get_history] 调用ak.stock_individual_fund_flow_rank")
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        if df is None or df.empty:
            print(f"[get_history] 未找到股票代码: {code} 的资金流向数据")
            return JSONResponse(
                {"success": False, "message": f"未找到股票代码: {code} 的资金流向数据"},
                status_code=404,
            )
        df_filtered = df[df["代码"] == code]
        if df_filtered.empty:
            print(f"[get_history] 未找到股票代码: {code} 的资金流向数据")
            return JSONResponse(
                {"success": False, "message": f"未找到股票代码: {code} 的资金流向数据"},
                status_code=404,
            )
        fund_flow = df_filtered.to_dict(orient="records")[0]
        print(f"[get_history] 输出数据: {fund_flow}")
        return JSONResponse({"success": True, "data": fund_flow})
    except Exception as e:
        print(f"[get_history] 查询个股资金流向异常: {e}")
        import traceback

        print(traceback.format_exc())
        return JSONResponse(
            {"success": False, "message": f"查询个股资金流向异常: {e}"}, status_code=500
        )


def _query_em_daily_rows(db: Session, code: str, days: int = 60) -> list:
    """从 stock_fund_flow_em_daily 读分档序列（升序）。"""
    code_n = normalize_ths_code(code) or normalize_equity_code(code) or str(code).strip()
    days = max(1, min(int(days or 60), 250))
    rows = db.execute(
        text(
            """
            SELECT code, trade_date,
                   main_net_inflow, main_net_inflow_pct,
                   super_large_net_inflow, super_large_net_inflow_pct,
                   large_net_inflow, large_net_inflow_pct,
                   mid_net_inflow, mid_net_inflow_pct,
                   small_net_inflow, small_net_inflow_pct,
                   close_price, change_percent, source, updated_at
            FROM stock_fund_flow_em_daily
            WHERE code = :code
            ORDER BY trade_date DESC
            LIMIT :lim
            """
        ),
        {"code": code_n, "lim": days},
    ).mappings().all()
    out = [dict(r) for r in rows]
    out.reverse()
    return out


@router.get("/em/daily")
async def get_em_daily(
    code: str = Query(..., description="股票代码"),
    days: int = Query(60, ge=1, le=250, description="回看交易日数"),
    db: Session = Depends(get_db),
):
    """读取东财个股主力/分档资金流日表（本地入库）。"""
    if is_hk_equity_code(code):
        return JSONResponse(
            {"success": False, "message": "东财主力分档仅支持 A 股"},
            status_code=400,
        )
    try:
        series = _query_em_daily_rows(db, code, days=days)
        if not series:
            return JSONResponse(
                {
                    "success": False,
                    "message": "暂无东财资金流分档数据（需日终采集或回填）",
                },
                status_code=404,
            )
        return {
            "success": True,
            "data": {
                "code": series[0].get("code") or code,
                "days_requested": days,
                "series_source": "stock_fund_flow_em_daily",
                "series": series,
                "disclaimer": "东财订单分档净流入，非机构身份",
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询东财资金流失败: {e}"},
            status_code=500,
        )


def compute_main_force_entry_response(
    db: Session, code: str, days: int = 60
) -> dict:
    """供 API 与 analysis bundle 复用。"""
    from backend_core.analysis.main_force_entry import compute_main_force_entry

    code_n = normalize_ths_code(code) or normalize_equity_code(code) or str(code).strip()
    days = max(5, min(int(days or 60), 250))
    em_series = _query_em_daily_rows(db, code_n, days=days)
    if not em_series:
        return {
            "success": False,
            "message": "暂无东财资金流分档数据（需日终采集或回填）",
        }

    first = em_series[0]["trade_date"]
    last = em_series[-1]["trade_date"]
    quotes = db.execute(
        text(
            """
            SELECT CAST(date AS VARCHAR(10)) AS trade_date,
                   open, high, low, close, volume, amount
            FROM historical_quotes
            WHERE code = :code
              AND CAST(date AS VARCHAR(10)) >= :d0
              AND CAST(date AS VARCHAR(10)) <= :d1
            ORDER BY date
            """
        ),
        {"code": code_n, "d0": first, "d1": last},
    ).mappings().all()
    quote_rows = [dict(r) for r in quotes]

    ths_rows = db.execute(
        text(
            """
            SELECT trade_date, net_amount
            FROM stock_fund_flow_daily
            WHERE code = :code AND trade_date >= :d0 AND trade_date <= :d1
            """
        ),
        {"code": code_n, "d0": first, "d1": last},
    ).mappings().all()
    ths_map = {
        str(r["trade_date"])[:10]: safe_float(r["net_amount"])
        for r in ths_rows
        if r.get("trade_date") is not None
    }

    board_nets = []
    try:
        board_rows = db.execute(
            text(
                """
                SELECT b.main_net_inflow
                FROM board_fund_flow_daily b
                INNER JOIN industry_board_constituents c
                  ON c.board_code = b.board_code
                 AND c.stock_code = :code
                WHERE CAST(b.trade_date AS VARCHAR(10)) >= :d0
                  AND CAST(b.trade_date AS VARCHAR(10)) <= :d1
                  AND b.board_kind = 'industry'
                ORDER BY b.trade_date DESC
                LIMIT 5
                """
            ),
            {"code": code_n, "d0": first, "d1": last},
        ).mappings().all()
        board_nets = [
            safe_float(r["main_net_inflow"])
            for r in board_rows
            if safe_float(r["main_net_inflow"]) is not None
        ]
    except Exception:
        board_nets = []

    data = compute_main_force_entry(
        code=code_n,
        em_rows=em_series,
        quote_rows=quote_rows,
        ths_net_by_date=ths_map,
        board_main_nets=board_nets or None,
        lookback_days=days,
    )
    sources = sorted(
        {
            str(r.get("source") or "").strip()
            for r in em_series
            if str(r.get("source") or "").strip()
        }
    )
    data["series_source"] = "+".join(sources) if sources else "stock_fund_flow_em_daily"
    return {"success": True, "data": data}


@router.get("/main_force_entry")
async def get_main_force_entry(
    code: str = Query(..., description="股票代码"),
    days: int = Query(60, ge=5, le=250, description="回看交易日数"),
    db: Session = Depends(get_db),
):
    """主力入场判定：时间窗口 + 净流入加权均价 + VP 旁证。"""
    if is_hk_equity_code(code):
        return JSONResponse(
            {"success": False, "message": "主力入场判定一期仅支持 A 股"},
            status_code=400,
        )
    try:
        body = compute_main_force_entry_response(db, code, days=days)
        if not body.get("success"):
            return JSONResponse(body, status_code=404)
        return body
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"主力入场判定失败: {e}"},
            status_code=500,
        )


@router.post("/em/collect")
async def trigger_em_collect(
    background_tasks: BackgroundTasks,
    code: Optional[str] = Query(None, description="单票代码；不传则活跃池批量"),
    trade_date: Optional[str] = Query(None, description="仅落该交易日 YYYY-MM-DD"),
    sync: bool = Query(False, description="true 则同步执行"),
    max_codes: int = Query(0, ge=0, description="批量时最多票数，0=不限制"),
):
    """触发东财个股主力/分档资金流采集写入 stock_fund_flow_em_daily。"""
    from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
        collect_em_stock_fund_flow_daily,
        collect_em_stock_fund_flow_for_code,
    )

    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )

    if code:
        code_n = normalize_ths_code(code) or str(code).strip()

        def _one():
            return collect_em_stock_fund_flow_for_code(
                code_n,
                min_date=trade_date,
                max_date=trade_date,
                keep_last_n=None if not trade_date else None,
            )

        if sync:
            try:
                return {"success": True, "data": _one()}
            except Exception as e:
                return JSONResponse(
                    {"success": False, "message": f"采集失败: {e}"}, status_code=500
                )
        background_tasks.add_task(_one)
        return {"success": True, "message": f"东财资金流采集已在后台启动: {code_n}"}

    def _batch():
        return collect_em_stock_fund_flow_daily(
            trade_date=trade_date,
            max_codes=max_codes or None,
        )

    if sync:
        try:
            return {"success": True, "data": _batch()}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"采集失败: {e}"}, status_code=500
            )
    background_tasks.add_task(_batch)
    return {"success": True, "message": "东财资金流批量采集已在后台启动"}


@router.post("/main_force/collect")
async def collect_main_force_series(
    background_tasks: BackgroundTasks,
    code: str = Query(..., description="股票代码"),
    source: str = Query("auto", description="auto | em | tushare"),
    days: int = Query(120, ge=5, le=250),
    sync: bool = Query(True, description="默认同步，便于分析页立即重算"),
):
    """补主力分档：auto 先 Tushare moneyflow，失败再东财。"""
    if is_hk_equity_code(code):
        return JSONResponse(
            {"success": False, "message": "主力分档仅支持 A 股"},
            status_code=400,
        )
    from backend_core.data_collectors.tushare.moneyflow import collect_main_force_for_code

    src = (source or "auto").strip().lower()

    def _run():
        return collect_main_force_for_code(code, source=src, days=days)

    if sync:
        try:
            result = _run()
            if not result.get("success"):
                return JSONResponse(
                    {
                        "success": False,
                        "message": result.get("error") or "采集失败",
                        "data": result,
                    },
                    status_code=404,
                )
            return {"success": True, "data": result}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"采集失败: {e}"}, status_code=500
            )
    background_tasks.add_task(_run)
    return {"success": True, "message": f"主力分档采集已在后台启动: {code} ({src})"}


@router.get("/em/import/template")
async def em_import_template():
    from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
        IMPORT_TEMPLATE_CSV,
    )

    body = (
        "\ufeff"
        + "# 东财分档模板（金额默认元）。也可导入 Tushare moneyflow 导出（buy_elg_amount 等，单位万元，系统自动换算）。\n"
        + IMPORT_TEMPLATE_CSV
    )
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=em_fund_flow_import_template.csv"
        },
    )


@router.post("/em/import")
async def import_em_daily(
    code: str = Form(..., description="股票代码"),
    amount_unit: str = Form("auto", description="auto | yuan | wan | yi"),
    text: Optional[str] = Form(None, description="粘贴的 CSV / JSON"),
    file: Optional[UploadFile] = File(None),
):
    """手动导入东财分档或 Tushare moneyflow 表，UPSERT 到 stock_fund_flow_em_daily。"""
    if is_hk_equity_code(code):
        return JSONResponse(
            {"success": False, "message": "主力分档仅支持 A 股"},
            status_code=400,
        )
    from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
        parse_import_bytes,
        parse_import_table,
        upsert_rows,
    )
    from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
        normalize_code as em_norm,
    )
    from backend_core.database.db import SessionLocal

    code_n = em_norm(code) or str(code).strip()
    rows = []
    try:
        if file is not None and file.filename:
            content = await file.read()
            if content:
                rows = parse_import_bytes(
                    code_n,
                    content,
                    filename=file.filename or "",
                    amount_unit=amount_unit,
                )
        if not rows and text:
            rows = parse_import_table(code_n, text, amount_unit=amount_unit)
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"解析失败: {e}"},
            status_code=400,
        )
    if not rows:
        return JSONResponse(
            {"success": False, "message": "未解析到有效行，请检查表头与日期列"},
            status_code=400,
        )
    session = SessionLocal()
    try:
        n = upsert_rows(session, rows)
        session.commit()
        return {
            "success": True,
            "data": {
                "code": code_n,
                "upserted": n,
                "first_date": rows[0]["trade_date"],
                "last_date": rows[-1]["trade_date"],
                "source": rows[0].get("source") or "manual",
            },
        }
    except Exception as e:
        session.rollback()
        return JSONResponse(
            {"success": False, "message": f"写入失败: {e}"},
            status_code=500,
        )
    finally:
        session.close()


@router.get("/today")
async def get_today(
    code: str = Query(None, description="股票代码"),
    db: Session = Depends(get_db),
):
    """获取个股东财资金流向历史（优先读库 stock_fund_flow_em_daily，缺数再打东财）。"""
    print(f"[get_stock_fund_flow_today] 输入参数: code={code}")
    if not code:
        print("[get_stock_fund_flow_today] 缺少参数code")
        return JSONResponse(
            {"success": False, "message": "缺少股票代码参数code"}, status_code=400
        )
    try:
        # 优先本地东财日表
        try:
            series = _query_em_daily_rows(db, code, days=120)
            if series:
                result = [
                    {
                        "date": r.get("trade_date"),
                        "code": r.get("code") or code,
                        "main_net_inflow": safe_float(r.get("main_net_inflow")),
                        "large_net_inflow": safe_float(r.get("large_net_inflow")),
                        "super_large_net_inflow": safe_float(
                            r.get("super_large_net_inflow")
                        ),
                        "mid_net_inflow": safe_float(r.get("mid_net_inflow")),
                        "small_net_inflow": safe_float(r.get("small_net_inflow")),
                        "source": "stock_fund_flow_em_daily",
                    }
                    for r in series
                ]
                return {"success": True, "data": result, "series_source": "db"}
        except Exception as db_ex:
            print(f"[get_stock_fund_flow_today] 读库失败，回退东财: {db_ex}")

        df = None
        for market in ("sh", "sz", "bj"):
            try:
                print(
                    f"[get_stock_fund_flow_today] 尝试方法-{market}: "
                    f"调用ak.stock_individual_fund_flow, stock={code}"
                )
                df = ak.stock_individual_fund_flow(stock=code, market=market)
                if df is not None and not df.empty:
                    break
                df = None
            except Exception as ex:
                print(f"[get_stock_fund_flow_today] 市场 {market} 异常: {ex}")
                df = None

        if df is None or df.empty:
            print(f"[get_stock_fund_flow_today] 未找到股票代码: {code} 的资金流向历史数据")
            return JSONResponse(
                {
                    "success": False,
                    "message": f"未找到股票代码: {code} 的资金流向历史数据",
                },
                status_code=404,
            )

        rows = df.to_dict(orient="records")
        result = []
        for row in rows:
            result.append(
                {
                    "date": row.get("date") or row.get("日期"),
                    "code": code,
                    "main_net_inflow": safe_float(row.get("主力净流入-净额")),
                    "large_net_inflow": safe_float(row.get("大单净流入-净额")),
                    "super_large_net_inflow": safe_float(row.get("超大单净流入-净额")),
                    "mid_net_inflow": safe_float(row.get("中单净流入-净额")),
                    "small_net_inflow": safe_float(row.get("小单净流入-净额")),
                    "source": "em_live",
                }
            )
        return {"success": True, "data": result, "series_source": "em_live"}
    except Exception as e:
        print(f"[get_stock_fund_flow_today] 查询个股资金流向历史数据异常: {e}")
        import traceback

        print(traceback.format_exc())
        return JSONResponse(
            {"success": False, "message": f"查询个股资金流向历史数据异常: {e}"},
            status_code=500,
        )


def _trade_date_key(val) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        try:
            return val.isoformat()[:10]
        except Exception:
            pass
    s = str(val).strip()
    return s[:10] if s else None


def _merge_fund_flow_series(
    primary: list,
    secondary: list,
    *,
    days: int,
    primary_label: str,
    secondary_label: str,
) -> tuple:
    """
    按交易日合并两路资金流：同日优先 primary（专用日表），缺失日用 secondary 补齐。
    返回 (升序 series, series_source 描述)。
    """
    by_date = {}
    sources_used = set()

    for r in secondary or []:
        d = _trade_date_key(r.get("trade_date"))
        if not d:
            continue
        item = dict(r)
        item["trade_date"] = d
        by_date[d] = item
        sources_used.add(secondary_label)

    for r in primary or []:
        d = _trade_date_key(r.get("trade_date"))
        if not d:
            continue
        item = dict(r)
        item["trade_date"] = d
        by_date[d] = item
        sources_used.add(primary_label)

    if not by_date:
        return [], ""

    dates_desc = sorted(by_date.keys(), reverse=True)[: max(1, int(days))]
    series_desc = [by_date[d] for d in dates_desc]
    for item in series_desc:
        if item.get("updated_at") is not None:
            item["updated_at"] = str(item["updated_at"])

    if primary_label in sources_used and secondary_label in sources_used:
        source = f"{primary_label}+{secondary_label}"
    elif primary_label in sources_used:
        source = primary_label
    else:
        source = secondary_label
    return list(reversed(series_desc)), source


def compute_daily_fund_flow(db: Session, code: str, days: int = 20) -> dict:
    """
    近 N 日流入/流出/净额 + 简单变化分析（同步，供路由与个股 bundle 复用）。
    成功返回 {"success": True, "data": {...}}；失败返回 {"success": False, "message": ...}。
    """
    code_n = normalize_equity_code(code) or normalize_ths_code(code)
    if not code_n:
        return {"success": False, "message": "无效股票代码"}
    market = "HK" if is_hk_equity_code(code_n) else "CN"
    days_n = max(1, min(120, int(days or 20)))
    fetch_n = max(days_n * 2, days_n + 5)
    if market == "HK":
        hist_rows = db.execute(
            text(
                """
                SELECT code,
                       date AS trade_date,
                       name,
                       inflow_amount,
                       outflow_amount,
                       net_amount,
                       amount AS turnover_amount,
                       change_percent,
                       turnover_rate,
                       close AS current_price
                FROM historical_quotes_hk
                WHERE code = :code
                  AND (inflow_amount IS NOT NULL OR outflow_amount IS NOT NULL OR net_amount IS NOT NULL)
                ORDER BY date DESC
                LIMIT :days
                """
            ),
            {"code": code_n, "days": fetch_n},
        ).mappings().all()
        daily_rows = db.execute(
            text(
                """
                SELECT code, trade_date, name, inflow_amount, outflow_amount,
                       net_amount, turnover_amount, change_percent, turnover_rate,
                       current_price, source, updated_at
                FROM stock_fund_flow_daily_hk
                WHERE code = :code
                ORDER BY trade_date DESC
                LIMIT :days
                """
            ),
            {"code": code_n, "days": fetch_n},
        ).mappings().all()
        series_asc, source = _merge_fund_flow_series(
            [dict(r) for r in daily_rows],
            [dict(r) for r in hist_rows],
            days=days_n,
            primary_label="stock_fund_flow_daily_hk",
            secondary_label="historical_quotes_hk",
        )
    else:
        hist_rows = db.execute(
            text(
                """
                SELECT code,
                       date AS trade_date,
                       name,
                       inflow_amount,
                       outflow_amount,
                       net_amount,
                       amount AS turnover_amount,
                       change_percent,
                       turnover_rate,
                       close AS current_price
                FROM historical_quotes
                WHERE code = :code
                  AND (inflow_amount IS NOT NULL OR outflow_amount IS NOT NULL OR net_amount IS NOT NULL)
                ORDER BY date DESC
                LIMIT :days
                """
            ),
            {"code": code_n, "days": fetch_n},
        ).mappings().all()
        daily_rows = db.execute(
            text(
                """
                SELECT code, trade_date, name, inflow_amount, outflow_amount,
                       net_amount, turnover_amount, change_percent, turnover_rate,
                       current_price, source, updated_at
                FROM stock_fund_flow_daily
                WHERE code = :code
                ORDER BY trade_date DESC
                LIMIT :days
                """
            ),
            {"code": code_n, "days": fetch_n},
        ).mappings().all()
        series_asc, source = _merge_fund_flow_series(
            [dict(r) for r in daily_rows],
            [dict(r) for r in hist_rows],
            days=days_n,
            primary_label="stock_fund_flow_daily",
            secondary_label="historical_quotes",
        )

    analysis = analyze_fund_flow_series(series_asc)
    return {
        "success": True,
        "data": {
            "code": code_n,
            "market": market,
            "days_requested": days_n,
            "series_source": source,
            "series": series_asc,
            "analysis": analysis,
        },
    }


@router.get("/daily")
async def get_daily_inflow_outflow(
    code: str = Query(..., description="股票代码（A股6位或港股5位）"),
    days: int = Query(20, ge=1, le=120, description="近N个交易日"),
    db: Session = Depends(get_db),
):
    """
    近 N 日流入/流出/净额 + 简单变化分析。
    A股：合并 stock_fund_flow_daily 与 historical_quotes（同日优先日表，避免行情表滞后丢最新日）。
    港股：合并 stock_fund_flow_daily_hk 与 historical_quotes_hk（同上）。
    """
    try:
        result = compute_daily_fund_flow(db, code, days=days)
        if not result.get("success"):
            return JSONResponse(result, status_code=400)
        return result
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询日资金流失败: {e}"}, status_code=500
        )


# 日/周/月：交易日窗口（近 N 个有资金流数据的交易日）
_STOCK_FUND_FLOW_RANK_PERIODS = {
    "day": {"days": 1, "label": "日"},
    "week": {"days": 5, "label": "周"},
    "month": {"days": 20, "label": "月"},
}


def _pick_rank_sides(rows: list, sides: int) -> list:
    """按净流入升序，取最弱 sides + 最强 sides（去重后仍升序，供横条图展示）。"""
    lim = max(1, int(sides))
    cleaned = [r for r in rows if r.get("net_amount") is not None]
    cleaned.sort(key=lambda x: float(x["net_amount"]))
    if len(cleaned) <= lim * 2:
        return cleaned
    weak = cleaned[:lim]
    strong = cleaned[-lim:]
    seen = set()
    out = []
    for r in weak + strong:
        code = r.get("code")
        if code in seen:
            continue
        seen.add(code)
        out.append(r)
    out.sort(key=lambda x: float(x["net_amount"]))
    return out


@router.get("/rank")
async def get_stock_fund_flow_rank(
    period: str = Query("day", description="day|week|month（近1/5/20 个交易日净流入合计）"),
    sides: int = Query(
        80,
        ge=5,
        le=100,
        description="净流入最强与最弱各取 N 只（合并去重后升序返回）",
    ),
    trade_date: Optional[str] = Query(
        None, description="锚定交易日 YYYY-MM-DD；默认取库内最新日"
    ),
    db: Session = Depends(get_db),
):
    """
    个股资金流向趋势跟踪：按日/周/月汇总净流入，返回两端排名（弱→强）。
    数据源：stock_fund_flow_daily（A股同花顺日采）。
    """
    key = (period or "day").strip().lower()
    meta = _STOCK_FUND_FLOW_RANK_PERIODS.get(key)
    if not meta:
        return JSONResponse(
            {"success": False, "message": "period 应为 day / week / month"},
            status_code=400,
        )
    n_days = int(meta["days"])
    anchor = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            anchor = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    try:
        if not anchor:
            latest = db.execute(
                text("SELECT MAX(trade_date) FROM stock_fund_flow_daily")
            ).scalar()
            if latest is None:
                return {
                    "success": True,
                    "data": {
                        "period": key,
                        "period_label": meta["label"],
                        "trade_days": n_days,
                        "start_date": None,
                        "end_date": None,
                        "items": [],
                        "count": 0,
                        "sides": sides,
                    },
                }
            anchor = (
                latest.isoformat()[:10]
                if hasattr(latest, "isoformat")
                else str(latest)[:10]
            )

        date_rows = db.execute(
            text(
                """
                SELECT DISTINCT trade_date
                FROM stock_fund_flow_daily
                WHERE trade_date <= :anchor
                ORDER BY trade_date DESC
                LIMIT :n_days
                """
            ),
            {"anchor": anchor, "n_days": n_days},
        ).fetchall()
        trade_dates = [
            (r[0].isoformat()[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10])
            for r in date_rows
            if r and r[0] is not None
        ]
        if not trade_dates:
            return {
                "success": True,
                "data": {
                    "period": key,
                    "period_label": meta["label"],
                    "trade_days": n_days,
                    "start_date": None,
                    "end_date": anchor,
                    "items": [],
                    "count": 0,
                    "sides": sides,
                },
            }

        start_date = min(trade_dates)
        end_date = max(trade_dates)
        rows = db.execute(
            text(
                """
                SELECT
                    code,
                    (array_agg(name ORDER BY trade_date DESC))[1] AS name,
                    SUM(net_amount) AS net_amount,
                    SUM(inflow_amount) AS inflow_amount,
                    SUM(outflow_amount) AS outflow_amount,
                    SUM(turnover_amount) AS turnover_amount,
                    COUNT(*)::int AS days_count
                FROM stock_fund_flow_daily
                WHERE trade_date >= :start_d
                  AND trade_date <= :end_d
                GROUP BY code
                HAVING SUM(net_amount) IS NOT NULL
                """
            ),
            {"start_d": start_date, "end_d": end_date},
        ).mappings().all()

        all_items = []
        for r in rows:
            all_items.append(
                {
                    "code": r["code"],
                    "name": r["name"],
                    "net_amount": safe_float(r["net_amount"]),
                    "inflow_amount": safe_float(r["inflow_amount"]),
                    "outflow_amount": safe_float(r["outflow_amount"]),
                    "turnover_amount": safe_float(r["turnover_amount"]),
                    "days_count": int(r["days_count"] or 0),
                }
            )
        items = _pick_rank_sides(all_items, sides)
        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": meta["label"],
                "trade_days": n_days,
                "start_date": start_date,
                "end_date": end_date,
                "items": items,
                "count": len(items),
                "total_universe": len(all_items),
                "sides": sides,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询个股资金流排名失败: {e}"},
            status_code=500,
        )


@router.post("/daily/sync-quotes")
async def sync_fund_flow_to_quotes(
    trade_date: Optional[str] = Query(
        None, description="交易日 YYYY-MM-DD；不传则同步 stock_fund_flow_daily 全部日期"
    ),
    db: Session = Depends(get_db),
):
    """将 stock_fund_flow_daily 回写到 historical_quotes / stock_realtime_quote。"""
    from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
        ThsFundFlowDailyCollector,
    )

    try:
        if trade_date:
            datetime.strptime(trade_date, "%Y-%m-%d")
            q = text(
                """
                SELECT code, trade_date, inflow_amount, outflow_amount, net_amount
                FROM stock_fund_flow_daily
                WHERE trade_date = :d
                """
            )
            params = {"d": trade_date}
        else:
            q = text(
                """
                SELECT code, trade_date, inflow_amount, outflow_amount, net_amount
                FROM stock_fund_flow_daily
                """
            )
            params = {}
        rows = [dict(r) for r in db.execute(q, params).mappings().all()]
        synced = ThsFundFlowDailyCollector(
            trade_date=trade_date or datetime.now().strftime("%Y-%m-%d")
        ).sync_to_quote_tables(rows)
        return {
            "success": True,
            "data": {
                "rows": len(rows),
                **synced,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"同步失败: {e}"}, status_code=500
        )


@router.post("/daily/collect")
async def trigger_daily_collect(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，默认今天"),
    sync: bool = Query(False, description="true 则同步执行（约20秒）"),
):
    """触发同花顺「即时」全市场流入/流出日采（并回写实时/历史行情表）。"""
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )

    if sync:
        try:
            result = collect_ths_fund_flow_daily(trade_date=trade_date)
            return {"success": True, "data": result}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"采集失败: {e}"}, status_code=500
            )

    background_tasks.add_task(collect_ths_fund_flow_daily, trade_date)
    return {
        "success": True,
        "message": "同花顺资金流日采已在后台启动",
        "trade_date": trade_date or datetime.now().strftime("%Y-%m-%d"),
    }
