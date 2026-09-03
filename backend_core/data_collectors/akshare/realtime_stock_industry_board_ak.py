import akshare as ak
import pandas as pd
import traceback
from datetime import datetime
import sys
from backend_core.config.config import DATA_COLLECTORS
from backend_core.database.db import SessionLocal
from backend_core.data_collectors.akshare.industry_board_normalize import (
    enrich_leading_stock_codes,
    industry_board_to_english_df,
    normalize_ths_industry_df,
)
from backend_api.utils.bk_board_code import (
    allocate_bk_board_code,
    is_valid_bk_board_code,
    normalize_bk_board_code,
    normalize_industry_board_code,
)
from backend_api.utils.board_code_source import (
    SYNC_BOARD_CODE_SOURCE,
    sql_board_code_source_preserve_on_conflict,
)

try:
    from backend_api.utils.industry_board_query import lookup_leading_code_from_constituents
except ImportError:
    lookup_leading_code_from_constituents = None  # type: ignore
from sqlalchemy import text

class RealtimeStockIndustryBoardCollector:
    def __init__(self):
        self.db_file = DATA_COLLECTORS['akshare']['db_file']
        self.table_name = 'industry_board_realtime_quotes'
        self.log_table = 'realtime_collect_operation_logs'
        self._init_db()

    def _init_db(self):
        session = SessionLocal()
        try:
            # 创建行业板块基本信息表
            print("Creating industry_board_basic_info...")
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS industry_board_basic_info (
                    board_code TEXT PRIMARY KEY,
                    board_name TEXT,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
                )
            '''))
            session.commit()
            session.execute(text(
                "ALTER TABLE industry_board_basic_info ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            session.commit()
            print("Created industry_board_basic_info.")
        except Exception as e:
            print(f"Error creating industry_board_basic_info: {e}")
            session.rollback()

        try:
            # 创建行业板块实时行情表
            print(f"Creating {self.table_name}...")
            session.execute(text(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    board_code TEXT,
                    board_name TEXT,
                    latest_price REAL,
                    change_amount REAL,
                    change_percent REAL,
                    total_market_value REAL,
                    volume REAL,
                    amount REAL,
                    turnover_rate REAL,
                    up_count INTEGER,
                    down_count INTEGER,
                    leading_stock_name TEXT,
                    leading_stock_change_percent REAL,
                    leading_stock_code TEXT,
                    update_time TIMESTAMP,
                    PRIMARY KEY (board_code, update_time)
                )
            '''))
            session.commit()
            # 兼容旧表结构：补齐历史缺失字段
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS up_count INTEGER"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS down_count INTEGER"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_name TEXT"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_change_percent REAL"))
            session.execute(text(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS leading_stock_code TEXT"))
            session.commit()
            print(f"Created {self.table_name}.")
        except Exception as e:
            print(f"Error creating {self.table_name}: {e}")
            session.rollback()

        try:
            # 创建日志表
            print(f"Creating {self.log_table}...")
            session.execute(text(f'''
                CREATE TABLE IF NOT EXISTS {self.log_table} (
                    id SERIAL PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_desc TEXT NOT NULL,
                    affected_rows INTEGER,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            session.commit()
            print(f"Created {self.log_table}.")
        except Exception as e:
            print(f"Error creating {self.log_table}: {e}")
            session.rollback()
        finally:
            session.close()

    def fetch_data(self):
        # 调用akshare接口
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            print(f"[采集] 东方财富接口调用失败: {e}，尝试调用同花顺接口...")
            try:
                df = ak.stock_board_industry_summary_ths()
                return normalize_ths_industry_df(df)
            except Exception as e2:
                print(f"[采集] 同花顺接口调用也失败: {e2}")
                raise e # 抛出原始异常或新异常

    def _load_stock_name_code_map(self, session) -> dict:
        try:
            rows = session.execute(
                text(
                    "SELECT code, name FROM stock_basic_info "
                    "WHERE name IS NOT NULL AND code IS NOT NULL"
                )
            ).fetchall()
            return {str(name).strip(): str(code).strip() for code, name in rows if name and code}
        except Exception as e:
            print(f"[采集] 读取 stock_basic_info 失败，跳过领涨股代码补全: {e}")
            return {}

    def _clear_stale_avg_as_index(self, session) -> int:
        """清除误当作指数入库的同花顺「均价」残留（<100 且无涨跌额）。"""
        try:
            res = session.execute(
                text(
                    f"""
                    UPDATE {self.table_name}
                    SET latest_price = NULL
                    WHERE latest_price IS NOT NULL
                      AND latest_price < 100
                      AND change_amount IS NULL
                    """
                )
            )
            session.commit()
            n = int(res.rowcount or 0)
            if n:
                print(f"[采集] 已清除均价冒充指数的 latest_price 行数: {n}")
            return n
        except Exception as e:
            print(f"[采集] 清除均价残留失败: {e}")
            session.rollback()
            return 0

    def save_to_db(self, df):
        session = SessionLocal()
        try:
            self._clear_stale_avg_as_index(session)
            now = datetime.now().replace(microsecond=0)
            df = industry_board_to_english_df(df)
            if df.empty:
                return False, "归一化后数据为空"
            name_code_map = self._load_stock_name_code_map(session)
            df = enrich_leading_stock_codes(df, name_code_map)
            if lookup_leading_code_from_constituents and "leading_stock_name" in df.columns:
                if "leading_stock_code" not in df.columns:
                    df["leading_stock_code"] = None
                for idx, row in df.iterrows():
                    existing = row.get("leading_stock_code")
                    if existing is not None and not pd.isna(existing) and str(existing).strip():
                        continue
                    bcode = row.get("board_code")
                    lname = row.get("leading_stock_name")
                    if pd.isna(bcode) or pd.isna(lname):
                        continue
                    code = lookup_leading_code_from_constituents(
                        session, str(bcode).strip(), str(lname).strip()
                    )
                    if code:
                        df.at[idx, "leading_stock_code"] = code
            df["update_time"] = now
            
            # 更新行业板块基本信息表
            # 使用 executemany 优化性能? 或者简单的循环
            # 这里为了简单和处理冲突，使用循环
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS concept_board_basic_info (
                    board_code VARCHAR(20) PRIMARY KEY,
                    board_name VARCHAR(100),
                    create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
            '''))
            session.commit()

            basic_info_count = 0
            em_to_stored: dict[str, str] = {}
            # 新建板标东财；已有板保留原 board_code_source（禁止把同花顺改成东财）
            _src_preserve = sql_board_code_source_preserve_on_conflict("industry_board_basic_info")
            for _, row in df.iterrows():
                if pd.isna(row.get('board_code')) or row.get('board_code') == '':
                    print(f"Skipping row with empty board_code: {row.get('board_name')}")
                    continue

                em_code = str(row['board_code']).strip()
                board_name = row.get('board_name')
                name_key = str(board_name).strip() if board_name is not None and not pd.isna(board_name) else ""
                try:
                    existing = None
                    if name_key:
                        # 仅复用东财/空来源同名板；同花顺等同名板不参与匹配，避免被东财同步改写
                        existing = session.execute(
                            text(
                                """
                                SELECT board_code FROM industry_board_basic_info
                                WHERE TRIM(board_name) = :name
                                  AND COALESCE(NULLIF(TRIM(board_code_source), ''), 'eastmoney')
                                      = 'eastmoney'
                                LIMIT 1
                                """
                            ),
                            {"name": name_key},
                        ).scalar()
                    if existing:
                        stored_code = normalize_industry_board_code(existing) or str(existing).strip()
                    elif em_code in em_to_stored:
                        stored_code = em_to_stored[em_code]
                    elif name_key and normalize_industry_board_code(name_key):
                        stored_code = normalize_industry_board_code(name_key)
                    else:
                        preferred = em_code if is_valid_bk_board_code(em_code) else None
                        stored_code = allocate_bk_board_code(session, preferred=preferred)
                    em_to_stored[em_code] = stored_code
                    session.execute(text(f'''
                        INSERT INTO industry_board_basic_info (board_code, board_name, create_date, board_code_source)
                        VALUES (:board_code, :board_name, :create_date, :board_code_source)
                        ON CONFLICT (board_code) DO UPDATE SET
                            board_name = EXCLUDED.board_name,
                            {_src_preserve}
                    '''), {
                        'board_code': stored_code,
                        'board_name': board_name,
                        'create_date': now,
                        'board_code_source': SYNC_BOARD_CODE_SOURCE,
                    })
                    basic_info_count += 1
                except Exception as e:
                    print(f"Error inserting basic info for {row.get('board_code')}: {e}")

            print(f"Inserted/updated {basic_info_count} industry basic_info")
            session.commit()
            
            columns = list(df.columns)
            # 仅 UPSERT：保留历史实时行情，不整表清空
            for _, row in df.iterrows():
                if pd.isna(row.get("board_code")) or str(row.get("board_code", "")).strip() == "":
                    continue
                em_code = str(row.get("board_code")).strip()
                stored_code = em_to_stored.get(em_code)
                if not stored_code:
                    continue
                value_dict = {}
                for col in columns:
                    v = row[col]
                    if hasattr(v, 'item'):
                        v = v.item()
                    if pd.isna(v):
                        v = None
                    if str(type(v)).endswith("Timestamp'>"):
                        v = v.to_pydatetime().isoformat()
                    if col == 'update_time' and not isinstance(v, str):
                        v = v.isoformat()
                    value_dict[col] = v
                value_dict["board_code"] = stored_code
                placeholders = ','.join([f':{col}' for col in columns])
                col_names = ','.join([f'"{col}"' for col in columns])
                # upsert：有新指数则写入；无新指数时仅保留「像指数」的旧值，
                # 绝不继续保留同花顺均价残留（<100 且无涨跌额）。
                update_parts = []
                for col in columns:
                    if col in ('board_code', 'update_time'):
                        continue
                    if col == 'latest_price':
                        update_parts.append(
                            f'"{col}"=CASE '
                            f'WHEN EXCLUDED."{col}" IS NOT NULL THEN EXCLUDED."{col}" '
                            f'WHEN {self.table_name}."{col}" IS NOT NULL AND ('
                            f'{self.table_name}."{col}" >= 100 OR '
                            f'{self.table_name}.change_amount IS NOT NULL'
                            f') THEN {self.table_name}."{col}" '
                            f'ELSE NULL END'
                        )
                    else:
                        update_parts.append(f'"{col}"=EXCLUDED."{col}"')
                update_set = ','.join(update_parts)
                sql = f'INSERT INTO {self.table_name} ({col_names}) VALUES ({placeholders}) ON CONFLICT (board_code, update_time) DO UPDATE SET {update_set}'
                session.execute(text(sql), value_dict)
            # 东财「最新价」= 板块指数点位。优先按代码映射镜像到同花顺板，其次按同名镜像。
            # 仅当本批写入含有效 latest_price（指数）时镜像，避免同花顺均价兜底污染。
            try:
                from backend_api.utils.industry_board_code_map import (
                    ensure_industry_board_code_map_table,
                    load_active_code_maps,
                )

                ensure_industry_board_code_map_table(session)
                ths_to_em, em_to_ths = load_active_code_maps(session, board_kind="industry")
                # 采集后轻量补映射：同名精确（不覆盖手工）
                try:
                    from backend_api.utils.industry_board_code_map import rebuild_name_exact_maps

                    rebuild_name_exact_maps(session, board_kind="industry", replace_auto=False)
                    ths_to_em, em_to_ths = load_active_code_maps(session, board_kind="industry")
                except Exception as rebuild_err:
                    print(f"[采集] 代码映射自动补全跳过: {rebuild_err}")

                if em_to_ths:
                    # 按映射表：东财码 → 同花顺码
                    session.execute(
                        text(
                            f"""
                            INSERT INTO {self.table_name} (
                                board_code, board_name, latest_price, change_amount,
                                change_percent, total_market_value, volume, amount,
                                turnover_rate, up_count, down_count,
                                leading_stock_name, leading_stock_code,
                                leading_stock_change_percent, update_time
                            )
                            SELECT
                                m.ths_board_code,
                                COALESCE(t.board_name, q.board_name),
                                q.latest_price, q.change_amount,
                                q.change_percent, q.total_market_value, q.volume, q.amount,
                                q.turnover_rate, q.up_count, q.down_count,
                                q.leading_stock_name, q.leading_stock_code,
                                q.leading_stock_change_percent, q.update_time
                            FROM {self.table_name} q
                            INNER JOIN industry_board_code_map m
                              ON m.em_board_code = q.board_code
                             AND m.board_kind = 'industry'
                             AND m.is_active IS TRUE
                            LEFT JOIN industry_board_basic_info t
                              ON t.board_code = m.ths_board_code
                            WHERE q.update_time = :now
                              AND q.latest_price IS NOT NULL
                              AND m.ths_board_code <> q.board_code
                            ON CONFLICT (board_code, update_time) DO UPDATE SET
                                board_name = EXCLUDED.board_name,
                                latest_price = EXCLUDED.latest_price,
                                change_amount = EXCLUDED.change_amount,
                                change_percent = EXCLUDED.change_percent,
                                total_market_value = EXCLUDED.total_market_value,
                                volume = EXCLUDED.volume,
                                amount = EXCLUDED.amount,
                                turnover_rate = EXCLUDED.turnover_rate,
                                up_count = EXCLUDED.up_count,
                                down_count = EXCLUDED.down_count,
                                leading_stock_name = EXCLUDED.leading_stock_name,
                                leading_stock_code = EXCLUDED.leading_stock_code,
                                leading_stock_change_percent = EXCLUDED.leading_stock_change_percent
                            """
                        ),
                        {"now": now},
                    )

                # 名称兜底：未映射到的同花顺板仍按同名桥接
                session.execute(
                    text(
                        f"""
                        INSERT INTO {self.table_name} (
                            board_code, board_name, latest_price, change_amount,
                            change_percent, total_market_value, volume, amount,
                            turnover_rate, up_count, down_count,
                            leading_stock_name, leading_stock_code,
                            leading_stock_change_percent, update_time
                        )
                        SELECT
                            t.board_code, t.board_name, q.latest_price, q.change_amount,
                            q.change_percent, q.total_market_value, q.volume, q.amount,
                            q.turnover_rate, q.up_count, q.down_count,
                            q.leading_stock_name, q.leading_stock_code,
                            q.leading_stock_change_percent, q.update_time
                        FROM industry_board_basic_info t
                        INNER JOIN {self.table_name} q
                          ON TRIM(q.board_name) = TRIM(t.board_name)
                         AND q.update_time = :now
                         AND q.latest_price IS NOT NULL
                        WHERE COALESCE(NULLIF(TRIM(t.board_code_source), ''), 'eastmoney')
                              = 'tonghuashun'
                          AND q.board_code <> t.board_code
                          AND NOT EXISTS (
                              SELECT 1 FROM industry_board_code_map m
                              WHERE m.board_kind = 'industry'
                                AND m.is_active IS TRUE
                                AND m.ths_board_code = t.board_code
                          )
                        ON CONFLICT (board_code, update_time) DO UPDATE SET
                            board_name = EXCLUDED.board_name,
                            latest_price = EXCLUDED.latest_price,
                            change_amount = EXCLUDED.change_amount,
                            change_percent = EXCLUDED.change_percent,
                            total_market_value = EXCLUDED.total_market_value,
                            volume = EXCLUDED.volume,
                            amount = EXCLUDED.amount,
                            turnover_rate = EXCLUDED.turnover_rate,
                            up_count = EXCLUDED.up_count,
                            down_count = EXCLUDED.down_count,
                            leading_stock_name = EXCLUDED.leading_stock_name,
                            leading_stock_code = EXCLUDED.leading_stock_code,
                            leading_stock_change_percent = EXCLUDED.leading_stock_change_percent
                        """
                    ),
                    {"now": now},
                )
            except Exception as mirror_err:
                print(f"[采集] 同花顺板指数镜像跳过: {mirror_err}")
            session.commit()
            return True, None
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def write_log(self, operation_type, operation_desc, affected_rows, status, error_message=None):
        session = SessionLocal()
        try:
            now = datetime.now().replace(microsecond=0)
            session.execute(text(f"INSERT INTO {self.log_table} (operation_type, operation_desc, affected_rows, status, error_message, created_at) VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)"),
                           {'operation_type': operation_type, 'operation_desc': operation_desc, 'affected_rows': affected_rows, 'status': status, 'error_message': error_message or '', 'created_at': now})
            session.commit()
        except Exception as e:
            print(f"[LOG ERROR] {e}")
        finally:
            session.close()

    def _log_slope_refresh_result(
        self,
        *,
        operation_type: str,
        operation_desc: str,
        written: int,
        total: int,
        error_message: str = None,
    ):
        """斜率 refresh 结果写入 realtime_collect_operation_logs（必落库，便于核对）。"""
        if error_message:
            status = "fail"
            err = error_message
        elif total == 0:
            status = "success"
            err = "无同花顺板可算（basic_info 过滤后为空）"
        elif written <= 0:
            status = "fail"
            err = f"尝试 {total} 板均无有效斜率写入"
        elif written < total:
            status = "partial"
            err = f"写入 {written}/{total}"
        else:
            status = "success"
            err = None
        self.write_log(
            operation_type=operation_type,
            operation_desc=operation_desc,
            affected_rows=written,
            status=status,
            error_message=err,
        )

    def _refresh_sector_slopes_after_quotes(self):
        """行情入库成功后：同花顺行业板 + 概念板全成分斜率入库；其它来源不扫。失败只记日志。

        调度说明：仓库无概念板实时行情采集器；概念板斜率与行业板共用本任务挂载点
        （``RealtimeStockIndustryBoardCollector.run`` 行情成功后对称刷新），
        保证日更节奏一致。成分同步见 ``ConceptBoardConstituentsCollector``（不单独挂斜率）。

        可观测性：开始/成功/失败均写入 ``realtime_collect_operation_logs``
        （operation_type=industry_board_sector_slope / concept_board_sector_slope）。
        """
        from backend_core.board_metrics.sector_slope_store import (
            ALLOWED_SLOPE_BOARD_CODE_SOURCE,
            refresh_board_sector_slopes,
        )

        # 先落 start，避免长耗时中途被杀时完全无痕迹
        self.write_log(
            operation_type="industry_board_sector_slope",
            operation_desc="开始：同花顺行业/概念板斜率入库（行情采集挂载）",
            affected_rows=0,
            status="start",
            error_message=None,
        )

        session = SessionLocal()
        try:
            try:
                written, total = refresh_board_sector_slopes(
                    session,
                    board_kind="industry",
                    board_code_source=ALLOWED_SLOPE_BOARD_CODE_SOURCE,
                    member_limit=None,
                    commit=True,
                )
                print(f"[采集] 同花顺行业板斜率入库完成: written={written}/{total}")
                self._log_slope_refresh_result(
                    operation_type="industry_board_sector_slope",
                    operation_desc="同花顺行业板成分量权斜率计算入库",
                    written=written,
                    total=total,
                )
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[采集] 行业板斜率入库失败（不影响行情）: {e}\n{tb}")
                self._log_slope_refresh_result(
                    operation_type="industry_board_sector_slope",
                    operation_desc="同花顺行业板成分量权斜率计算入库",
                    written=0,
                    total=0,
                    error_message=str(e) + "\n" + tb,
                )
                try:
                    session.rollback()
                except Exception:
                    pass

            # 概念板无 realtime collector：与行业板对称刷新同花顺概念斜率
            try:
                c_written, c_total = refresh_board_sector_slopes(
                    session,
                    board_kind="concept",
                    board_code_source=ALLOWED_SLOPE_BOARD_CODE_SOURCE,
                    member_limit=None,
                    commit=True,
                )
                print(f"[采集] 同花顺概念板斜率入库完成: written={c_written}/{c_total}")
                self._log_slope_refresh_result(
                    operation_type="concept_board_sector_slope",
                    operation_desc="同花顺概念板成分量权斜率计算入库（挂载于行业板实时采集后）",
                    written=c_written,
                    total=c_total,
                )
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[采集] 概念板斜率入库失败（不影响行情）: {e}\n{tb}")
                self._log_slope_refresh_result(
                    operation_type="concept_board_sector_slope",
                    operation_desc="同花顺概念板成分量权斜率计算入库（挂载于行业板实时采集后）",
                    written=0,
                    total=0,
                    error_message=str(e) + "\n" + tb,
                )
        finally:
            session.close()

    def run(self):
        try:
            print("[采集] 开始采集行业板块实时行情...")
            df = self.fetch_data()
            print(f"[采集] 获取到{len(df)}条数据")
            ok, err = self.save_to_db(df)
            if ok:
                print("[采集] 数据写入成功")
                self.write_log(
                    operation_type="industry_board_realtime",
                    operation_desc="采集行业板块实时行情",
                    affected_rows=len(df),
                    status="success",
                    error_message=None
                )
                # 斜率依赖成分日线，与实时涨跌分离；失败不拖垮整次采集
                self._refresh_sector_slopes_after_quotes()
            else:
                print(f"[采集] 数据写入失败: {err}")
                self.write_log(
                    operation_type="industry_board_realtime",
                    operation_desc="采集行业板块实时行情",
                    affected_rows=0,
                    status="fail",
                    error_message=err
                )
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[采集] 采集异常: {e}\n{tb}")
            self.write_log(
                operation_type="industry_board_realtime",
                operation_desc="采集行业板块实时行情",
                affected_rows=0,
                status="fail",
                error_message=str(e) + "\n" + tb
            )

if __name__ == '__main__':
    collector = RealtimeStockIndustryBoardCollector()
    collector.run()
