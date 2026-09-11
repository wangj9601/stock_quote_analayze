# -*- coding: utf-8 -*-
"""板块资金流日采：同花顺优先，东财分档/成分上卷兜底 → board_fund_flow_daily。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.data_collectors.akshare.ths_fund_flow_daily import (
    parse_ths_amount,
    parse_ths_percent,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

SOURCE_THS_FUND = "ths_fund_flow"
SOURCE_THS_SUMMARY = "ths_summary"
SOURCE_EM_RANK = "em_rank"
SOURCE_AGGREGATE = "aggregate"

UPSERT_SQL = text(
    """
    INSERT INTO board_fund_flow_daily (
        board_kind, board_code_source, board_code, trade_date, board_name,
        change_percent, inflow_amount, outflow_amount, main_net_inflow,
        main_net_inflow_pct, super_large_net_inflow, large_net_inflow,
        mid_net_inflow, small_net_inflow, source, em_board_code,
        created_at, updated_at
    ) VALUES (
        :board_kind, :board_code_source, :board_code, :trade_date, :board_name,
        :change_percent, :inflow_amount, :outflow_amount, :main_net_inflow,
        :main_net_inflow_pct, :super_large_net_inflow, :large_net_inflow,
        :mid_net_inflow, :small_net_inflow, :source, :em_board_code,
        :created_at, :updated_at
    )
    ON CONFLICT (board_kind, board_code_source, board_code, trade_date) DO UPDATE SET
        board_name = COALESCE(EXCLUDED.board_name, board_fund_flow_daily.board_name),
        change_percent = COALESCE(EXCLUDED.change_percent, board_fund_flow_daily.change_percent),
        inflow_amount = CASE
            WHEN EXCLUDED.source IN ('ths_fund_flow', 'ths_summary')
                 AND EXCLUDED.inflow_amount IS NOT NULL
            THEN EXCLUDED.inflow_amount
            WHEN board_fund_flow_daily.inflow_amount IS NULL
            THEN EXCLUDED.inflow_amount
            ELSE board_fund_flow_daily.inflow_amount
        END,
        outflow_amount = CASE
            WHEN EXCLUDED.source IN ('ths_fund_flow', 'ths_summary')
                 AND EXCLUDED.outflow_amount IS NOT NULL
            THEN EXCLUDED.outflow_amount
            WHEN board_fund_flow_daily.outflow_amount IS NULL
            THEN EXCLUDED.outflow_amount
            ELSE board_fund_flow_daily.outflow_amount
        END,
        main_net_inflow = CASE
            WHEN EXCLUDED.source IN ('ths_fund_flow', 'ths_summary')
                 AND EXCLUDED.main_net_inflow IS NOT NULL
            THEN EXCLUDED.main_net_inflow
            WHEN board_fund_flow_daily.main_net_inflow IS NULL
            THEN EXCLUDED.main_net_inflow
            ELSE board_fund_flow_daily.main_net_inflow
        END,
        main_net_inflow_pct = COALESCE(
            EXCLUDED.main_net_inflow_pct, board_fund_flow_daily.main_net_inflow_pct
        ),
        super_large_net_inflow = COALESCE(
            EXCLUDED.super_large_net_inflow, board_fund_flow_daily.super_large_net_inflow
        ),
        large_net_inflow = COALESCE(
            EXCLUDED.large_net_inflow, board_fund_flow_daily.large_net_inflow
        ),
        mid_net_inflow = COALESCE(
            EXCLUDED.mid_net_inflow, board_fund_flow_daily.mid_net_inflow
        ),
        small_net_inflow = COALESCE(
            EXCLUDED.small_net_inflow, board_fund_flow_daily.small_net_inflow
        ),
        source = CASE
            WHEN board_fund_flow_daily.source IN ('ths_fund_flow', 'ths_summary')
            THEN board_fund_flow_daily.source
            ELSE EXCLUDED.source
        END,
        em_board_code = COALESCE(
            EXCLUDED.em_board_code, board_fund_flow_daily.em_board_code
        ),
        updated_at = EXCLUDED.updated_at
    """
)


def _parse_trade_date(raw: Optional[str]) -> date:
    if raw:
        s = str(raw).strip()[:10]
        return datetime.strptime(s, "%Y-%m-%d").date()
    return datetime.now().date()


def _yi_to_yuan(val: Any) -> Optional[float]:
    """同花顺/东财「亿」口径数值 → 元；已带单位字符串走 parse_ths_amount。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, str):
        s = val.strip()
        if not s or s in ("-", "--"):
            return None
        if "亿" in s or "万" in s:
            return parse_ths_amount(s)
        try:
            return round(float(s.replace(",", "")) * 1e8, 2)
        except ValueError:
            return parse_ths_amount(s)
    try:
        return round(float(val) * 1e8, 2)
    except (TypeError, ValueError):
        return None


def _col(df: pd.DataFrame, *names: str):
    col_map = {str(c).strip(): c for c in df.columns}
    for n in names:
        if n in col_map:
            return col_map[n]
    return None


def _empty_row(
    *,
    board_kind: str,
    board_code: str,
    board_name: str,
    trade_date: date,
    source: str,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, Any]:
    now = datetime.now()
    return {
        "board_kind": board_kind,
        "board_code_source": board_code_source,
        "board_code": board_code,
        "trade_date": trade_date,
        "board_name": board_name,
        "change_percent": None,
        "inflow_amount": None,
        "outflow_amount": None,
        "main_net_inflow": None,
        "main_net_inflow_pct": None,
        "super_large_net_inflow": None,
        "large_net_inflow": None,
        "mid_net_inflow": None,
        "small_net_inflow": None,
        "source": source,
        "em_board_code": None,
        "created_at": now,
        "updated_at": now,
    }


class BoardFundFlowDailyCollector:
    """同花顺行业/概念资金流日采 + summary/东财/成分上卷兜底。"""

    def __init__(self, trade_date: Optional[str] = None) -> None:
        self.trade_date = _parse_trade_date(trade_date)
        self.logger = logger

    def _load_name_code_maps(
        self, session
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """board_name → board_code（仅 tonghuashun）。"""
        industry: Dict[str, str] = {}
        concept: Dict[str, str] = {}
        for table, bucket in (
            ("industry_board_basic_info", industry),
            ("concept_board_basic_info", concept),
        ):
            try:
                rows = session.execute(
                    text(
                        f"""
                        SELECT board_code, board_name
                        FROM {table}
                        WHERE COALESCE(NULLIF(TRIM(board_code_source), ''), '')
                              = :src
                        """
                    ),
                    {"src": DEFAULT_BOARD_CODE_SOURCE},
                ).fetchall()
            except Exception as e:
                self.logger.warning("加载 %s 名称映射失败: %s", table, e)
                try:
                    session.rollback()
                except Exception:
                    pass
                continue
            for code, name in rows:
                n = str(name or "").strip()
                c = str(code or "").strip()
                if n and c and n not in bucket:
                    bucket[n] = c
        return industry, concept

    def _resolve_code(
        self, name_map: Dict[str, str], name: str
    ) -> Optional[str]:
        key = str(name or "").strip()
        if not key:
            return None
        return name_map.get(key)

    def fetch_ths_fund_flow(self, board_kind: str) -> pd.DataFrame:
        if board_kind == "concept":
            self.logger.info("调用 ak.stock_fund_flow_concept(symbol='即时')")
            df = ak.stock_fund_flow_concept(symbol="即时")
        else:
            self.logger.info("调用 ak.stock_fund_flow_industry(symbol='即时')")
            df = ak.stock_fund_flow_industry(symbol="即时")
        if df is None or df.empty:
            raise RuntimeError(f"同花顺{board_kind}资金流「即时」返回空")
        return df

    def ths_fund_flow_to_rows(
        self,
        df: pd.DataFrame,
        *,
        board_kind: str,
        name_map: Dict[str, str],
    ) -> Tuple[List[Dict[str, Any]], int]:
        c_name = _col(df, "行业", "板块", "名称", "概念")
        c_chg = _col(df, "行业-涨跌幅", "涨跌幅", "阶段涨跌幅")
        c_in = _col(df, "流入资金")
        c_out = _col(df, "流出资金")
        c_net = _col(df, "净额")
        if c_name is None or c_net is None:
            raise RuntimeError(f"同花顺资金流缺列: {list(df.columns)}")

        rows: List[Dict[str, Any]] = []
        unmatched = 0
        seen: set = set()
        for _, r in df.iterrows():
            name = str(r.get(c_name) or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            code = self._resolve_code(name_map, name)
            if not code:
                unmatched += 1
                continue
            row = _empty_row(
                board_kind=board_kind,
                board_code=code,
                board_name=name,
                trade_date=self.trade_date,
                source=SOURCE_THS_FUND,
            )
            # 即时接口金额单位为「亿」
            row["inflow_amount"] = _yi_to_yuan(r.get(c_in)) if c_in else None
            row["outflow_amount"] = _yi_to_yuan(r.get(c_out)) if c_out else None
            row["main_net_inflow"] = _yi_to_yuan(r.get(c_net))
            row["change_percent"] = (
                parse_ths_percent(r.get(c_chg)) if c_chg else None
            )
            rows.append(row)
        return rows, unmatched

    def fetch_ths_summary_fill(
        self, name_map: Dict[str, str], existing_codes: set
    ) -> List[Dict[str, Any]]:
        """行业 summary 净流入：仅补缺尚未有 main_net_inflow 的板。"""
        try:
            from backend_core.data_collectors.akshare.industry_board_normalize import (
                normalize_ths_industry_df,
            )

            self.logger.info("调用 ak.stock_board_industry_summary_ths() 补缺净流入")
            df = ak.stock_board_industry_summary_ths()
            df = normalize_ths_industry_df(df)
        except Exception as e:
            self.logger.warning("summary_ths 补缺失败: %s", e)
            return []

        c_name = _col(df, "板块名称", "板块")
        c_net = _col(df, "净流入")
        c_chg = _col(df, "涨跌幅")
        if c_name is None or c_net is None:
            return []

        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            name = str(r.get(c_name) or "").strip()
            code = self._resolve_code(name_map, name)
            if not code or code in existing_codes:
                continue
            net = _yi_to_yuan(r.get(c_net))
            if net is None:
                continue
            row = _empty_row(
                board_kind="industry",
                board_code=code,
                board_name=name,
                trade_date=self.trade_date,
                source=SOURCE_THS_SUMMARY,
            )
            row["main_net_inflow"] = net
            row["change_percent"] = (
                parse_ths_percent(r.get(c_chg)) if c_chg else None
            )
            rows.append(row)
            existing_codes.add(code)
        return rows

    def fetch_em_rank_rows(
        self,
        *,
        board_kind: str,
        name_map: Dict[str, str],
        ths_to_em: Dict[str, str],
        em_to_ths: Dict[str, str],
        existing_with_net: set,
    ) -> List[Dict[str, Any]]:
        sector_type = "概念资金流" if board_kind == "concept" else "行业资金流"
        try:
            self.logger.info(
                "调用 ak.stock_sector_fund_flow_rank(indicator='今日', sector_type=%s)",
                sector_type,
            )
            df = ak.stock_sector_fund_flow_rank(
                indicator="今日", sector_type=sector_type
            )
        except Exception as e:
            self.logger.warning("东财板块资金流排名失败 kind=%s: %s", board_kind, e)
            return []
        if df is None or df.empty:
            return []

        c_name = _col(df, "名称", "板块名称", "行业")
        c_code = _col(df, "板块代码", "代码")
        c_chg = _col(df, "今日涨跌幅", "涨跌幅")
        c_main = _col(df, "今日主力净流入-净额", "主力净流入-净额")
        c_main_pct = _col(df, "今日主力净流入-净占比", "主力净流入-净占比")
        c_super = _col(df, "今日超大单净流入-净额", "超大单净流入-净额")
        c_large = _col(df, "今日大单净流入-净额", "大单净流入-净额")
        c_mid = _col(df, "今日中单净流入-净额", "中单净流入-净额")
        c_small = _col(df, "今日小单净流入-净额", "小单净流入-净额")
        if c_name is None:
            return []

        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            name = str(r.get(c_name) or "").strip()
            em_code = str(r.get(c_code) or "").strip() if c_code else ""
            ths_code = None
            if em_code and em_code in em_to_ths:
                ths_code = em_to_ths[em_code]
            if not ths_code:
                ths_code = self._resolve_code(name_map, name)
            if not ths_code:
                continue

            # 已有 THS 净额：只补分档
            only_tiers = ths_code in existing_with_net
            main_net = None
            if c_main is not None:
                # 东财净额通常已是元（偶带「亿」）
                raw = r.get(c_main)
                if isinstance(raw, str) and ("亿" in raw or "万" in raw):
                    main_net = parse_ths_amount(raw)
                else:
                    try:
                        main_net = float(raw) if raw is not None and not pd.isna(raw) else None
                    except (TypeError, ValueError):
                        main_net = parse_ths_amount(raw)

            def _tier(col):
                if col is None:
                    return None
                raw = r.get(col)
                if isinstance(raw, str) and ("亿" in raw or "万" in raw):
                    return parse_ths_amount(raw)
                try:
                    return float(raw) if raw is not None and not pd.isna(raw) else None
                except (TypeError, ValueError):
                    return parse_ths_amount(raw)

            row = _empty_row(
                board_kind=board_kind,
                board_code=ths_code,
                board_name=name,
                trade_date=self.trade_date,
                source=SOURCE_EM_RANK,
            )
            row["em_board_code"] = em_code or ths_to_em.get(ths_code)
            row["change_percent"] = (
                parse_ths_percent(r.get(c_chg)) if c_chg else None
            )
            row["super_large_net_inflow"] = _tier(c_super)
            row["large_net_inflow"] = _tier(c_large)
            row["mid_net_inflow"] = _tier(c_mid)
            row["small_net_inflow"] = _tier(c_small)
            row["main_net_inflow_pct"] = (
                parse_ths_percent(r.get(c_main_pct)) if c_main_pct else None
            )
            if not only_tiers:
                row["main_net_inflow"] = main_net
                existing_with_net.add(ths_code)
            rows.append(row)
        return rows

    def aggregate_from_constituents(
        self,
        session,
        *,
        board_kind: str,
        existing_codes: set,
    ) -> List[Dict[str, Any]]:
        cons_table = (
            "concept_board_constituents"
            if board_kind == "concept"
            else "industry_board_constituents"
        )
        basic_table = (
            "concept_board_basic_info"
            if board_kind == "concept"
            else "industry_board_basic_info"
        )
        td = self.trade_date.isoformat()
        sql = text(
            f"""
            SELECT b.board_code, b.board_name, SUM(f.net_amount) AS net_sum
            FROM {basic_table} b
            JOIN {cons_table} c ON c.board_code = b.board_code
            JOIN stock_fund_flow_daily f
              ON f.code = c.stock_code AND f.trade_date = :td
            WHERE COALESCE(NULLIF(TRIM(b.board_code_source), ''), '') = :src
              AND NOT EXISTS (
                SELECT 1 FROM board_fund_flow_daily d
                WHERE d.board_kind = :kind
                  AND d.board_code_source = :src
                  AND d.board_code = b.board_code
                  AND d.trade_date = CAST(:td AS date)
                  AND d.main_net_inflow IS NOT NULL
              )
            GROUP BY b.board_code, b.board_name
            """
        )
        try:
            rows_db = session.execute(
                sql,
                {
                    "td": td,
                    "src": DEFAULT_BOARD_CODE_SOURCE,
                    "kind": board_kind,
                },
            ).fetchall()
        except Exception as e:
            self.logger.warning("成分上卷失败 kind=%s: %s", board_kind, e)
            try:
                session.rollback()
            except Exception:
                pass
            return []

        out: List[Dict[str, Any]] = []
        for code, name, net_sum in rows_db:
            c = str(code or "").strip()
            if not c or c in existing_codes:
                continue
            if net_sum is None:
                continue
            row = _empty_row(
                board_kind=board_kind,
                board_code=c,
                board_name=str(name or "").strip() or c,
                trade_date=self.trade_date,
                source=SOURCE_AGGREGATE,
            )
            row["main_net_inflow"] = float(net_sum)
            out.append(row)
            existing_codes.add(c)
        return out

    def upsert_rows(self, rows: List[Dict[str, Any]], batch_size: int = 200) -> int:
        if not rows:
            return 0
        session = SessionLocal()
        written = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                session.execute(UPSERT_SQL, chunk)
                session.commit()
                written += len(chunk)
            return written
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _codes_with_net(self, session, board_kind: str) -> set:
        td = self.trade_date
        try:
            rows = session.execute(
                text(
                    """
                    SELECT board_code FROM board_fund_flow_daily
                    WHERE board_kind = :kind
                      AND board_code_source = :src
                      AND trade_date = :td
                      AND main_net_inflow IS NOT NULL
                    """
                ),
                {
                    "kind": board_kind,
                    "src": DEFAULT_BOARD_CODE_SOURCE,
                    "td": td,
                },
            ).fetchall()
            return {str(r[0]).strip() for r in rows if r[0]}
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
            return set()

    def collect(self) -> Dict[str, Any]:
        session = SessionLocal()
        stats: Dict[str, Any] = {
            "success": True,
            "trade_date": self.trade_date.isoformat(),
            "industry": {},
            "concept": {},
        }
        try:
            ind_map, con_map = self._load_name_code_maps(session)

            for kind, name_map in (("industry", ind_map), ("concept", con_map)):
                kind_stats: Dict[str, Any] = {
                    "ths_written": 0,
                    "ths_unmatched": 0,
                    "summary_written": 0,
                    "em_written": 0,
                    "agg_written": 0,
                }
                all_rows: List[Dict[str, Any]] = []
                existing: set = set()
                ths_to_em: Dict[str, str] = {}
                em_to_ths: Dict[str, str] = {}
                try:
                    from backend_api.utils.industry_board_code_map import (
                        load_active_code_maps,
                    )

                    ths_to_em, em_to_ths = load_active_code_maps(
                        session, board_kind=kind
                    )
                except Exception as e:
                    self.logger.warning("加载 THS↔EM 码表失败 kind=%s: %s", kind, e)
                    try:
                        session.rollback()
                    except Exception:
                        pass

                # 1) THS 主路径
                try:
                    df = self.fetch_ths_fund_flow(kind)
                    rows, unmatched = self.ths_fund_flow_to_rows(
                        df, board_kind=kind, name_map=name_map
                    )
                    kind_stats["ths_unmatched"] = unmatched
                    all_rows.extend(rows)
                    existing |= {r["board_code"] for r in rows}
                except Exception as e:
                    self.logger.warning("同花顺资金流失败 kind=%s: %s", kind, e)

                # 2) summary 补缺（仅行业）
                if kind == "industry":
                    fill = self.fetch_ths_summary_fill(name_map, existing)
                    kind_stats["summary_written"] = len(fill)
                    all_rows.extend(fill)

                # 先落 THS，便于后续查已有净额
                if all_rows:
                    n = self.upsert_rows(all_rows)
                    kind_stats["ths_written"] = n
                    all_rows = []

                existing_net = self._codes_with_net(session, kind) | existing

                # 3) 东财分档 / 兜底
                em_rows = self.fetch_em_rank_rows(
                    board_kind=kind,
                    name_map=name_map,
                    ths_to_em=ths_to_em,
                    em_to_ths=em_to_ths,
                    existing_with_net=existing_net,
                )
                if em_rows:
                    kind_stats["em_written"] = self.upsert_rows(em_rows)
                    existing_net |= {
                        r["board_code"]
                        for r in em_rows
                        if r.get("main_net_inflow") is not None
                    }

                # 4) 成分上卷
                agg_rows = self.aggregate_from_constituents(
                    session, board_kind=kind, existing_codes=existing_net
                )
                if agg_rows:
                    kind_stats["agg_written"] = self.upsert_rows(agg_rows)

                stats[kind] = kind_stats
                self.logger.info(
                    "板块资金流日采完成 kind=%s %s", kind, kind_stats
                )
        finally:
            session.close()
        return stats


def collect_board_fund_flow_daily(
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    return BoardFundFlowDailyCollector(trade_date=trade_date).collect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(collect_board_fund_flow_daily())
