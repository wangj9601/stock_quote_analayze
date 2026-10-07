"""
迁移：将策略/资金流/复盘/简报等节点挂入「A股收盘后标准流程」。

已有节点（rs/gms/urt/index_daily 等）跳过；缺失则按依赖顺序插入。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WF_NAME = "A股收盘后标准流程"

# (after_node_key, node_key, display_name, on_failure)
# 按依赖链依次插入；锚点不存在则追加到末尾
INSERTS = [
    ("cn_board_historical", "ths_fund_flow_daily", "同花顺资金流入流出日采", "continue"),
    ("ths_fund_flow_daily", "board_fund_flow_daily", "板块资金流向历史", "continue"),
    ("board_fund_flow_daily", "zt_pool_em_daily", "东财涨停股池历史", "continue"),
    ("zt_pool_em_daily", "market_daily_review", "每日复盘指标", "continue"),
    ("urt_signals_cn", "csb_signals_cn", "CSB信号预计算(A股)", "continue"),
    ("csb_signals_cn", "sbbr_signals_cn", "SBBR信号预计算(A股)", "continue"),
    ("sbbr_signals_cn", "rpe_signals_cn", "RPE信号预计算(A股)", "continue"),
    ("rpe_signals_cn", "stock_recommend_brief", "个股推荐简报(日/周/月)", "continue"),
]

# 确保基础节点也在（旧库可能缺）；先挂基础再挂资金流/复盘，使 ths 插在 board 与 rs 之间
ENSURE_AFTER = [
    ("cn_index_historical", "index_daily_cn", "A股指数日线采集", "continue"),
    ("cn_board_historical", "rs_rating_cn", "A股相对强度RS预计算", "stop"),
    ("rs_rating_cn", "gms_signals_cn", "GMS信号预计算(A股)", "stop"),
    ("gms_signals_cn", "urt_signals_cn", "URT信号预计算(A股)", "stop"),
]


def _insert_after(
    conn,
    *,
    workflow_name: str,
    after_node_key: str,
    node_key: str,
    display_name: str,
    on_failure: str = "continue",
) -> None:
    wf = conn.execute(
        text("SELECT id FROM collection_workflows WHERE name = :name LIMIT 1"),
        {"name": workflow_name},
    ).fetchone()
    if not wf:
        logger.warning("未找到流程「%s」，跳过节点 %s", workflow_name, node_key)
        return
    wf_id = int(wf[0])

    exists = conn.execute(
        text(
            """
            SELECT id FROM collection_workflow_nodes
            WHERE workflow_id = :wid AND node_key = :nk
            LIMIT 1
            """
        ),
        {"wid": wf_id, "nk": node_key},
    ).fetchone()
    if exists:
        # 同步展示名（历史日采等改名）
        conn.execute(
            text(
                """
                UPDATE collection_workflow_nodes
                SET display_name = :dn
                WHERE workflow_id = :wid AND node_key = :nk
                  AND (display_name IS DISTINCT FROM :dn)
                """
            ),
            {"wid": wf_id, "nk": node_key, "dn": display_name},
        )
        logger.info("流程「%s」已包含节点 %s，跳过插入", workflow_name, node_key)
        return

    after = conn.execute(
        text(
            """
            SELECT order_index FROM collection_workflow_nodes
            WHERE workflow_id = :wid AND node_key = :nk
            LIMIT 1
            """
        ),
        {"wid": wf_id, "nk": after_node_key},
    ).fetchone()
    if after:
        target_order = int(after[0]) + 1
    else:
        mx = conn.execute(
            text(
                """
                SELECT COALESCE(MAX(order_index), -1)
                FROM collection_workflow_nodes
                WHERE workflow_id = :wid
                """
            ),
            {"wid": wf_id},
        ).scalar()
        target_order = int(mx) + 1
        logger.warning(
            "流程「%s」未找到锚点 %s，将 %s 追加到末尾 order=%s",
            workflow_name,
            after_node_key,
            node_key,
            target_order,
        )

    conn.execute(
        text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index + 1000
            WHERE workflow_id = :wid AND order_index >= :ord
            """
        ),
        {"wid": wf_id, "ord": target_order},
    )
    conn.execute(
        text(
            """
            UPDATE collection_workflow_nodes
            SET order_index = order_index - 999
            WHERE workflow_id = :wid AND order_index >= :ord_hi
            """
        ),
        {"wid": wf_id, "ord_hi": target_order + 1000},
    )
    conn.execute(
        text(
            """
            INSERT INTO collection_workflow_nodes (
                workflow_id, order_index, node_key, display_name,
                params, on_failure, retry_count, wait_seconds, enabled
            ) VALUES (
                :wid, :ord, :nk, :dn,
                '{}'::jsonb, :fail, 0, 0, TRUE
            )
            """
        ),
        {
            "wid": wf_id,
            "ord": target_order,
            "nk": node_key,
            "dn": display_name,
            "fail": on_failure,
        },
    )
    logger.info(
        "已向「%s」插入节点 %s @ order_index=%s（%s 之后）",
        workflow_name,
        node_key,
        target_order,
        after_node_key,
    )


def upgrade():
    with engine.begin() as conn:
        for after_key, node_key, display_name, on_failure in ENSURE_AFTER + INSERTS:
            _insert_after(
                conn,
                workflow_name=WF_NAME,
                after_node_key=after_key,
                node_key=node_key,
                display_name=display_name,
                on_failure=on_failure,
            )


if __name__ == "__main__":
    upgrade()
