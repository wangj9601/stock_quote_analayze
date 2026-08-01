"""
迁移：将存量新浪复权因子（akshare_sina_qfq）从旧形态幂等归一化为内部约定。

背景：
  新浪原始 qfq-factor 为「历史>1、最新≈1」；内部约定与 BaoStock 一致为
  「历史通常≤1、最新≈1」。新代码入库前已取倒数；本脚本处理旧数据。

策略（按 code 分组，幂等）：
  - 若 MAX(adj_factor) > 1.05：仍为旧新浪形态 → 全部行 adj_factor = 1.0/adj_factor
    （仅 adj_factor > 0），并更新 updated_at。
  - 若 MAX(adj_factor) ≤ 1.05：已归一化 → 跳过，避免二次倒数。

用法:
    python migrations/normalize_sina_adj_factor_reciprocal.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_api.database import SessionLocal

logger = logging.getLogger(__name__)

SOURCE = "akshare_sina_qfq"
# 略大于 1，容忍浮点/最新日≈1；历史旧新浪因子通常明显 >1
MAX_FACTOR_THRESHOLD = 1.05


def run() -> None:
    db = SessionLocal()
    try:
        codes = db.execute(
            text(
                """
                SELECT code, MAX(adj_factor) AS max_f, COUNT(*) AS cnt
                FROM stock_adj_factor
                WHERE source = :source
                GROUP BY code
                ORDER BY code
                """
            ),
            {"source": SOURCE},
        ).fetchall()

        if not codes:
            logger.info("无 source=%s 的复权因子，跳过", SOURCE)
            return

        need_fix: list = []
        skipped = 0
        for row in codes:
            code = str(row[0])
            max_f = float(row[1]) if row[1] is not None else 0.0
            cnt = int(row[2] or 0)
            if max_f > MAX_FACTOR_THRESHOLD:
                need_fix.append((code, max_f, cnt))
            else:
                skipped += 1

        logger.info(
            "扫描完成：共 %s 只股票；需归一化 %s 只；已是内部约定跳过 %s 只",
            len(codes),
            len(need_fix),
            skipped,
        )

        total_rows = 0
        for code, max_f, cnt in need_fix:
            result = db.execute(
                text(
                    """
                    UPDATE stock_adj_factor
                    SET adj_factor = 1.0 / adj_factor,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source = :source
                      AND code = :code
                      AND adj_factor > 0
                    """
                ),
                {"source": SOURCE, "code": code},
            )
            n = int(result.rowcount or 0)
            total_rows += n
            logger.info(
                "已归一化 code=%s max_was=%.6f rows=%s (expect≈%s)",
                code,
                max_f,
                n,
                cnt,
            )

        db.commit()
        logger.info(
            "新浪复权因子归一化完成：影响股票数=%s，影响行数=%s",
            len(need_fix),
            total_rows,
        )
        print(
            f"normalize_sina_adj_factor_reciprocal: "
            f"stocks={len(need_fix)}, rows={total_rows}, skipped_stocks={skipped}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
