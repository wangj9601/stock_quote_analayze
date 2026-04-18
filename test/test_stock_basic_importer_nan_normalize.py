from __future__ import annotations

from backend_core.utils.stock_basic_importer import parse_import_file


def test_parse_import_file_should_normalize_nan_like_text_fields() -> None:
    csv_content = (
        "code,name,total_shares,free_float_shares,industry,listing_date,collect_enabled\n"
        "000001,平安银行,19405918000,19405600000,nan,nan,true\n"
    ).encode("utf-8")

    rows, issues = parse_import_file("sample.csv", csv_content)

    assert not issues
    assert len(rows) == 1
    assert rows[0]["code"].isdigit()
    assert rows[0]["industry"] is None
    assert rows[0]["listing_date"] is None
    assert rows[0]["collect_enabled"] is True
