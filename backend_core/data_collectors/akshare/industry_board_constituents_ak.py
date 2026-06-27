"""
东财行业板块成分股采集：industry_board_basic_info -> stock_board_industry_cons_em -> industry_board_constituents
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from typing import Any, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

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


class IndustryBoardConstituentsCollector:
    log_table = "realtime_collect_operation_logs"

    def __init__(self) -> None:
        self.interval_sec = _env_float("INDUSTRY_CONS_API_INTERVAL_SEC", 0.3)
        self.max_retries = int(os.getenv("INDUSTRY_CONS_MAX_RETRIES", "2"))

    def _load_board_codes(self, session) -> List[Tuple[str, Optional[str]]]:
        rows = session.execute(
            text("SELECT board_code, board_name FROM industry_board_basic_info ORDER BY board_code")
        ).fetchall()
        return [(str(r[0]).strip(), r[1]) for r in rows if r[0]]

    def fetch_board_constituents(
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

    def save_board_constituents(
        self, session, board_code: str, constituents: List[Tuple[str, str]], now: datetime
    ) -> int:
        session.execute(
            text("DELETE FROM industry_board_constituents WHERE board_code = :board_code"),
            {"board_code": board_code},
        )
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

    def run(self, board_codes: Optional[List[str]] = None) -> None:
        session = SessionLocal()
        now = datetime.now().replace(microsecond=0)
        total_rows = 0
        ok_boards = 0
        fail_boards: List[str] = []
        try:
            if board_codes:
                boards = []
                for c in board_codes:
                    name_row = session.execute(
                        text(
                            "SELECT board_name FROM industry_board_basic_info WHERE board_code = :code LIMIT 1"
                        ),
                        {"code": c},
                    ).fetchone()
                    boards.append((c, name_row[0] if name_row else None))
            else:
                boards = self._load_board_codes(session)
            if not boards:
                print("[成分股] industry_board_basic_info 为空，请先运行行业板块实时采集")
                self.write_log("成分股同步", 0, "fail", "无板块列表")
                return

            print(f"[成分股] 开始同步 {len(boards)} 个板块，间隔 {self.interval_sec}s")
            for i, (board_code, board_name) in enumerate(boards, 1):
                label = board_name or board_code
                try:
                    cons = self.fetch_board_constituents(board_code, board_name)
                    n = self.save_board_constituents(session, board_code, cons, now)
                    session.commit()
                    total_rows += n
                    ok_boards += 1
                    if i % 20 == 0 or i == len(boards):
                        print(f"[成分股] {i}/{len(boards)} {label} -> {n} 只")
                except Exception as e:
                    session.rollback()
                    fail_boards.append(board_code)
                    print(f"[成分股] 失败 {label} ({board_code}): {e}")
                time.sleep(self.interval_sec)

            msg = f"成功 {ok_boards}/{len(boards)} 板块，共 {total_rows} 条成分"
            if fail_boards:
                msg += f"；失败 {len(fail_boards)} 个: {','.join(fail_boards[:10])}"
            print(f"[成分股] {msg}")
            self.write_log(msg, total_rows, "success" if not fail_boards else "partial", msg if fail_boards else None)
        except Exception as e:
            session.rollback()
            tb = traceback.format_exc()
            print(f"[成分股] 异常: {e}\n{tb}")
            self.write_log("成分股同步异常", 0, "fail", str(e) + "\n" + tb)
        finally:
            session.close()


if __name__ == "__main__":
    IndustryBoardConstituentsCollector().run()
