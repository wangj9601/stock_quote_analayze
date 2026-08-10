"""RPE 数据加载：行业成分股 + 日线。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)

# 与全站约定一致：空 board_code_source 视为历史东财
_LEGACY_BOARD_CODE_SOURCE = "eastmoney"
_DEFAULT_BOARD_CODE_SOURCE = "tonghuashun"


def _norm_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _resolve_source(raw: Optional[str]) -> str:
    try:
        from backend_api.utils.board_code_source import (
            DEFAULT_BOARD_CODE_SOURCE,
            resolve_board_code_source,
        )

        return resolve_board_code_source(
            raw, fallback=DEFAULT_BOARD_CODE_SOURCE or _DEFAULT_BOARD_CODE_SOURCE
        )
    except Exception:
        s = str(raw or "").strip().lower()
        return s or _DEFAULT_BOARD_CODE_SOURCE


class RPEDataLoader:
    def __init__(self, db_session=None, board_code_source: Optional[str] = None):
        self._db = db_session
        # 行业/概念列表与主板块解析默认仅同花顺，与 GMS「所属行业」一致
        self.board_code_source = _resolve_source(board_code_source)
        # 同一次选股/重算内缓存 ensure_adj_factors 结果，避免成分股重复读库/拉因子
        self._qfq_factor_cache: Dict[str, Dict[str, Any]] = {}

    def _source_params(self) -> Dict[str, str]:
        return {
            "source": self.board_code_source,
            "legacy": _LEGACY_BOARD_CODE_SOURCE,
        }

    @staticmethod
    def _source_sql(alias: str = "b") -> str:
        """COALESCE 空来源为东财后，与目标来源精确匹配。"""
        return (
            f"COALESCE(NULLIF(TRIM({alias}.board_code_source), ''), :legacy) = :source"
        )

    def _session(self):
        if self._db is not None:
            return self._db
        from backend_api.database import SessionLocal

        return SessionLocal()

    def resolve_trade_date(self) -> str:
        db = self._session()
        own = self._db is None
        try:
            from backend_api.models import HistoricalQuotes
            from sqlalchemy import func

            latest = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest:
                return latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
        except Exception as e:
            logger.warning("resolve_trade_date failed: %s", e)
        finally:
            if own:
                db.close()
        return datetime.now().strftime("%Y-%m-%d")

    def list_industry_boards(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                f"""
                SELECT board_code, board_name
                FROM industry_board_basic_info b
                WHERE {self._source_sql("b")}
                ORDER BY board_code
                """
            )
            rows = db.execute(sql, self._source_params()).fetchall()
            out = [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
            if limit:
                out = out[: int(limit)]
            return out
        except Exception as e:
            logger.warning("list_industry_boards failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def list_concept_boards(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                f"""
                SELECT board_code, board_name
                FROM concept_board_basic_info b
                WHERE board_code IS NOT NULL AND TRIM(board_code) <> ''
                  AND {self._source_sql("b")}
                ORDER BY board_code
                """
            )
            rows = db.execute(sql, self._source_params()).fetchall()
            out = [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
            if limit:
                out = out[: int(limit)]
            return out
        except Exception as e:
            logger.warning("list_concept_boards failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def lookup_board_name(self, board_code: str, board_kind: str = "industry") -> Optional[str]:
        """按 board_code 取板块名：优先当前 board_code_source，否则任意来源。"""
        bc = str(board_code or "").strip()
        if not bc:
            return None
        table = (
            "concept_board_basic_info"
            if board_kind == "concept"
            else "industry_board_basic_info"
        )
        db = self._session()
        own = self._db is None
        try:
            params = {"bc": bc, **self._source_params()}
            row = db.execute(
                text(
                    f"""
                    SELECT board_name FROM {table} b
                    WHERE b.board_code = :bc AND {self._source_sql("b")}
                    LIMIT 1
                    """
                ),
                params,
            ).fetchone()
            if row and str(row[0] or "").strip():
                return str(row[0]).strip()
            row2 = db.execute(
                text(
                    f"""
                    SELECT board_name FROM {table}
                    WHERE board_code = :bc
                    LIMIT 1
                    """
                ),
                {"bc": bc},
            ).fetchone()
            if row2 and str(row2[0] or "").strip():
                return str(row2[0]).strip()
            return None
        except Exception as e:
            logger.warning("lookup_board_name %s failed: %s", bc, e)
            return None
        finally:
            if own:
                db.close()

    def load_basic_industry_names(self, codes: List[str]) -> Dict[str, str]:
        """回退：stock_basic_info.industry（展示用，非同花顺成分映射）。"""
        codes_n = list(dict.fromkeys(_norm_code(c) for c in (codes or []) if c))
        if not codes_n:
            return {}
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                """
                SELECT code, industry
                FROM stock_basic_info
                WHERE code IN :codes
                """
            ).bindparams(bindparam("codes", expanding=True))
            rows = db.execute(sql, {"codes": codes_n}).fetchall()
            out: Dict[str, str] = {}
            for r in rows:
                code = _norm_code(r[0])
                ind = str(r[1] or "").strip()
                if code and ind and ind not in ("-", "--", "None", "null"):
                    out[code] = ind
            return out
        except Exception as e:
            logger.warning("load_basic_industry_names failed: %s", e)
            return {}
        finally:
            if own:
                db.close()

    def list_boards(self, board_kind: str = "industry", limit: Optional[int] = None) -> List[Dict[str, str]]:
        if board_kind == "concept":
            return self.list_concept_boards(limit=limit)
        return self.list_industry_boards(limit=limit)

    def load_stock_names(self, codes: List[str]) -> Dict[str, str]:
        """从 stock_basic_info 批量取证券简称（成分表 stock_name 常为空）。"""
        codes_n = list(dict.fromkeys(_norm_code(c) for c in (codes or []) if c))
        if not codes_n:
            return {}
        db = self._session()
        own = self._db is None
        try:
            sql = text(
                """
                SELECT code, name
                FROM stock_basic_info
                WHERE code IN :codes
                """
            ).bindparams(bindparam("codes", expanding=True))
            rows = db.execute(sql, {"codes": codes_n}).fetchall()
            out: Dict[str, str] = {}
            for r in rows:
                code = _norm_code(r[0])
                name = str(r[1] or "").strip()
                if code and name:
                    out[code] = name
            return out
        except Exception as e:
            logger.warning("load_stock_names failed: %s", e)
            return {}
        finally:
            if own:
                db.close()

    def load_board_members(self, board_code: str, board_kind: str = "industry") -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        table = (
            "concept_board_constituents"
            if board_kind == "concept"
            else "industry_board_constituents"
        )
        members: List[Dict[str, str]] = []
        try:
            sql = text(
                f"""
                SELECT stock_code, stock_name
                FROM {table}
                WHERE board_code = :bc
                """
            )
            rows = db.execute(sql, {"bc": board_code}).fetchall()
            members = [
                {"code": _norm_code(r[0]), "name": str(r[1] or "").strip()}
                for r in rows
                if r[0]
            ]
        except Exception as e:
            logger.warning("load_board_members %s (%s) failed: %s", board_code, board_kind, e)
            return []
        finally:
            if own:
                db.close()

        missing = [m["code"] for m in members if not m.get("name")]
        if missing:
            filled = self.load_stock_names(missing)
            for m in members:
                if not m.get("name") and filled.get(m["code"]):
                    m["name"] = filled[m["code"]]
        return members

    def _code_variants(self, code: str) -> List[str]:
        code_n = _norm_code(code)
        raw = str(code or "").strip()
        stripped = code_n.lstrip("0") or code_n
        return list(dict.fromkeys([v for v in (code_n, raw, stripped) if v]))

    def find_boards_for_code(self, code: str, board_kind: str = "industry") -> List[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            variants = self._code_variants(code)
            params = {"codes": variants, **self._source_params()}
            if board_kind == "concept":
                sql = text(
                    f"""
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM concept_board_constituents c
                    INNER JOIN concept_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                      AND {self._source_sql("b")}
                    ORDER BY c.board_code
                    """
                ).bindparams(bindparam("codes", expanding=True))
            else:
                sql = text(
                    f"""
                    SELECT c.board_code, COALESCE(b.board_name, c.board_code)
                    FROM industry_board_constituents c
                    INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                      AND {self._source_sql("b")}
                    ORDER BY c.board_code
                    """
                ).bindparams(bindparam("codes", expanding=True))
            rows = db.execute(sql, params).fetchall()
            return [{"board_code": str(r[0]), "board_name": str(r[1] or r[0])} for r in rows]
        except Exception as e:
            logger.warning("find_boards_for_code failed: %s", e)
            return []
        finally:
            if own:
                db.close()

    def resolve_primary_board(
        self,
        code: str,
        board_kind: str = "industry",
        *,
        allow_fallback: bool = True,
    ) -> Optional[Dict[str, str]]:
        """
        固定个股主板块（用于选股/追溯，避免同股多板块按日跳变）。

        规则：
        1. 优先指定 kind（默认 industry）；行业/概念均仅取 ``board_code_source``（默认同花顺）
        2. 无同花顺行业归属且 allow_fallback 时回退同花顺概念
        3. 同 kind 多板块时取成分股数量最多者
        4. 成分数并列时按 board_code 升序，保证稳定可复现
        """
        kind = "concept" if board_kind == "concept" else "industry"
        picked = self._pick_primary_board_among(code, kind)
        if picked is None and allow_fallback and kind == "industry":
            picked = self._pick_primary_board_among(code, "concept")
        return picked

    def _pick_primary_board_among(self, code: str, board_kind: str) -> Optional[Dict[str, str]]:
        db = self._session()
        own = self._db is None
        try:
            variants = self._code_variants(code)
            params = {"codes": variants, **self._source_params()}
            src_filter = self._source_sql("b")
            src_filter2 = self._source_sql("b2")
            if board_kind == "concept":
                sql = text(
                    f"""
                    SELECT c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name,
                           cnt.n AS member_count
                    FROM concept_board_constituents c
                    JOIN (
                        SELECT c2.board_code, COUNT(*) AS n
                        FROM concept_board_constituents c2
                        INNER JOIN concept_board_basic_info b2 ON b2.board_code = c2.board_code
                        WHERE {src_filter2}
                        GROUP BY c2.board_code
                    ) cnt ON cnt.board_code = c.board_code
                    INNER JOIN concept_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                      AND {src_filter}
                    ORDER BY cnt.n DESC, c.board_code ASC
                    LIMIT 1
                    """
                ).bindparams(bindparam("codes", expanding=True))
            else:
                sql = text(
                    f"""
                    SELECT c.board_code,
                           COALESCE(b.board_name, c.board_code) AS board_name,
                           cnt.n AS member_count
                    FROM industry_board_constituents c
                    JOIN (
                        SELECT c2.board_code, COUNT(*) AS n
                        FROM industry_board_constituents c2
                        INNER JOIN industry_board_basic_info b2 ON b2.board_code = c2.board_code
                        WHERE {src_filter2}
                        GROUP BY c2.board_code
                    ) cnt ON cnt.board_code = c.board_code
                    INNER JOIN industry_board_basic_info b ON b.board_code = c.board_code
                    WHERE c.stock_code IN :codes
                      AND {src_filter}
                    ORDER BY cnt.n DESC, c.board_code ASC
                    LIMIT 1
                    """
                ).bindparams(bindparam("codes", expanding=True))
            row = db.execute(sql, params).fetchone()
            if not row:
                return None
            return {
                "board_code": str(row[0]),
                "board_name": str(row[1] or row[0]),
                "board_kind": "concept" if board_kind == "concept" else "industry",
                "member_count": int(row[2] or 0),
                "board_code_source": self.board_code_source,
            }
        except Exception as e:
            logger.warning("resolve_primary_board failed: %s", e)
            return None
        finally:
            if own:
                db.close()

    def load_bars(
        self,
        code: str,
        *,
        end_date: Optional[str] = None,
        limit: Optional[int] = 250,
        adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        db = self._session()
        own = self._db is None
        try:
            code_n = _norm_code(code)
            params: Dict[str, Any] = {"code": code_n}
            lim_sql = ""
            if limit is not None and int(limit) > 0:
                params["lim"] = int(limit)
                lim_sql = " LIMIT :lim"
            if end_date:
                params["d"] = end_date
                sql = text(
                    f"""
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code AND date <= :d
                    ORDER BY date DESC
                    {lim_sql}
                    """
                )
            else:
                sql = text(
                    f"""
                    SELECT date, open, high, low, close, volume, amount, turnover_rate
                    FROM historical_quotes
                    WHERE code = :code
                    ORDER BY date DESC
                    {lim_sql}
                    """
                )
            rows = db.execute(sql, params).fetchall()
            bars = []
            for r in reversed(rows):
                d = r[0]
                ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                bars.append(
                    {
                        "date": ds,
                        "open": float(r[1] or 0),
                        "high": float(r[2] or 0),
                        "low": float(r[3] or 0),
                        "close": float(r[4] or 0),
                        "volume": float(r[5] or 0),
                        "amount": float(r[6] or 0) if r[6] is not None else None,
                        "turnover_rate": float(r[7]) if r[7] is not None else None,
                    }
                )
            adjust_n = str(adjust or "none").strip().lower() or "none"
            if adjust_n == "qfq" and bars:
                bars = self._apply_qfq_bars(
                    db,
                    code_n,
                    bars,
                    factor_source=factor_source,
                    refresh_factor=refresh_factor,
                )
            return bars
        except Exception as e:
            logger.warning("load_bars %s failed: %s", code, e)
            return []
        finally:
            if own:
                db.close()

    def _apply_qfq_bars(
        self,
        db,
        code: str,
        bars: List[Dict[str, Any]],
        *,
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        """对已加载的不复权 bars 现算前复权；失败返回空列表（从 panel 中剔除，避免混口径）。

        因子：prefer_db=True → 优先 stock_adj_factor；库中没有才调第三方并 UPSERT。
        """
        try:
            from backend_api.utils.adj_quotes import (
                AdjQuotesError,
                apply_qfq_to_bars,
                ensure_adj_factors,
            )
        except ImportError:
            from utils.adj_quotes import (  # type: ignore
                AdjQuotesError,
                apply_qfq_to_bars,
                ensure_adj_factors,
            )
        try:
            cache_key = f"{code}|{factor_source or 'auto'}|{int(bool(refresh_factor))}"
            ensured = self._qfq_factor_cache.get(cache_key)
            if ensured is None:
                # 整策略前复权：强制优先读库，禁止因“过期”批量打外网
                ensured = ensure_adj_factors(
                    db,
                    code,
                    force_refresh=bool(refresh_factor),
                    factor_source=factor_source or "auto",
                    prefer_db=True,
                )
                self._qfq_factor_cache[cache_key] = ensured
                if ensured.get("factor_fetched"):
                    logger.info(
                        "RPE 复权因子外网补齐并入库 code=%s source=%s asof=%s",
                        code,
                        ensured.get("source"),
                        ensured.get("adj_factor_asof"),
                    )
                else:
                    logger.debug(
                        "RPE 复权因子读库 code=%s source=%s asof=%s",
                        code,
                        ensured.get("source"),
                        ensured.get("adj_factor_asof"),
                    )
            return apply_qfq_to_bars(bars, ensured["factors"])
        except AdjQuotesError as e:
            logger.warning("RPE qfq bars skip %s: %s", code, e)
            return []
        except Exception as e:
            logger.warning("RPE qfq bars failed %s: %s", code, e)
            return []

    def load_sector_panel(
        self,
        member_codes: List[str],
        *,
        end_date: Optional[str] = None,
        lookback: Optional[int] = 250,
        adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量加载成分股 bars（逐只；lookback=None 表示拉全历史）。

        adjust=qfq 时对 OHLC 现算前复权（成交额/换手不变），保证板块基准与个股同口径。
        """
        out: Dict[str, List[Dict[str, Any]]] = {}
        for code in member_codes:
            bars = self.load_bars(
                code,
                end_date=end_date,
                limit=lookback,
                adjust=adjust,
                factor_source=factor_source,
                refresh_factor=refresh_factor,
            )
            if bars:
                out[_norm_code(code)] = bars
        return out

    def build_date_members(
        self, panel: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Tuple[float, float]]]:
        """{date: [(close, volume), ...]}"""
        date_map: Dict[str, List[Tuple[float, float]]] = {}
        for bars in panel.values():
            for b in bars:
                d = b["date"]
                date_map.setdefault(d, []).append((b["close"], b["volume"]))
        return date_map
