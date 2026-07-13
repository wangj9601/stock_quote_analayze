# -*- coding: utf-8 -*-
"""每月交易日志：归一化与响应映射单元测试（不连库）。"""

import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parents[1]
backend_api = project_root / "backend_api"
for p in (str(project_root), str(backend_api)):
    if p not in sys.path:
        sys.path.insert(0, p)

from trading_notes_routes import _normalize_month_start, _journal_to_response  # noqa: E402


def test_normalize_month_start():
    assert _normalize_month_start(date(2026, 7, 13)) == date(2026, 7, 1)
    assert _normalize_month_start(date(2026, 7, 1)) == date(2026, 7, 1)
    assert _normalize_month_start(date(2025, 12, 31)) == date(2025, 12, 1)


def test_journal_to_response_monthly_exposes_month_start():
    now = datetime(2026, 7, 13, 8, 0, 0)
    record = SimpleNamespace(
        id=1,
        user_id=9,
        log_type="monthly",
        log_date=date(2026, 7, 1),
        week_start=None,
        mood=None,
        score="A",
        content="本月复盘",
        created_at=now,
        updated_at=now,
    )
    resp = _journal_to_response(record)
    assert resp.log_type == "monthly"
    assert resp.month_start == date(2026, 7, 1)
    assert resp.log_date == date(2026, 7, 1)
    assert resp.score == "A"


def test_journal_to_response_daily_has_no_month_start():
    now = datetime(2026, 7, 13, 8, 0, 0)
    record = SimpleNamespace(
        id=2,
        user_id=9,
        log_type="daily",
        log_date=date(2026, 7, 13),
        week_start=None,
        mood="good",
        score=None,
        content="日复盘",
        created_at=now,
        updated_at=now,
    )
    resp = _journal_to_response(record)
    assert resp.month_start is None
