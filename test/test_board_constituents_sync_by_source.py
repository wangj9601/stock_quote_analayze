"""成分同步：按 board_code_source 路由；全来源进入路径；preserve 不受影响。"""

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
    sql_board_code_source_preserve_on_conflict,
)
from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
    IndustryBoardConstituentsCollector,
    resolve_industry_cons_fetcher,
)
from backend_core.data_collectors.akshare.concept_board_constituents_ak import (
    ConceptBoardConstituentsCollector,
)
from backend_core.data_collectors.akshare.ths_board_constituents import (
    _parse_cons_table,
    resolve_ths_board_code,
)


def test_resolve_fetcher_by_source():
    assert resolve_industry_cons_fetcher("eastmoney") == "eastmoney"
    assert resolve_industry_cons_fetcher(None) == "eastmoney"  # LEGACY
    assert resolve_industry_cons_fetcher("") == "eastmoney"
    assert resolve_industry_cons_fetcher("tonghuashun") == "tonghuashun"
    assert resolve_industry_cons_fetcher("同花顺") == "tonghuashun"
    assert resolve_industry_cons_fetcher("manual") == "unsupported"
    assert resolve_industry_cons_fetcher("huatai") == "unsupported"
    assert resolve_industry_cons_fetcher("other") == "unsupported"


def test_parse_ths_cons_table_html():
    html = """
    <html><body>
    <span class="page_info">1/2</span>
    <table>
      <tr><th>序号</th><th>代码</th><th>名称</th><th>现价</th></tr>
      <tr><td>1</td><td>000001</td><td>平安银行</td><td>10</td></tr>
      <tr><td>2</td><td>600036</td><td>招商银行</td><td>20</td></tr>
    </table>
    </body></html>
    """
    rows, pages = _parse_cons_table(html)
    assert pages == 2
    assert rows == [("000001", "平安银行"), ("600036", "招商银行")]


def test_resolve_ths_board_code_numeric():
    assert resolve_ths_board_code("881121", "半导体", kind="industry") == "881121"


def _make_industry_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    session.execute(
        text(
            """
            CREATE TABLE industry_board_basic_info (
                board_code VARCHAR(20) PRIMARY KEY,
                board_name VARCHAR(100),
                board_code_source VARCHAR(32)
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE TABLE industry_board_constituents (
                board_code VARCHAR(20) NOT NULL,
                stock_code VARCHAR(10) NOT NULL,
                stock_name VARCHAR(50),
                updated_at TIMESTAMP,
                PRIMARY KEY (board_code, stock_code)
            )
            """
        )
    )
    session.commit()
    return session


def test_industry_run_routes_all_sources_and_skips_manual():
    """全量同步：东财/同花顺都进入对应 fetch；manual 计入 skip。"""
    session = _make_industry_session()
    now = datetime(2026, 8, 7, 12, 0, 0)
    session.execute(
        text(
            "INSERT INTO industry_board_basic_info VALUES ('BK0420', '半导体', 'eastmoney')"
        )
    )
    session.execute(
        text(
            "INSERT INTO industry_board_basic_info VALUES ('881101', '半导体', 'tonghuashun')"
        )
    )
    session.execute(
        text(
            "INSERT INTO industry_board_basic_info VALUES ('MANUAL1', '自定义', 'manual')"
        )
    )
    session.commit()

    collector = IndustryBoardConstituentsCollector()
    em_calls = []
    ths_calls = []

    def fake_em(code, name=None):
        em_calls.append((code, name))
        return [("000001", "平安银行")]

    def fake_ths(code, name=None):
        ths_calls.append((code, name))
        return [("600036", "招商银行")]

    class _FakeSessionLocal:
        def __call__(self):
            return session

    with patch(
        "backend_core.data_collectors.akshare.industry_board_constituents_ak.SessionLocal",
        side_effect=[session, session],
    ), patch.object(collector, "fetch_board_constituents_eastmoney", side_effect=fake_em), patch.object(
        collector, "fetch_board_constituents_tonghuashun", side_effect=fake_ths
    ), patch.object(collector, "write_log"):
        # run 会再开 SessionLocal 写日志；上面 side_effect 两次：主会话 + write_log
        result = collector.run()

    assert em_calls == [("BK0420", "半导体")]
    assert ths_calls == [("881101", "半导体")]
    assert result["ok_boards"] == 2
    assert len(result["skip_boards"]) == 1
    assert result["skip_boards"][0]["board_code"] == "MANUAL1"
    assert result["skip_boards"][0]["source"] == "manual"
    assert result["by_source"]["eastmoney"]["ok"] == 1
    assert result["by_source"]["tonghuashun"]["ok"] == 1
    assert result["by_source"]["manual"]["skip"] == 1

    rows = session.execute(
        text("SELECT board_code, stock_code FROM industry_board_constituents ORDER BY board_code")
    ).fetchall()
    assert ("BK0420", "000001") in rows
    assert ("881101", "600036") in rows


def test_industry_single_board_uses_db_source():
    """行级同步：按库中 board_code_source 选采集器，不只走东财。"""
    session = _make_industry_session()
    session.execute(
        text(
            "INSERT INTO industry_board_basic_info VALUES ('881101', '半导体', 'tonghuashun')"
        )
    )
    session.commit()
    collector = IndustryBoardConstituentsCollector()
    ths_calls = []

    def fake_ths(code, name=None):
        ths_calls.append(code)
        return [("000002", "万科A")]

    with patch(
        "backend_core.data_collectors.akshare.industry_board_constituents_ak.SessionLocal",
        side_effect=[session, session],
    ), patch.object(collector, "fetch_board_constituents_tonghuashun", side_effect=fake_ths), patch.object(
        collector, "fetch_board_constituents_eastmoney", side_effect=AssertionError("不应走东财")
    ), patch.object(collector, "write_log"):
        result = collector.run(board_codes=["881101"])

    assert ths_calls == ["881101"]
    assert result["ok_boards"] == 1
    assert result["by_source"]["tonghuashun"]["ok"] == 1


def test_concept_run_routes_ths_and_em():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    session.execute(
        text(
            """
            CREATE TABLE concept_board_basic_info (
                board_code VARCHAR(20) PRIMARY KEY,
                board_name VARCHAR(100),
                board_code_source VARCHAR(32)
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE TABLE concept_board_constituents (
                board_code VARCHAR(20) NOT NULL,
                stock_code VARCHAR(10) NOT NULL,
                stock_name VARCHAR(50),
                updated_at TIMESTAMP,
                PRIMARY KEY (board_code, stock_code)
            )
            """
        )
    )
    session.execute(
        text("INSERT INTO concept_board_basic_info VALUES ('BK1641', '机器人', 'eastmoney')")
    )
    session.execute(
        text("INSERT INTO concept_board_basic_info VALUES ('885556', '机器人', 'tonghuashun')")
    )
    session.commit()

    collector = ConceptBoardConstituentsCollector()
    em_calls, ths_calls = [], []

    with patch(
        "backend_core.data_collectors.akshare.concept_board_constituents_ak.SessionLocal",
        side_effect=[session, session],
    ), patch.object(
        collector,
        "fetch_board_constituents_eastmoney",
        side_effect=lambda code: em_calls.append(code) or [("000001", "A")],
    ), patch.object(
        collector,
        "fetch_board_constituents_tonghuashun",
        side_effect=lambda code, name=None: ths_calls.append(code) or [("000002", "B")],
    ), patch.object(collector, "write_log"):
        result = collector.run()

    assert em_calls == ["BK1641"]
    assert ths_calls == ["885556"]
    assert result["ok_boards"] == 2


def test_cons_sync_does_not_overwrite_board_code_source():
    """成分同步只写 constituents，basic_info.board_code_source 保持不变。"""
    session = _make_industry_session()
    session.execute(
        text(
            "INSERT INTO industry_board_basic_info VALUES ('881101', '半导体', 'tonghuashun')"
        )
    )
    session.commit()
    collector = IndustryBoardConstituentsCollector()

    with patch(
        "backend_core.data_collectors.akshare.industry_board_constituents_ak.SessionLocal",
        side_effect=[session, session],
    ), patch.object(
        collector,
        "fetch_board_constituents_tonghuashun",
        return_value=[("600036", "招商银行")],
    ), patch.object(collector, "write_log"):
        collector.run(board_codes=["881101"])

    src = session.execute(
        text(
            "SELECT board_code_source FROM industry_board_basic_info WHERE board_code='881101'"
        )
    ).scalar()
    assert src == "tonghuashun"


def test_concept_list_ths_upsert_preserves_existing_source():
    """概念列表同花顺 upsert 不得覆盖已有来源。"""
    from backend_core.data_collectors.akshare.concept_board_basic_ak import (
        ConceptBoardBasicCollector,
    )

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
    now = datetime(2026, 8, 7, 12, 0, 0)
    session.execute(
        text(
            """
            INSERT INTO concept_board_basic_info
                (board_code, board_name, create_date, board_code_source)
            VALUES ('885556', '机器人概念', :now, 'manual')
            """
        ),
        {"now": now},
    )
    session.commit()

    collector = ConceptBoardBasicCollector()
    ths_df = pd.DataFrame([{"board_code": "885556", "board_name": "机器人概念"}])
    n = collector._upsert_rows(
        session, ths_df, now=now, incoming_source="tonghuashun"
    )
    session.commit()
    assert n == 1
    src = session.execute(
        text(
            "SELECT board_code_source FROM concept_board_basic_info WHERE board_code='885556'"
        )
    ).scalar()
    assert src == "manual"


def test_preserve_sql_still_used_on_em_list_conflict():
    frag = sql_board_code_source_preserve_on_conflict("concept_board_basic_info")
    assert "COALESCE" in frag
    assert SYNC_BOARD_CODE_SOURCE == "eastmoney"
