"""港股历史上传：同花顺伪 xls 解析与规范命名为 CSV。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend_core.data_collectors.akshare.hk_historical_import_from_file import (
    HK_HIST_FILE_PREFIX,
    load_hk_quote_file_dataframe,
    normalize_hk_historical_upload_df,
    save_hk_historical_upload_as_csv,
)


def _make_ths_fake_xls(path: Path) -> Path:
    """同花顺风格：GBK + 制表符，表头带尾部空格。"""
    header = "代码\t名称    \t涨幅%\t现价\t总手\t昨收\t开盘\t最高\t最低\t金额\t涨跌\r\n"
    row = "HK0001\t长和\t+1.44\t70.350\t5609920\t69.350\t69.500\t70.350\t69.200\t392325440\t+1.000\r\n"
    path.write_bytes((header + row).encode("gbk"))
    return path


def test_load_ths_fake_xls_preserves_chinese_headers(tmp_path: Path):
    src = _make_ths_fake_xls(tmp_path / "Table.xls")
    df = load_hk_quote_file_dataframe(src)
    strips = {str(c).strip() for c in df.columns}
    assert "代码" in strips
    assert "名称" in strips
    assert "现价" in strips


def test_normalize_handles_trailing_spaces_in_headers():
    df = pd.DataFrame(
        [
            {
                "代码": "HK0700",
                "名称    ": "腾讯控股",
                "现价": 300.0,
                "昨收": 290.0,
                "开盘": 295.0,
                "最高": 305.0,
                "最低": 294.0,
                "总手": 1000,
                "金额": 3e8,
                "涨幅%": 3.45,
                "涨跌": 10.0,
            }
        ]
    )
    out = normalize_hk_historical_upload_df(df, "20260909")
    assert len(out) == 1
    assert out.iloc[0]["code"] == "00700"
    assert out.iloc[0]["name"] == "腾讯控股"
    assert float(out.iloc[0]["close"]) == 300.0
    assert out.iloc[0]["trade_date"] == "20260909"


def test_save_hk_historical_upload_as_csv(tmp_path: Path):
    src = _make_ths_fake_xls(tmp_path / "Table (1).xls")
    result = save_hk_historical_upload_as_csv(src, "2026-09-09", data_dir=tmp_path)
    assert result["filename"] == f"{HK_HIST_FILE_PREFIX}20260909.csv"
    assert result["file_type"] == "csv"
    assert result["rows"] == 1
    out = Path(result["path"])
    assert out.exists()
    text = out.read_text(encoding="utf-8-sig")
    assert "00001,20260909,长和" in text.replace(" ", "")
