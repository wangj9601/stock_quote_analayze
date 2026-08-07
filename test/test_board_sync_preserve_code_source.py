"""东财板块列表同步：已有 tonghuashun 的 board_code_source 不得被覆盖。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.board_code_source import (
    SYNC_BOARD_CODE_SOURCE,
    merge_board_code_source_on_sync,
    sql_board_code_source_preserve_on_conflict,
)


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    session.execute(
        text(
            """
            CREATE TABLE concept_board_basic_info (
                board_code VARCHAR(20) PRIMARY KEY,
                board_name VARCHAR(100),
                create_date TIMESTAMP,
                trade_observe_flag BOOLEAN NOT NULL DEFAULT 0,
                board_code_source VARCHAR(32)
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE TABLE industry_board_basic_info (
                board_code VARCHAR(20) PRIMARY KEY,
                board_name VARCHAR(100),
                create_date TIMESTAMP,
                board_code_source VARCHAR(32)
            )
            """
        )
    )
    session.commit()
    return session


def test_merge_helper_regression():
    assert merge_board_code_source_on_sync("tonghuashun") == "tonghuashun"
    assert merge_board_code_source_on_sync(None) == SYNC_BOARD_CODE_SOURCE


def test_concept_em_upsert_preserves_tonghuashun_source():
    """模拟概念板块列表同步 upsert：同代码已是同花顺则保持不变。"""
    session = _make_sqlite_session()
    now = datetime(2026, 8, 7, 12, 0, 0)
    session.execute(
        text(
            """
            INSERT INTO concept_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES ('BK1641', '人形机器人', :now, 'tonghuashun')
            """
        ),
        {"now": now},
    )
    session.commit()

    preserve = sql_board_code_source_preserve_on_conflict("concept_board_basic_info")
    session.execute(
        text(
            f"""
            INSERT INTO concept_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES (:board_code, :board_name, :create_date, :board_code_source)
            ON CONFLICT (board_code) DO UPDATE SET
                board_name = EXCLUDED.board_name,
                {preserve}
            """
        ),
        {
            "board_code": "BK1641",
            "board_name": "人形机器人",
            "create_date": now,
            "board_code_source": SYNC_BOARD_CODE_SOURCE,
        },
    )
    session.commit()
    row = session.execute(
        text(
            "SELECT board_code_source, board_name FROM concept_board_basic_info "
            "WHERE board_code = 'BK1641'"
        )
    ).fetchone()
    assert row[0] == "tonghuashun"
    assert row[1] == "人形机器人"


def test_concept_em_upsert_sets_eastmoney_for_new_board():
    session = _make_sqlite_session()
    now = datetime(2026, 8, 7, 12, 0, 0)
    preserve = sql_board_code_source_preserve_on_conflict("concept_board_basic_info")
    session.execute(
        text(
            f"""
            INSERT INTO concept_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES (:board_code, :board_name, :create_date, :board_code_source)
            ON CONFLICT (board_code) DO UPDATE SET
                board_name = EXCLUDED.board_name,
                {preserve}
            """
        ),
        {
            "board_code": "BK9999",
            "board_name": "新概念",
            "create_date": now,
            "board_code_source": SYNC_BOARD_CODE_SOURCE,
        },
    )
    session.commit()
    src = session.execute(
        text(
            "SELECT board_code_source FROM concept_board_basic_info WHERE board_code = 'BK9999'"
        )
    ).scalar()
    assert src == "eastmoney"


def test_industry_em_upsert_preserves_tonghuashun_and_skips_name_match():
    """行业同步：同花顺同名板不参与按名匹配；若误撞同代码则来源仍保留。"""
    session = _make_sqlite_session()
    now = datetime(2026, 8, 7, 12, 0, 0)
    session.execute(
        text(
            """
            INSERT INTO industry_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES ('881101', '半导体', :now, 'tonghuashun')
            """
        ),
        {"now": now},
    )
    session.commit()

    # 按名匹配应忽略同花顺板
    matched = session.execute(
        text(
            """
            SELECT board_code FROM industry_board_basic_info
            WHERE TRIM(board_name) = :name
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), 'eastmoney')
                  = 'eastmoney'
            LIMIT 1
            """
        ),
        {"name": "半导体"},
    ).scalar()
    assert matched is None

    # 若按代码冲突，仍保留来源
    preserve = sql_board_code_source_preserve_on_conflict("industry_board_basic_info")
    session.execute(
        text(
            f"""
            INSERT INTO industry_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES (:board_code, :board_name, :create_date, :board_code_source)
            ON CONFLICT (board_code) DO UPDATE SET
                board_name = EXCLUDED.board_name,
                {preserve}
            """
        ),
        {
            "board_code": "881101",
            "board_name": "半导体",
            "create_date": now,
            "board_code_source": SYNC_BOARD_CODE_SOURCE,
        },
    )
    session.commit()
    src = session.execute(
        text(
            "SELECT board_code_source FROM industry_board_basic_info WHERE board_code = '881101'"
        )
    ).scalar()
    assert src == "tonghuashun"


def test_concept_board_basic_collector_uses_preserve_sql():
    """ConceptBoardBasicCollector.run 使用保留来源的 upsert SQL。"""
    from backend_core.data_collectors.akshare.concept_board_basic_ak import (
        ConceptBoardBasicCollector,
    )

    executed_sql: list[str] = []

    class _FakeResult:
        def fetchone(self):
            return None

        def scalar(self):
            return None

    class _FakeSession:
        def execute(self, sql, params=None):
            executed_sql.append(str(sql))
            return _FakeResult()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    fake = _FakeSession()
    collector = ConceptBoardBasicCollector()
    df = pd.DataFrame([{"board_code": "BK1641", "board_name": "人形机器人"}])

    with patch(
        "backend_core.data_collectors.akshare.concept_board_basic_ak.SessionLocal",
        return_value=fake,
    ), patch.object(collector, "fetch_data", return_value=df), patch.object(
        collector, "fetch_ths_data", return_value=pd.DataFrame()
    ), patch.object(collector, "write_log"):
        collector.run(include_ths=True)

    upsert_sql = next((s for s in executed_sql if "ON CONFLICT" in s and "INSERT INTO concept_board_basic_info" in s), "")
    assert upsert_sql, f"未找到 upsert SQL，实际: {executed_sql}"
    assert "COALESCE" in upsert_sql
    assert "concept_board_basic_info.board_code_source" in upsert_sql
    # 禁止旧写法：无条件 board_code_source = EXCLUDED.board_code_source
    assert "board_code_source = EXCLUDED.board_code_source" not in upsert_sql
