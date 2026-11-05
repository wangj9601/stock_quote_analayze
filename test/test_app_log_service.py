# -*- coding: utf-8 -*-
"""应用日志扫描服务单元测试。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend_api.services import app_log_service as svc


def test_is_whitelist_name():
    assert svc.is_whitelist_name("app.log")
    assert svc.is_whitelist_name("quotes.log")
    assert svc.is_whitelist_name("akshare_historicalquotecollector.log")
    assert svc.is_whitelist_name("enhanced_akshare_foo.log")
    assert svc.is_whitelist_name("app.log.1")
    assert not svc.is_whitelist_name("scheduler.log")
    assert not svc.is_whitelist_name("../etc/passwd")


def test_redact_secrets():
    text = (
        "conn=postgresql+psycopg2://postgres:secretpass@localhost:5446/stock_analysis "
        "password=abc123 DB_PASSWORD=xyz"
    )
    out = svc.redact_secrets(text)
    assert "secretpass" not in out
    assert "abc123" not in out
    assert "xyz" not in out
    assert "***" in out


def test_parse_log_text_multiline_stack(tmp_path: Path):
    text = (
        "2026-11-04 16:13:46,100 - backend_core.monitoring.system_monitor - ERROR - "
        "[system_monitor.py:10] - 记录指标失败 cpu_usage: boom\n"
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1, in <module>\n'
        "OperationalError: connection refused\n"
        "2026-11-04 16:13:51,200 - backend_api.main - WARNING - 权限注册表增量同步失败\n"
    )
    records = svc.parse_log_text(text, "app.log")
    assert len(records) == 2
    assert records[0].level == "ERROR"
    assert "Traceback" in records[0].message
    assert "connection refused" in records[0].message
    assert records[1].level == "WARNING"
    assert records[1].logger == "backend_api.main"


def test_scan_app_logs_filters(tmp_path: Path):
    log_file = tmp_path / "app.log"
    lines = []
    for i, level in enumerate(["INFO", "WARNING", "ERROR", "INFO"]):
        lines.append(
            f"2026-11-04 16:1{i}:00,000 - demo.logger - {level} - [a.py:1] - message-{level}-{i}"
        )
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = svc.scan_app_logs(
        levels="WARNING,ERROR",
        start_date="2026-11-04",
        end_date="2026-11-04",
        keyword=None,
        source_file=None,
        page=1,
        page_size=20,
        logs_dir=tmp_path,
        window_bytes=1024 * 1024,
    )
    assert result["total"] == 2
    assert result["stats"]["error"] == 1
    assert result["stats"]["warning"] == 1
    levels = {row["level"] for row in result["data"]}
    assert levels == {"WARNING", "ERROR"}
    assert any(f["name"] == "app.log" for f in result["files"])


def test_scan_rejects_non_whitelist_via_empty_targets(tmp_path: Path):
    (tmp_path / "secret.log").write_text(
        "2026-11-04 16:10:00,000 - x - ERROR - should-not-see\n",
        encoding="utf-8",
    )
    result = svc.scan_app_logs(
        levels="all",
        logs_dir=tmp_path,
        window_bytes=1024,
    )
    assert result["total"] == 0
    assert result["files"] == []


def test_keyword_and_pagination(tmp_path: Path):
    log_file = tmp_path / "quotes.log"
    rows = []
    for i in range(5):
        rows.append(
            f"2026-11-04 12:00:0{i},000 - quotes - ERROR - [q.py:1] - fail-item-{i}"
        )
    log_file.write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = svc.scan_app_logs(
        levels="ERROR",
        keyword="fail-item-4",
        page=1,
        page_size=10,
        logs_dir=tmp_path,
    )
    assert result["total"] == 1
    assert "fail-item-4" in result["data"][0]["message"]

    page1 = svc.scan_app_logs(levels="ERROR", page=1, page_size=2, logs_dir=tmp_path)
    page2 = svc.scan_app_logs(levels="ERROR", page=2, page_size=2, logs_dir=tmp_path)
    assert page1["total"] == 5
    assert len(page1["data"]) == 2
    assert len(page2["data"]) == 2
    assert page1["data"][0]["id"] != page2["data"][0]["id"]
