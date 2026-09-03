"""
概念板块列表同步：
- 东财：stock_board_concept_name_em -> concept_board_basic_info（新建标 eastmoney）
- 同花顺：stock_board_concept_name_ths（新建标 tonghuashun）
已有板保留原 board_code_source，禁止静默覆盖。
"""
from __future__ import annotations

import traceback
from datetime import datetime
from typing import Optional

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_api.utils.board_code_source import (
    DEFAULT_BOARD_CODE_SOURCE,
    SYNC_BOARD_CODE_SOURCE,
    sql_board_code_source_preserve_on_conflict,
)
from backend_core.data_collectors.akshare.industry_board_normalize import industry_board_to_english_df
from backend_core.database.db import SessionLocal


class ConceptBoardBasicCollector:
    log_table = "realtime_collect_operation_logs"

    def fetch_data(self) -> pd.DataFrame:
        df = ak.stock_board_concept_name_em()
        return industry_board_to_english_df(df)

    def fetch_ths_data(self) -> pd.DataFrame:
        df = ak.stock_board_concept_name_ths()
        if df is None or df.empty:
            return pd.DataFrame(columns=["board_code", "board_name"])
        out = pd.DataFrame(
            {
                "board_code": df["code"].astype(str).str.strip(),
                "board_name": df["name"].astype(str).str.strip(),
            }
        )
        return out[(out["board_code"] != "") & (out["board_name"] != "")]

    def write_log(self, operation_desc: str, affected_rows: int, status: str, error_message: Optional[str] = None) -> None:
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
                    "operation_type": "concept_board_basic",
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

    def _ensure_table(self, session) -> None:
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS concept_board_basic_info (
                    board_code VARCHAR(20) PRIMARY KEY,
                    board_name VARCHAR(100),
                    create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
        )
        session.execute(
            text(
                "ALTER TABLE concept_board_basic_info ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        session.execute(
            text(
                "ALTER TABLE concept_board_basic_info "
                "ADD COLUMN IF NOT EXISTS board_code_source VARCHAR(32)"
            )
        )
        session.commit()

    def _upsert_rows(
        self,
        session,
        df: pd.DataFrame,
        *,
        now: datetime,
        incoming_source: str,
    ) -> int:
        _src_preserve = sql_board_code_source_preserve_on_conflict("concept_board_basic_info")
        count = 0
        for _, row in df.iterrows():
            bcode = row.get("board_code")
            if bcode is None or pd.isna(bcode) or not str(bcode).strip():
                continue
            session.execute(
                text(
                    f"""
                    INSERT INTO concept_board_basic_info (board_code, board_name, create_date, board_code_source)
                    VALUES (:board_code, :board_name, :create_date, :board_code_source)
                    ON CONFLICT (board_code) DO UPDATE SET
                        board_name = EXCLUDED.board_name,
                        {_src_preserve}
                    """
                ),
                {
                    "board_code": str(bcode).strip(),
                    "board_name": None
                    if pd.isna(row.get("board_name"))
                    else str(row.get("board_name")).strip(),
                    "create_date": now,
                    "board_code_source": incoming_source,
                },
            )
            count += 1
        return count

    def run(self, *, include_ths: bool = True) -> int:
        """同步概念列表。默认东财 + 同花顺；include_ths=False 时仅东财。"""
        session = SessionLocal()
        now = datetime.now().replace(microsecond=0)
        count = 0
        try:
            self._ensure_table(session)
            df = self.fetch_data()
            if df.empty:
                self.write_log("概念板块列表同步", 0, "fail", "东财接口返回为空")
                return 0
            # 新建板标东财；已有板（含同花顺）保留原 board_code_source，禁止静默覆盖
            count += self._upsert_rows(session, df, now=now, incoming_source=SYNC_BOARD_CODE_SOURCE)
            ths_count = 0
            if include_ths:
                try:
                    ths_df = self.fetch_ths_data()
                    if not ths_df.empty:
                        ths_count = self._upsert_rows(
                            session,
                            ths_df,
                            now=now,
                            incoming_source=DEFAULT_BOARD_CODE_SOURCE,
                        )
                        count += ths_count
                except Exception as ths_err:
                    # 东财已成功时同花顺列表失败不整体失败，记日志便于排查
                    print(f"[概念板块] 同花顺列表同步失败（东财已写入）: {ths_err}")
                    self.write_log(
                        "概念板块同花顺列表同步失败",
                        count,
                        "partial",
                        str(ths_err),
                    )
            # 同步后按同名补全同花顺↔东财映射（不覆盖手工）
            try:
                from backend_api.utils.industry_board_code_map import rebuild_name_exact_maps

                map_stats = rebuild_name_exact_maps(
                    session, board_kind="concept", replace_auto=False
                )
                print(f"[概念板块] 代码映射补全: {map_stats}")
            except Exception as map_err:
                print(f"[概念板块] 代码映射补全跳过: {map_err}")
            session.commit()
            msg = f"概念板块列表同步 {count} 条（东财+同花顺={ths_count}）"
            print(f"[概念板块] {msg}")
            self.write_log(msg, count, "success")
            return count
        except Exception as e:
            session.rollback()
            tb = traceback.format_exc()
            print(f"[概念板块] 列表同步异常: {e}\n{tb}")
            self.write_log("概念板块列表同步异常", 0, "fail", str(e))
            raise
        finally:
            session.close()


if __name__ == "__main__":
    ConceptBoardBasicCollector().run()
