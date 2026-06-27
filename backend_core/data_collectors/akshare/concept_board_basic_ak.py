"""
东财概念板块列表同步：stock_board_concept_name_em -> concept_board_basic_info
"""
from __future__ import annotations

import traceback
from datetime import datetime
from typing import Optional

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_core.data_collectors.akshare.industry_board_normalize import industry_board_to_english_df
from backend_core.database.db import SessionLocal


class ConceptBoardBasicCollector:
    log_table = "realtime_collect_operation_logs"

    def fetch_data(self) -> pd.DataFrame:
        df = ak.stock_board_concept_name_em()
        return industry_board_to_english_df(df)

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

    def run(self) -> int:
        session = SessionLocal()
        now = datetime.now().replace(microsecond=0)
        count = 0
        try:
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
            session.commit()
            df = self.fetch_data()
            if df.empty:
                self.write_log("概念板块列表同步", 0, "fail", "接口返回为空")
                return 0
            for _, row in df.iterrows():
                bcode = row.get("board_code")
                if bcode is None or pd.isna(bcode) or not str(bcode).strip():
                    continue
                session.execute(
                    text(
                        """
                        INSERT INTO concept_board_basic_info (board_code, board_name, create_date)
                        VALUES (:board_code, :board_name, :create_date)
                        ON CONFLICT (board_code) DO UPDATE SET
                            board_name = EXCLUDED.board_name,
                            create_date = EXCLUDED.create_date
                        """
                    ),
                    {
                        "board_code": str(bcode).strip(),
                        "board_name": None if pd.isna(row.get("board_name")) else str(row.get("board_name")).strip(),
                        "create_date": now,
                    },
                )
                count += 1
            session.commit()
            msg = f"概念板块列表同步 {count} 条"
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
