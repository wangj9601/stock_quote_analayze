# -*- coding: utf-8 -*-
"""检查行业板指数日 K 是否够算板 RS（IBD 窗需 ≥253 根）。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import SessionLocal
from backend_core.indicators.rs_rating.config import RS_WINDOWS
from backend_core.indicators.rs_rating.calculator import compute_rs_raw

NEED = max(RS_WINDOWS) + 1  # 252 + 1


def main() -> None:
    db = SessionLocal()
    try:
        print("RS_WINDOWS", RS_WINDOWS, "need_bars", NEED)
        # 同花顺行业板目录
        boards = db.execute(
            text(
                """
                SELECT board_code, board_name
                FROM industry_board_basic_info
                WHERE COALESCE(board_code_source, 'tonghuashun') = 'tonghuashun'
                ORDER BY board_code
                """
            )
        ).fetchall()
        print("ths industry boards", len(boards))

        hist = db.execute(
            text(
                """
                SELECT board_code,
                       COUNT(*) AS n,
                       MIN(trade_date) AS d0,
                       MAX(trade_date) AS d1
                FROM industry_board_historical_quotes
                WHERE close IS NOT NULL AND close > 0
                GROUP BY board_code
                """
            )
        ).fetchall()
        by = {str(r[0]): r for r in hist}
        print("hist boards with closes", len(by))

        enough = 0
        raw_ok = 0
        samples = []
        for code, name in boards:
            row = by.get(str(code))
            n = int(row[1]) if row else 0
            if n >= NEED:
                enough += 1
            # 抽前 5 个有数板试算
            if len(samples) < 5 and n > 0:
                closes = [
                    float(c)
                    for (c,) in db.execute(
                        text(
                            """
                            SELECT close FROM industry_board_historical_quotes
                            WHERE board_code = :c AND close > 0
                            ORDER BY trade_date ASC
                            """
                        ),
                        {"c": code},
                    ).fetchall()
                ]
                detail = compute_rs_raw(closes)
                if detail:
                    raw_ok += 1
                samples.append(
                    (
                        code,
                        name,
                        n,
                        str(row[2])[:10] if row else None,
                        str(row[3])[:10] if row else None,
                        "raw_ok" if detail else "raw_fail",
                    )
                )

        # 全量试算 raw 成功率（只对有历史的板）
        ok = 0
        fail = 0
        for code, name in boards:
            row = by.get(str(code))
            if not row or int(row[1]) < NEED:
                fail += 1
                continue
            closes = [
                float(c)
                for (c,) in db.execute(
                    text(
                        """
                        SELECT close FROM industry_board_historical_quotes
                        WHERE board_code = :c AND close > 0
                        ORDER BY trade_date ASC
                        """
                    ),
                    {"c": code},
                ).fetchall()
            ]
            if compute_rs_raw(closes):
                ok += 1
            else:
                fail += 1

        latest_gate = db.execute(
            text(
                """
                SELECT trade_date,
                       COUNT(*) AS n,
                       COUNT(rs_rating) AS rated,
                       COUNT(rs_raw) AS rawed
                FROM board_rs_ratings
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT 3
                """
            )
        ).fetchall()

        print("boards with bars >=", NEED, ":", enough, "/", len(boards))
        print("rs_raw computable (among all ths industry):", ok, "fail/short:", fail)
        print("samples:", samples)
        print("board_rs_ratings latest:", latest_gate)
    finally:
        db.close()


if __name__ == "__main__":
    main()
