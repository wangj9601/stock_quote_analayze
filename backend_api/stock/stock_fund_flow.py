from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Depends
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


@router.get("/today")
async def get_today(code: str = Query(None, description="股票代码")):
    """获取个股东财资金流向历史数据（净流入口径）。"""
    print(f"[get_stock_fund_flow_today] 输入参数: code={code}")
    if not code:
        print("[get_stock_fund_flow_today] 缺少参数code")
        return JSONResponse(
            {"success": False, "message": "缺少股票代码参数code"}, status_code=400
        )
    try:
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
                }
            )
        return {"success": True, "data": result}
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
    code_n = normalize_equity_code(code) or normalize_ths_code(code)
    if not code_n:
        return JSONResponse(
            {"success": False, "message": "无效股票代码"}, status_code=400
        )
    market = "HK" if is_hk_equity_code(code_n) else "CN"
    # 多取一些再截断，合并后仍保证近 N 日
    fetch_n = max(int(days) * 2, int(days) + 5)
    try:
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
                days=days,
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
                days=days,
                primary_label="stock_fund_flow_daily",
                secondary_label="historical_quotes",
            )

        analysis = analyze_fund_flow_series(series_asc)
        return {
            "success": True,
            "data": {
                "code": code_n,
                "market": market,
                "days_requested": days,
                "series_source": source,
                "series": series_asc,
                "analysis": analysis,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询日资金流失败: {e}"}, status_code=500
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
