"""
行业板块成分股采集：按 board_code_source 路由东财 / 同花顺接口。

- eastmoney（及空值按 LEGACY）：stock_board_industry_cons_em
- tonghuashun：同花顺 HTML 成分页
- manual / huatai / other：明确跳过并统计原因（无自动采集器）
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_api.utils.board_code_source import (
    LEGACY_DEFAULT_BOARD_CODE_SOURCE,
    resolve_board_code_source,
)
from backend_core.database.db import SessionLocal


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def normalize_stock_code(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    if s.isdigit():
        return s.zfill(6)
    return s


def parse_cons_dataframe(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """解析成分股 DataFrame，返回 [(stock_code, stock_name), ...]。"""
    if df is None or df.empty:
        return []
    code_col = "代码" if "代码" in df.columns else None
    name_col = "名称" if "名称" in df.columns else None
    if not code_col:
        return []
    rows: List[Tuple[str, str]] = []
    for _, row in df.iterrows():
        code = normalize_stock_code(row.get(code_col))
        if not code:
            continue
        name = ""
        if name_col and name_col in row.index:
            nv = row.get(name_col)
            if nv is not None and not pd.isna(nv):
                name = str(nv).strip()
        rows.append((code, name))
    return rows


# 无自动成分接口的来源：同步时显式跳过并计入 skip，禁止假装成功
UNSUPPORTED_CONS_SOURCES = frozenset({"manual", "huatai", "other"})


def resolve_industry_cons_fetcher(source: Optional[str]) -> str:
    """返回 eastmoney / tonghuashun / unsupported。"""
    src = resolve_board_code_source(source, fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE)
    if src == "tonghuashun":
        return "tonghuashun"
    if src in UNSUPPORTED_CONS_SOURCES:
        return "unsupported"
    return "eastmoney"


class IndustryBoardConstituentsCollector:
    log_table = "realtime_collect_operation_logs"

    def __init__(self) -> None:
        self.interval_sec = _env_float("INDUSTRY_CONS_API_INTERVAL_SEC", 0.3)
        self.max_retries = int(os.getenv("INDUSTRY_CONS_MAX_RETRIES", "2"))

    def _load_boards(self, session) -> List[Tuple[str, Optional[str], str]]:
        rows = session.execute(
            text(
                """
                SELECT board_code, board_name, board_code_source
                FROM industry_board_basic_info
                ORDER BY board_code
                """
            )
        ).fetchall()
        out: List[Tuple[str, Optional[str], str]] = []
        for r in rows:
            if not r[0]:
                continue
            src = resolve_board_code_source(r[2], fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE)
            out.append((str(r[0]).strip(), r[1], src))
        return out

    def _load_boards_by_codes(
        self, session, board_codes: List[str]
    ) -> List[Tuple[str, Optional[str], str]]:
        boards: List[Tuple[str, Optional[str], str]] = []
        for c in board_codes:
            name_row = session.execute(
                text(
                    """
                    SELECT board_name, board_code_source
                    FROM industry_board_basic_info
                    WHERE board_code = :code
                    LIMIT 1
                    """
                ),
                {"code": c},
            ).fetchone()
            if name_row:
                src = resolve_board_code_source(
                    name_row[1], fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
                )
                boards.append((c, name_row[0], src))
            else:
                # 库中无 basic 行时仍尝试东财链路，避免误丢请求
                boards.append((c, None, LEGACY_DEFAULT_BOARD_CODE_SOURCE))
        return boards

    def fetch_board_constituents_eastmoney(
        self, board_code: str, board_name: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        symbol = (board_name or board_code or "").strip()
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                df = ak.stock_board_industry_cons_em(symbol=symbol)
                return parse_cons_dataframe(df)
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.interval_sec * 2)
        raise last_err  # type: ignore[misc]

    def fetch_board_constituents_tonghuashun(
        self, board_code: str, board_name: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        from backend_core.data_collectors.akshare.ths_board_constituents import (
            fetch_ths_board_constituents,
        )

        return fetch_ths_board_constituents(
            board_code,
            board_name,
            kind="industry",
            interval_sec=self.interval_sec,
            max_retries=self.max_retries,
        )

    def fetch_board_constituents(
        self,
        board_code: str,
        board_name: Optional[str] = None,
        board_code_source: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """按来源拉取成分；unsupported 抛 ValueError。"""
        route = resolve_industry_cons_fetcher(board_code_source)
        if route == "tonghuashun":
            return self.fetch_board_constituents_tonghuashun(board_code, board_name)
        if route == "unsupported":
            src = resolve_board_code_source(
                board_code_source, fallback=LEGACY_DEFAULT_BOARD_CODE_SOURCE
            )
            raise ValueError(f"来源 {src} 暂无自动成分采集器，请手工维护或导入")
        return self.fetch_board_constituents_eastmoney(board_code, board_name)

    def save_board_constituents(
        self, session, board_code: str, constituents: List[Tuple[str, str]], now: datetime
    ) -> int:
        # 仅 UPSERT：不删除库中已有成分股，避免同步失败或接口缺漏时误删存量数据
        inserted = 0
        for stock_code, stock_name in constituents:
            session.execute(
                text(
                    """
                    INSERT INTO industry_board_constituents
                        (board_code, stock_code, stock_name, updated_at)
                    VALUES (:board_code, :stock_code, :stock_name, :updated_at)
                    ON CONFLICT (board_code, stock_code) DO UPDATE SET
                        stock_name = EXCLUDED.stock_name,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "board_code": board_code,
                    "stock_code": stock_code,
                    "stock_name": stock_name or None,
                    "updated_at": now,
                },
            )
            inserted += 1
        return inserted

    def write_log(
        self,
        operation_desc: str,
        affected_rows: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        session = SessionLocal()
        try:
            now = datetime.now().replace(microsecond=0)
            session.execute(
                text(
                    f"""
                    INSERT INTO {self.log_table}
                    (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
                    """
                ),
                {
                    "operation_type": "industry_board_constituents",
                    "operation_desc": operation_desc,
                    "affected_rows": affected_rows,
                    "status": status,
                    "error_message": error_message or "",
                    "created_at": now,
                },
            )
            session.commit()
        except Exception as e:
            print(f"[LOG ERROR] {e}")
        finally:
            session.close()

    def run(self, board_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        session = SessionLocal()
        now = datetime.now().replace(microsecond=0)
        total_rows = 0
        ok_boards = 0
        fail_boards: List[Dict[str, str]] = []
        skip_boards: List[Dict[str, str]] = []
        by_source: Dict[str, Dict[str, int]] = {}
        try:
            if board_codes:
                boards = self._load_boards_by_codes(session, board_codes)
            else:
                boards = self._load_boards(session)
            if not boards:
                print("[成分股] industry_board_basic_info 为空，请先运行行业板块实时采集")
                self.write_log("成分股同步", 0, "fail", "无板块列表")
                return {
                    "ok_boards": 0,
                    "fail_boards": [],
                    "skip_boards": [],
                    "total_rows": 0,
                    "total_boards": 0,
                    "by_source": {},
                    "status": "fail",
                    "message": "无板块列表",
                }

            print(f"[成分股] 开始同步 {len(boards)} 个板块（含全部代码来源），间隔 {self.interval_sec}s")
            for i, (board_code, board_name, source) in enumerate(boards, 1):
                label = board_name or board_code
                route = resolve_industry_cons_fetcher(source)
                by_source.setdefault(source, {"ok": 0, "fail": 0, "skip": 0})
                if route == "unsupported":
                    reason = f"来源 {source} 暂无自动成分采集器"
                    skip_boards.append({"board_code": board_code, "source": source, "reason": reason})
                    by_source[source]["skip"] += 1
                    print(f"[成分股] 跳过 {label} ({board_code}/{source}): {reason}")
                    continue
                try:
                    cons = self.fetch_board_constituents(board_code, board_name, source)
                    n = self.save_board_constituents(session, board_code, cons, now)
                    session.commit()
                    total_rows += n
                    ok_boards += 1
                    by_source[source]["ok"] += 1
                    if i % 20 == 0 or i == len(boards):
                        print(f"[成分股] {i}/{len(boards)} {label}[{source}] -> {n} 只")
                except Exception as e:
                    session.rollback()
                    fail_boards.append(
                        {"board_code": board_code, "source": source, "reason": str(e)}
                    )
                    by_source[source]["fail"] += 1
                    print(f"[成分股] 失败 {label} ({board_code}/{source}): {e}")
                time.sleep(self.interval_sec)

            status = "success"
            if fail_boards or skip_boards:
                status = "partial" if ok_boards else ("fail" if fail_boards else "partial")
            msg = (
                f"成功 {ok_boards}/{len(boards)} 板块，共 {total_rows} 条成分"
                f"；失败 {len(fail_boards)}，跳过 {len(skip_boards)}"
            )
            if fail_boards:
                sample = ",".join(f"{x['board_code']}({x['source']})" for x in fail_boards[:8])
                msg += f"；失败样例: {sample}"
            if skip_boards:
                sample = ",".join(f"{x['board_code']}({x['source']})" for x in skip_boards[:8])
                msg += f"；跳过样例: {sample}"
            print(f"[成分股] {msg}")
            self.write_log(
                msg,
                total_rows,
                status,
                msg if (fail_boards or skip_boards) else None,
            )
            return {
                "ok_boards": ok_boards,
                "fail_boards": fail_boards,
                "skip_boards": skip_boards,
                "total_rows": total_rows,
                "total_boards": len(boards),
                "by_source": by_source,
                "status": status,
                "message": msg,
            }
        except Exception as e:
            session.rollback()
            tb = traceback.format_exc()
            print(f"[成分股] 异常: {e}\n{tb}")
            self.write_log("成分股同步异常", 0, "fail", str(e) + "\n" + tb)
            return {
                "ok_boards": ok_boards,
                "fail_boards": fail_boards,
                "skip_boards": skip_boards,
                "total_rows": total_rows,
                "total_boards": 0,
                "by_source": by_source,
                "status": "fail",
                "message": str(e),
            }
        finally:
            session.close()


if __name__ == "__main__":
    IndustryBoardConstituentsCollector().run()
