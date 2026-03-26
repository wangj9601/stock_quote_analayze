from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text


_COLUMN_ALIASES = {
    "code": ["code", "代码", "股票代码", "证券代码"],
    "name": ["name", "名称", "股票名称", "证券简称", "简称"],
    "market": ["market", "市场", "市场类型"],
    "total_shares": ["total_shares", "总股本", "总股本(股)"],
    "free_float_shares": ["free_float_shares", "流通股", "流通股本", "流通股(股)", "流通股本(股)"],
    "listing_date": ["listing_date", "上市日期", "上市时间"],
    "industry": ["industry", "行业", "所属行业"],
    "asof_date": ["asof_date", "数据日期", "基准日期", "生效日期"],
    "collect_enabled": ["collect_enabled", "enabled", "is_enabled", "是否采集", "是否处理", "采集标志"],
}


@dataclass
class ImportIssue:
    row_no: int
    code: str
    message: str


def _pick_col(columns: List[str], aliases: List[str]) -> Optional[str]:
    lowered = {c.strip().lower(): c for c in columns}
    for alias in aliases:
        key = alias.strip().lower()
        if key in lowered:
            return lowered[key]
    return None


def normalize_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if not s:
        return ""
    for prefix in ("SH", "SZ", "BJ", "HK"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if "." in s:
        s = s.split(".")[0]
    if s.isdigit() and len(s) <= 5:
        return s.zfill(5)
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def detect_market(code: str, market_raw: Optional[str]) -> str:
    mr = str(market_raw or "").strip().upper()
    if mr in ("A", "CN", "ASHARE", "A股"):
        return "CN"
    if mr in ("HK", "H", "港股"):
        return "HK"
    pure = code.strip()
    if pure.isdigit() and len(pure) == 6:
        return "CN"
    return "HK"


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in ("-", "nan", "None"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f


def _to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "是", "启用", "enabled", "on"):
        return True
    if s in ("0", "false", "no", "n", "否", "停用", "disabled", "off"):
        return False
    return None


def _read_df_from_bytes(filename: str, content: bytes) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(BytesIO(content))
    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                return pd.read_csv(BytesIO(content), encoding=enc)
            except Exception:
                continue
    raise ValueError("仅支持 CSV/XLSX 文件")


def parse_import_file(filename: str, content: bytes) -> Tuple[List[Dict[str, Any]], List[ImportIssue]]:
    df = _read_df_from_bytes(filename, content)
    if df is None or df.empty:
        return [], [ImportIssue(row_no=0, code="", message="文件无数据")]

    columns = list(df.columns)
    picked = {k: _pick_col(columns, v) for k, v in _COLUMN_ALIASES.items()}
    if not picked["code"]:
        return [], [ImportIssue(row_no=0, code="", message="缺少 code/代码 列")]

    records: List[Dict[str, Any]] = []
    issues: List[ImportIssue] = []

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        code = normalize_code(row.get(picked["code"])) if picked["code"] else ""
        if not code:
            issues.append(ImportIssue(row_no=row_no, code="", message="代码为空"))
            continue

        name = str(row.get(picked["name"], "") or "").strip() if picked["name"] else ""
        market = detect_market(code, row.get(picked["market"]) if picked["market"] else None)
        total_shares = _to_float(row.get(picked["total_shares"])) if picked["total_shares"] else None
        free_float_shares = _to_float(row.get(picked["free_float_shares"])) if picked["free_float_shares"] else None
        listing_date = str(row.get(picked["listing_date"], "") or "").strip() if picked["listing_date"] else ""
        industry = str(row.get(picked["industry"], "") or "").strip() if picked["industry"] else ""
        asof_date = str(row.get(picked["asof_date"], "") or "").strip() if picked["asof_date"] else ""
        collect_enabled = _to_bool(row.get(picked["collect_enabled"])) if picked["collect_enabled"] else None

        if total_shares is not None and total_shares <= 0:
            issues.append(ImportIssue(row_no=row_no, code=code, message="total_shares 必须为正数"))
            continue
        if free_float_shares is not None and free_float_shares <= 0:
            issues.append(ImportIssue(row_no=row_no, code=code, message="free_float_shares 必须为正数"))
            continue
        if (
            total_shares is not None
            and free_float_shares is not None
            and free_float_shares > total_shares
        ):
            issues.append(ImportIssue(row_no=row_no, code=code, message="free_float_shares 不能大于 total_shares"))
            continue

        records.append(
            {
                "row_no": row_no,
                "code": code,
                "name": name,
                "market": market,
                "total_shares": total_shares,
                "free_float_shares": free_float_shares,
                "listing_date": listing_date or None,
                "industry": industry or None,
                "asof_date": asof_date or None,
                "collect_enabled": collect_enabled,
            }
        )

    return records, issues


def ensure_share_columns(session) -> None:
    session.execute(
        text(
            """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='total_shares') THEN
                ALTER TABLE stock_basic_info ADD COLUMN total_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='free_float_shares') THEN
                ALTER TABLE stock_basic_info ADD COLUMN free_float_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='shares_updated_at') THEN
                ALTER TABLE stock_basic_info ADD COLUMN shares_updated_at TIMESTAMP;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='industry') THEN
                ALTER TABLE stock_basic_info ADD COLUMN industry TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='listing_date') THEN
                ALTER TABLE stock_basic_info ADD COLUMN listing_date TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info' AND column_name='collect_enabled') THEN
                ALTER TABLE stock_basic_info ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
            END IF;
        END
        $$;
        """
        )
    )
    session.execute(
        text(
            """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='total_shares') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN total_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='free_float_shares') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN free_float_shares REAL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='shares_updated_at') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN shares_updated_at TIMESTAMP;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='industry') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN industry TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='listing_date') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN listing_date TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='stock_basic_info_hk' AND column_name='collect_enabled') THEN
                ALTER TABLE stock_basic_info_hk ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
            END IF;
        END
        $$;
        """
        )
    )
    session.commit()


def _update_cn_only_fill_empty(session, row: Dict[str, Any]) -> int:
    ret = session.execute(
        text(
            """
            UPDATE stock_basic_info
            SET
                name = CASE WHEN (name IS NULL OR name = '') THEN COALESCE(:name, name) ELSE name END,
                total_shares = CASE WHEN total_shares IS NULL THEN :total_shares ELSE total_shares END,
                free_float_shares = CASE WHEN free_float_shares IS NULL THEN :free_float_shares ELSE free_float_shares END,
                industry = CASE WHEN (industry IS NULL OR industry = '') THEN :industry ELSE industry END,
                listing_date = CASE WHEN (listing_date IS NULL OR listing_date = '') THEN :listing_date ELSE listing_date END,
                collect_enabled = CASE WHEN :collect_enabled IS NOT NULL THEN :collect_enabled ELSE collect_enabled END,
                shares_updated_at = CASE
                    WHEN shares_updated_at IS NULL AND
                         (:total_shares IS NOT NULL OR :free_float_shares IS NOT NULL OR :industry IS NOT NULL OR :listing_date IS NOT NULL)
                    THEN :updated_at
                    ELSE shares_updated_at
                END
            WHERE CAST(code AS TEXT) = :code
            """
        ),
        {
            "code": row["code"].zfill(6),
            "name": row.get("name"),
            "total_shares": row.get("total_shares"),
            "free_float_shares": row.get("free_float_shares"),
            "industry": row.get("industry"),
            "listing_date": row.get("listing_date"),
            "collect_enabled": row.get("collect_enabled"),
            "updated_at": datetime.now(),
        },
    )
    return ret.rowcount or 0


def _update_hk_only_fill_empty(session, row: Dict[str, Any]) -> int:
    ret = session.execute(
        text(
            """
            UPDATE stock_basic_info_hk
            SET
                name = CASE WHEN (name IS NULL OR name = '') THEN COALESCE(:name, name) ELSE name END,
                total_shares = CASE WHEN total_shares IS NULL THEN :total_shares ELSE total_shares END,
                free_float_shares = CASE WHEN free_float_shares IS NULL THEN :free_float_shares ELSE free_float_shares END,
                industry = CASE WHEN (industry IS NULL OR industry = '') THEN :industry ELSE industry END,
                listing_date = CASE WHEN (listing_date IS NULL OR listing_date = '') THEN :listing_date ELSE listing_date END,
                collect_enabled = CASE WHEN :collect_enabled IS NOT NULL THEN :collect_enabled ELSE collect_enabled END,
                shares_updated_at = CASE
                    WHEN shares_updated_at IS NULL AND
                         (:total_shares IS NOT NULL OR :free_float_shares IS NOT NULL OR :industry IS NOT NULL OR :listing_date IS NOT NULL)
                    THEN :updated_at
                    ELSE shares_updated_at
                END
            WHERE code = :code
            """
        ),
        {
            "code": row["code"],
            "name": row.get("name"),
            "total_shares": row.get("total_shares"),
            "free_float_shares": row.get("free_float_shares"),
            "industry": row.get("industry"),
            "listing_date": row.get("listing_date"),
            "collect_enabled": row.get("collect_enabled"),
            "updated_at": datetime.now(),
        },
    )
    return ret.rowcount or 0


def execute_import_rows(
    session,
    rows: List[Dict[str, Any]],
    mode: str = "only_fill_empty",
    dry_run: bool = False,
    max_errors: int = 100,
) -> Dict[str, Any]:
    if mode not in ("only_fill_empty",):
        raise ValueError("仅支持 only_fill_empty 模式")

    ensure_share_columns(session)
    success = 0
    skipped = 0
    failed = 0
    failures: List[Dict[str, Any]] = []
    market_count = {"CN": 0, "HK": 0}

    for row in rows:
        market = row.get("market", "CN")
        code = row.get("code", "")
        market_count[market] = market_count.get(market, 0) + 1

        try:
            if dry_run:
                success += 1
                continue

            affected = _update_cn_only_fill_empty(session, row) if market == "CN" else _update_hk_only_fill_empty(session, row)
            if affected > 0:
                success += 1
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            failures.append({"row_no": row.get("row_no"), "code": code, "message": str(e)})
            if failed >= max_errors:
                break

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return {
        "mode": mode,
        "dry_run": dry_run,
        "total_rows": len(rows),
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "market_count": market_count,
        "failures": failures,
        "failed_sample": failures[:20],
    }


def issues_to_dict(issues: List[ImportIssue]) -> List[Dict[str, Any]]:
    return [asdict(x) for x in issues]

