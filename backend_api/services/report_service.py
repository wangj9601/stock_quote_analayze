"""
报告服务 - 封装CSV报告生成器
"""

import os
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from backend_api.models import Watchlist, HistoricalQuotes, HistoricalQuotesHK, StockBasicInfo, StockBasicInfoHK

logger = logging.getLogger(__name__)


@dataclass
class ReportInfo:
    """报告信息"""
    stock_count: int  # 股票数量
    report_date: str  # 报告日期
    report_type: str  # 报告类型
    file_size: int  # 文件大小（字节）
    has_data: bool  # 是否有数据
    missing_data_stocks: List[str]  # 数据缺失的股票代码列表


@dataclass
class ReportResult:
    """报告生成结果"""
    success: bool  # 是否成功
    file_path: Optional[str]  # 报告文件路径
    report_info: Optional[ReportInfo]  # 报告信息
    error_message: Optional[str]  # 错误信息


class ReportService:
    """报告生成服务 - 封装CSV报告生成器"""
    
    def __init__(self, db: Session, report_dir: str = "reports/csv"):
        """
        初始化报告服务
        
        Args:
            db: 数据库会话
            report_dir: 报告文件保存目录
        """
        self.db = db
        self.report_dir = report_dir
        
        # 确保报告目录存在
        os.makedirs(self.report_dir, exist_ok=True)
        
        logger.info(f"ReportService 初始化完成，报告目录: {self.report_dir}")
    
    def get_user_watchlist(self, user_id: int, stock_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        获取用户自选股列表
        
        Args:
            user_id: 用户ID
            stock_codes: 指定股票代码列表，None表示获取全部自选股
            
        Returns:
            自选股列表，每项包含 stock_code, stock_name, market
        """
        try:
            query = self.db.query(Watchlist).filter(Watchlist.user_id == user_id)
            
            # 如果指定了股票代码，则过滤
            if stock_codes:
                query = query.filter(Watchlist.stock_code.in_(stock_codes))
            
            watchlist_items = query.all()
            
            if not watchlist_items:
                logger.warning(f"用户 {user_id} 没有自选股数据")
                return []
            
            # 构建返回结果，需要判断市场类型
            result = []
            for item in watchlist_items:
                # 判断是A股还是港股（港股代码通常以数字开头且长度为5位）
                market = self._determine_market(item.stock_code)
                result.append({
                    'stock_code': item.stock_code,
                    'stock_name': item.stock_name,
                    'market': market
                })
            
            logger.info(f"获取用户 {user_id} 自选股 {len(result)} 只")
            return result
            
        except Exception as e:
            logger.error(f"获取用户自选股失败: {str(e)}")
            return []
    
    def _determine_market(self, stock_code: str) -> str:
        """
        判断股票市场类型
        
        Args:
            stock_code: 股票代码
            
        Returns:
            'CN' 表示A股，'HK' 表示港股
        """
        # 港股代码通常是5位数字，如 "00700"
        # A股代码通常是6位数字，如 "000001", "600000"
        if len(stock_code) == 5 and stock_code.isdigit():
            return 'HK'
        return 'CN'
    
    def get_stock_history_data(
        self, 
        stock_code: str, 
        market: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取股票历史数据
        
        Args:
            stock_code: 股票代码
            market: 市场类型 ('CN' 或 'HK')
            days: 获取最近多少天的数据
            
        Returns:
            历史数据列表
        """
        try:
            if market == 'HK':
                # 查询港股历史数据
                query = text("""
                    SELECT 
                        date as trade_date,
                        open as open_price,
                        high as high_price,
                        low as low_price,
                        close as close_price,
                        volume,
                        amount,
                        change_amount,
                        change_percent
                    FROM historical_quotes_hk
                    WHERE code = :stock_code
                    ORDER BY date DESC
                    LIMIT :days
                """)
            else:
                # 查询A股历史数据
                query = text("""
                    SELECT 
                        date as trade_date,
                        open as open_price,
                        high as high_price,
                        low as low_price,
                        close as close_price,
                        volume,
                        amount,
                        change as change_amount,
                        change_percent
                    FROM historical_quotes
                    WHERE code = :stock_code
                    ORDER BY date DESC
                    LIMIT :days
                """)
            
            result = self.db.execute(query, {'stock_code': stock_code, 'days': days})
            rows = result.fetchall()
            
            # 转换为字典列表
            data = []
            for row in rows:
                data.append({
                    'trade_date': str(row.trade_date),
                    'open_price': float(row.open_price) if row.open_price else 0.0,
                    'high_price': float(row.high_price) if row.high_price else 0.0,
                    'low_price': float(row.low_price) if row.low_price else 0.0,
                    'close_price': float(row.close_price) if row.close_price else 0.0,
                    'volume': float(row.volume) if row.volume else 0.0,
                    'amount': float(row.amount) if row.amount else 0.0,
                    'change_amount': float(row.change_amount) if row.change_amount else 0.0,
                    'change_percent': float(row.change_percent) if row.change_percent else 0.0
                })
            
            if not data:
                logger.warning(f"股票 {stock_code} ({market}) 没有历史数据")
            
            return data
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} ({market}) 历史数据失败: {str(e)}")
            return []
    
    def get_stock_summary_data(self, stock_code: str, market: str) -> Dict[str, Any]:
        """
        获取股票汇总数据（最新一条数据）
        
        Args:
            stock_code: 股票代码
            market: 市场类型 ('CN' 或 'HK')
            
        Returns:
            汇总数据字典
        """
        try:
            if market == 'HK':
                # 查询港股最新数据
                query = text("""
                    SELECT 
                        h.name as stock_name,
                        h.close as current_price,
                        h.change_amount,
                        h.change_percent,
                        h.volume,
                        h.amount,
                        h.date as trade_date
                    FROM historical_quotes_hk h
                    WHERE h.code = :stock_code
                    ORDER BY h.date DESC
                    LIMIT 1
                """)
            else:
                # 查询A股最新数据
                query = text("""
                    SELECT 
                        h.name as stock_name,
                        h.close as current_price,
                        h.change as change_amount,
                        h.change_percent,
                        h.volume,
                        h.amount,
                        h.date as trade_date
                    FROM historical_quotes h
                    WHERE h.code = :stock_code
                    ORDER BY h.date DESC
                    LIMIT 1
                """)
            
            result = self.db.execute(query, {'stock_code': stock_code})
            row = result.fetchone()
            
            if not row:
                logger.warning(f"股票 {stock_code} ({market}) 没有汇总数据")
                return {}
            
            return {
                'stock_name': row.stock_name,
                'market': market,
                'current_price': float(row.current_price) if row.current_price else 0.0,
                'change_amount': float(row.change_amount) if row.change_amount else 0.0,
                'change_percent': float(row.change_percent) if row.change_percent else 0.0,
                'volume': float(row.volume) if row.volume else 0.0,
                'amount': float(row.amount) if row.amount else 0.0,
                'trade_date': str(row.trade_date)
            }
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} ({market}) 汇总数据失败: {str(e)}")
            return {}
    
    def generate_user_report(
        self, 
        user_id: int, 
        report_type: str,
        stock_codes: Optional[List[str]] = None
    ) -> ReportResult:
        """
        生成用户报告
        
        Args:
            user_id: 用户ID
            report_type: 报告类型 ('summary' 或 'detailed')
            stock_codes: 指定股票代码列表，None表示全部自选股
            
        Returns:
            ReportResult: 报告生成结果
        """
        try:
            # 成交量异动榜不依赖自选股，直接生成
            if report_type == 'volume_aberration':
                return self._generate_volume_aberration_report(user_id)

            # 获取用户自选股列表
            watchlist = self.get_user_watchlist(user_id, stock_codes)
            
            if not watchlist:
                logger.warning(f"用户 {user_id} 没有自选股，生成空报告")
                return ReportResult(
                    success=True,
                    file_path=None,
                    report_info=ReportInfo(
                        stock_count=0,
                        report_date=datetime.now().strftime("%Y-%m-%d"),
                        report_type=report_type,
                        file_size=0,
                        has_data=False,
                        missing_data_stocks=[]
                    ),
                    error_message="用户没有自选股"
                )
            
            # 根据报告类型生成报告
            if report_type == 'summary':
                return self._generate_summary_report(user_id, watchlist)
            elif report_type == 'detailed':
                return self._generate_detailed_report(user_id, watchlist)
            elif report_type == 'gms_daily':
                return self._generate_gms_report_for_user(user_id)
            else:
                return ReportResult(
                    success=False,
                    file_path=None,
                    report_info=None,
                    error_message=f"不支持的报告类型: {report_type}"
                )
                
        except Exception as e:
            logger.error(f"生成用户 {user_id} 报告失败: {str(e)}")
            return ReportResult(
                success=False,
                file_path=None,
                report_info=None,
                error_message=str(e)
            )
    
    def _generate_summary_report(
        self, 
        user_id: int, 
        watchlist: List[Dict[str, Any]]
    ) -> ReportResult:
        """
        生成汇总报告（仅包含最新数据）
        
        Args:
            user_id: 用户ID
            watchlist: 自选股列表
            
        Returns:
            ReportResult: 报告生成结果
        """
        summary_data = []
        missing_data_stocks = []
        
        for stock in watchlist:
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            market = stock['market']
            
            # 获取汇总数据
            summary = self.get_stock_summary_data(stock_code, market)
            
            if summary:
                summary_data.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '市场': market,
                    '当前价格': summary.get('current_price', 0),
                    '涨跌额': summary.get('change_amount', 0),
                    '涨跌幅(%)': summary.get('change_percent', 0),
                    '成交量': summary.get('volume', 0),
                    '成交额': summary.get('amount', 0),
                    '最新交易日': summary.get('trade_date', '')
                })
            else:
                # 数据缺失，添加占位行
                missing_data_stocks.append(stock_code)
                summary_data.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '市场': market,
                    '当前价格': '数据缺失',
                    '涨跌额': '数据缺失',
                    '涨跌幅(%)': '数据缺失',
                    '成交量': '数据缺失',
                    '成交额': '数据缺失',
                    '最新交易日': '数据缺失'
                })
        
        # 生成CSV文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_summary_{user_id}_{timestamp}.csv"
        filepath = os.path.join(self.report_dir, filename)
        
        df = pd.DataFrame(summary_data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        # 获取文件大小
        file_size = os.path.getsize(filepath)
        
        logger.info(f"生成汇总报告成功: {filepath}, 股票数: {len(watchlist)}, 数据缺失: {len(missing_data_stocks)}")
        
        return ReportResult(
            success=True,
            file_path=filepath,
            report_info=ReportInfo(
                stock_count=len(watchlist),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                report_type='summary',
                file_size=file_size,
                has_data=len(summary_data) > 0,
                missing_data_stocks=missing_data_stocks
            ),
            error_message=None
        )
    
    def _generate_detailed_report(
        self, 
        user_id: int, 
        watchlist: List[Dict[str, Any]],
        days: int = 30
    ) -> ReportResult:
        """
        生成详细报告（包含历史数据）
        
        Args:
            user_id: 用户ID
            watchlist: 自选股列表
            days: 获取最近多少天的数据
            
        Returns:
            ReportResult: 报告生成结果
        """
        all_data = []
        summary_data = []
        missing_data_stocks = []
        
        for stock in watchlist:
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            market = stock['market']
            
            # 获取历史数据
            history_data = self.get_stock_history_data(stock_code, market, days)
            
            # 获取汇总数据
            summary = self.get_stock_summary_data(stock_code, market)
            
            # 处理历史数据
            if history_data:
                for data in history_data:
                    all_data.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '市场': market,
                        '交易日期': data['trade_date'],
                        '开盘价': data['open_price'],
                        '最高价': data['high_price'],
                        '最低价': data['low_price'],
                        '收盘价': data['close_price'],
                        '成交量': data['volume'],
                        '成交额': data['amount'],
                        '涨跌额': data['change_amount'],
                        '涨跌幅(%)': data['change_percent']
                    })
            else:
                # 历史数据缺失
                missing_data_stocks.append(stock_code)
                all_data.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '市场': market,
                    '交易日期': '数据缺失',
                    '开盘价': '数据缺失',
                    '最高价': '数据缺失',
                    '最低价': '数据缺失',
                    '收盘价': '数据缺失',
                    '成交量': '数据缺失',
                    '成交额': '数据缺失',
                    '涨跌额': '数据缺失',
                    '涨跌幅(%)': '数据缺失'
                })
            
            # 处理汇总数据
            if summary:
                summary_data.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '市场': market,
                    '当前价格': summary.get('current_price', 0),
                    '涨跌额': summary.get('change_amount', 0),
                    '涨跌幅(%)': summary.get('change_percent', 0),
                    '成交量': summary.get('volume', 0),
                    '成交额': summary.get('amount', 0),
                    '最新交易日': summary.get('trade_date', '')
                })
            else:
                summary_data.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '市场': market,
                    '当前价格': '数据缺失',
                    '涨跌额': '数据缺失',
                    '涨跌幅(%)': '数据缺失',
                    '成交量': '数据缺失',
                    '成交额': '数据缺失',
                    '最新交易日': '数据缺失'
                })
        
        # 生成Excel文件，包含多个工作表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_report_{user_id}_{timestamp}.xlsx"
        filepath = os.path.join(self.report_dir, filename)
        
        # 创建Excel文件，包含多个工作表
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # 历史数据表
            if all_data:
                df_history = pd.DataFrame(all_data)
                df_history.to_excel(writer, sheet_name='历史数据', index=False)
            
            # 汇总数据表
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='股票汇总', index=False)
        
        # 获取文件大小
        file_size = os.path.getsize(filepath)
        
        logger.info(f"生成详细报告成功: {filepath}, 股票数: {len(watchlist)}, 数据缺失: {len(missing_data_stocks)}")
        
        return ReportResult(
            success=True,
            file_path=filepath,
            report_info=ReportInfo(
                stock_count=len(watchlist),
                report_date=datetime.now().strftime("%Y-%m-%d"),
                report_type='detailed',
                file_size=file_size,
                has_data=len(all_data) > 0,
                missing_data_stocks=missing_data_stocks
            ),
            error_message=None
        )

    def _generate_volume_aberration_report(self, user_id: int) -> ReportResult:
        """
        生成成交量异动榜报告（A股+港股放量榜全量），不依赖自选股。
        输出 Excel 两 sheet：A股放量榜、港股放量榜。
        """
        from backend_api.services.volume_aberration_service import get_volume_aberration_data

        result_cn, date_cn = get_volume_aberration_data(self.db, market="cn", date=None, order="desc")
        result_hk, date_hk = get_volume_aberration_data(self.db, market="hk", date=None, order="desc")

        report_date = date_cn or date_hk or datetime.now().strftime("%Y-%m-%d")
        total_count = len(result_cn) + len(result_hk)

        if total_count == 0:
            return ReportResult(
                success=True,
                file_path=None,
                report_info=ReportInfo(
                    stock_count=0,
                    report_date=report_date,
                    report_type="volume_aberration",
                    file_size=0,
                    has_data=False,
                    missing_data_stocks=[],
                ),
                error_message=None,
            )

        def to_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            rows = []
            for item in data:
                rows.append({
                    "排名": item.get("rank"),
                    "股票代码": "\u2060" + str(item.get("code", "")),
                    "股票名称": (item.get("name") or "").strip(),
                    "日期": item.get("date", ""),
                    "当日成交量": item.get("volume"),
                    "成交额": item.get("amount"),
                    "MAVOL5": item.get("mavol5"),
                    "MAVOL10": item.get("mavol10"),
                    "MAVOL20": item.get("mavol20"),
                    "量比(5)": item.get("ratio_5"),
                    "量比(20)": item.get("ratio_20"),
                    "涨跌幅(%)": item.get("change_percent"),
                    "收盘价": item.get("close"),
                    "换手率(%)": item.get("turnover_rate"),
                })
            return rows

        rows_cn = to_rows(result_cn)
        rows_hk = to_rows(result_hk)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"volume_aberration_{user_id}_{report_date.replace('-', '')}_{timestamp}.xlsx"
        filepath = os.path.join(self.report_dir, filename)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            if rows_cn:
                pd.DataFrame(rows_cn).to_excel(writer, sheet_name="A股放量榜", index=False)
            if rows_hk:
                pd.DataFrame(rows_hk).to_excel(writer, sheet_name="港股放量榜", index=False)

        file_size = os.path.getsize(filepath)
        logger.info("生成成交量异动榜报告成功: %s, A股=%s, 港股=%s", filepath, len(rows_cn), len(rows_hk))

        return ReportResult(
            success=True,
            file_path=filepath,
            report_info=ReportInfo(
                stock_count=total_count,
                report_date=report_date,
                report_type="volume_aberration",
                file_size=file_size,
                has_data=True,
                missing_data_stocks=[],
            ),
            error_message=None,
        )

    def _generate_gms_report_for_user(self, user_id: int) -> ReportResult:
        """
        生成该用户自选股范围内的 GMS 均值引力策略选股报告。
        """
        watchlist = self.get_user_watchlist(user_id)
        if not watchlist:
            return ReportResult(
                success=True,
                file_path=None,
                report_info=ReportInfo(
                    stock_count=0,
                    report_date=datetime.now().strftime("%Y-%m-%d"),
                    report_type="gms_daily",
                    file_size=0,
                    has_data=False,
                    missing_data_stocks=[],
                ),
                error_message="用户没有自选股",
            )
        # 自选股代码规范化：A 股 6 位，港股 5 位，与 GMS 指标表一致
        def _norm(s: str, market: str) -> str:
            s = str(s).strip()
            if not s:
                return s
            if market == "HK":
                return s.zfill(5) if s.isdigit() else s
            return s.zfill(6) if s.isdigit() else s

        stock_pool = []
        code_to_name = {}
        for s in watchlist:
            code = _norm(s["stock_code"], s["market"])
            if code:
                stock_pool.append(code)
                code_to_name[code] = s.get("stock_name") or ""

        if not stock_pool:
            return ReportResult(
                success=True,
                file_path=None,
                report_info=ReportInfo(
                    stock_count=0,
                    report_date=datetime.now().strftime("%Y-%m-%d"),
                    report_type="gms_daily",
                    file_size=0,
                    has_data=False,
                    missing_data_stocks=[],
                ),
                error_message="自选股代码无效",
            )

        try:
            from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface

            gms = GMSFrontendInterface(self.db)
            results = gms.get_selection_results(date=None, stock_pool=stock_pool, market="all")
        except Exception as e:
            logger.exception("GMS 选股失败: %s", e)
            return ReportResult(
                success=False,
                file_path=None,
                report_info=None,
                error_message=str(e),
            )

        if not results:
            report_date = datetime.now().strftime("%Y-%m-%d")
            return ReportResult(
                success=True,
                file_path=None,
                report_info=ReportInfo(
                    stock_count=0,
                    report_date=report_date,
                    report_type="gms_daily",
                    file_size=0,
                    has_data=False,
                    missing_data_stocks=[],
                ),
                error_message="当日自选股范围内无 GMS 选股结果",
            )

        # 报告日期：优先使用 GMS 结果中的 date 字段（YYYY-MM-DD），否则为今天
        report_date = str(results[0].get("date", "")[:10]) if results else datetime.now().strftime("%Y-%m-%d")

        codes = [r.get("code") or r.get("symbol") or "" for r in results]
        cn_codes = [c for c in codes if len(c) >= 6 and c.isdigit() and c[0] in "6039"]
        hk_codes = [c for c in codes if c not in cn_codes]

        # 与前端选股一致：从历史行情表取最近交易日收盘价、涨跌幅，用于「当前价格」「当前涨跌幅」
        hist_quotes_a: Dict[str, Any] = {}
        hist_quotes_hk: Dict[str, Any] = {}
        if cn_codes:
            latest_date_a = self.db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest_date_a:
                quotes_a = self.db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code.in_(cn_codes),
                    HistoricalQuotes.date == latest_date_a,
                ).all()
                hist_quotes_a = {q.code: q for q in quotes_a}
        if hk_codes:
            latest_date_hk = self.db.query(func.max(HistoricalQuotesHK.date)).scalar()
            if latest_date_hk:
                latest_hk_str = str(latest_date_hk).strip()[:10]
                quotes_hk = self.db.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code.in_(hk_codes),
                    HistoricalQuotesHK.date == latest_hk_str,
                ).all()
                hist_quotes_hk = {q.code: q for q in quotes_hk}

        # 补全股票名称：先用自选股 code_to_name，缺失时查 StockBasicInfo / StockBasicInfoHK（与前端 API 一致）
        for code in codes:
            if code_to_name.get(code):
                continue
            if code in hk_codes:
                info = self.db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
                if info and info.name:
                    code_to_name[code] = info.name
            else:
                info = self.db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
                if not info and code.startswith("SZ"):
                    info = self.db.query(StockBasicInfo).filter(StockBasicInfo.code == code[2:]).first()
                if not info and code.startswith("SH"):
                    info = self.db.query(StockBasicInfo).filter(StockBasicInfo.code == code[2:]).first()
                if info and info.name:
                    code_to_name[code] = info.name
            if not code_to_name.get(code):
                code_to_name[code] = f"股票{code}"

        # CSV 表头与内容与前端「选股 - GMS均值引力动量」导出一致（见 frontend/js/screening.js strategy===gms）
        def _fmt_pct(val, decimals=2):
            if val is None:
                return ""
            try:
                return f"{float(val) * 100:.{decimals}f}%"
            except (TypeError, ValueError):
                return ""

        def _fmt_score_detail(sd):
            """与前端 screening.js GMS 导出格式一致：总分 蓄势(引力+平衡+量缩)等级 动量(推力+支撑+攻击)等级"""
            if not sd or not isinstance(sd, dict):
                return ""
            def _n(v):
                if v is None:
                    return "--"
                try:
                    return f"{float(v):.1f}"
                except (TypeError, ValueError):
                    return "--"
            acc = sd.get("score_accumulation")
            acc_part = f"蓄势{_n(acc)}(引力{_n(sd.get('score_acc_fz'))}+平衡{_n(sd.get('score_acc_balance'))}+量缩{_n(sd.get('score_acc_volume'))}){sd.get('accumulation_grade') or ''}" if acc is not None else "蓄势--"
            mom = sd.get("score_momentum")
            mom_part = f"动量{_n(mom)}(推力{_n(sd.get('score_mom_ratio_d1'))}+支撑{_n(sd.get('score_mom_deviation'))}+攻击{_n(sd.get('score_mom_volume'))}){sd.get('momentum_grade') or ''}" if mom is not None else "动量--"
            return f"总分{_n(sd.get('score_total'))} {acc_part} {mom_part}"

        rows = []
        for r in results:
            code = r.get("code") or r.get("symbol") or ""
            name = code_to_name.get(code, "")
            st = r.get("score_total")
            sig = (float(st) / 100.0) if st is not None and st > 0 else (r.get("signal_strength") or 0.0)
            buy_type = r.get("buy_type") or ""
            delta = r.get("delta")
            d = r.get("d")
            ratio_d20 = r.get("ratio_d20")
            ratio_d1 = r.get("ratio_d1")
            fz_ratio = r.get("fz_ratio")
            rising_days = r.get("rising_days")
            falling_days = r.get("falling_days")
            ratio_relative = (delta / d) if (delta is not None and d is not None and d != 0) else None

            quote = hist_quotes_a.get(code) or hist_quotes_hk.get(code)
            current_price = d or 0
            current_change_percent = None
            if quote and hasattr(quote, "close") and quote.close is not None:
                current_price = float(quote.close)
            if quote and hasattr(quote, "change_percent") and quote.change_percent is not None:
                current_change_percent = float(quote.change_percent)

            score_detail_str = _fmt_score_detail(r.get("score_detail"))

            rows.append({
                "股票代码": "\u2060" + str(code),  # 零宽字符前缀使 Excel 整列统一按文本显示，左对齐且保留前导零
                    "股票名称": name,
                "信号强度": f"{sig * 100:.1f}%",
                "买点类型": buy_type,
                "当前价格": f"{current_price:.2f}" if current_price is not None else "",
                "Δ (20日位移)": f"{delta:.4f}" if delta is not None else "",
                "F (下跌天)": falling_days if falling_days is not None else "",
                "Z (上涨天)": rising_days if rising_days is not None else "",
                "d (20日均价)": f"{d:.2f}" if d is not None else "",
                "Δ/d (位移/均价)": _fmt_pct(ratio_relative),
                "Δ/d₂₀": _fmt_pct(ratio_d20),
                "Δ/d₁": _fmt_pct(ratio_d1),
                "F/Z": f"{fz_ratio:.2f}" if fz_ratio is not None else "",
                "当前涨跌幅": f"{current_change_percent:.2f}%" if current_change_percent is not None else "0%",
                "得分明细": score_detail_str,
            })

        filename = f"gms_{user_id}_{report_date.replace('-', '')}.csv"
        filepath = os.path.join(self.report_dir, filename)
        df = pd.DataFrame(rows)
        if "股票代码" in df.columns:
            df["股票代码"] = df["股票代码"].astype(str)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        file_size = os.path.getsize(filepath)
        logger.info("生成 GMS 自选股报告成功: %s, 选股数: %s", filepath, len(rows))
        return ReportResult(
            success=True,
            file_path=filepath,
            report_info=ReportInfo(
                stock_count=len(rows),
                report_date=report_date,
                report_type="gms_daily",
                file_size=file_size,
                has_data=True,
                missing_data_stocks=[],
            ),
            error_message=None,
        )

    def get_report_info(self, report_path: str) -> Optional[ReportInfo]:
        """
        获取报告信息
        
        Args:
            report_path: 报告文件路径
            
        Returns:
            ReportInfo: 报告信息，如果文件不存在返回None
        """
        try:
            if not os.path.exists(report_path):
                logger.error(f"报告文件不存在: {report_path}")
                return None
            
            # 获取文件大小
            file_size = os.path.getsize(report_path)
            
            # 从文件名解析报告类型和日期
            filename = os.path.basename(report_path)
            if 'volume_aberration' in filename:
                report_type = 'volume_aberration'
            elif 'gms_' in filename:
                report_type = 'gms_daily'
            elif 'summary' in filename:
                report_type = 'summary'
            else:
                report_type = 'detailed'
            report_date = datetime.now().strftime("%Y-%m-%d")
            
            # 读取文件获取股票数量
            stock_count = 0
            has_data = False
            
            if report_path.endswith('.csv'):
                df = pd.read_csv(report_path, encoding='utf-8-sig')
                stock_count = len(df)
                has_data = stock_count > 0
            elif report_path.endswith('.xlsx'):
                if report_type == 'volume_aberration':
                    try:
                        df_cn = pd.read_excel(report_path, sheet_name='A股放量榜')
                        stock_count += len(df_cn)
                    except Exception:
                        pass
                    try:
                        df_hk = pd.read_excel(report_path, sheet_name='港股放量榜')
                        stock_count += len(df_hk)
                    except Exception:
                        pass
                    has_data = stock_count > 0
                else:
                    df = pd.read_excel(report_path, sheet_name='股票汇总')
                    stock_count = len(df)
                    has_data = stock_count > 0
            
            return ReportInfo(
                stock_count=stock_count,
                report_date=report_date,
                report_type=report_type,
                file_size=file_size,
                has_data=has_data,
                missing_data_stocks=[]  # 从文件中无法获取，返回空列表
            )
            
        except Exception as e:
            logger.error(f"获取报告信息失败: {str(e)}")
            return None
