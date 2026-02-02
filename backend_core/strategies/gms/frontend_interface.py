"""
GMS 前端选股接口
供 API 调用的选股入口
"""

import logging
from typing import List, Optional
from datetime import datetime

from .data_loader import GMSDataLoader
from .strategy_engine import GMSStrategyEngine
from .config import GMSConfigManager

logger = logging.getLogger(__name__)


class GMSFrontendInterface:
    """GMS 选股前端接口"""

    def __init__(self, db, config: Optional[dict] = None):
        self.db = db
        self.config = config or GMSConfigManager().get_config()
        self.min_score = 0
        self.max_results = 10000

    def set_selection_config(
        self,
        min_score: float = 0,
        max_results: int = 10000,
    ):
        self.min_score = min_score
        self.max_results = max_results

    def get_selection_results(
        self,
        date: Optional[str] = None,
        stock_pool: Optional[List[str]] = None,
        market: str = "all",
    ) -> List[dict]:
        """
        获取选股结果

        Args:
            date: 目标日期 YYYY-MM-DD
            stock_pool: 股票代码列表，None 时从指标表获取
            market: cn / hk / all

        Returns:
            选股结果列表
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        date = str(date).strip()[:10]

        if stock_pool is None:
            stock_pool = self._get_stock_pool(date, market)
        else:
            stock_pool = list(dict.fromkeys(stock_pool))

        if not stock_pool:
            return []

        loader = GMSDataLoader(self.db)
        engine = GMSStrategyEngine(loader, self.config)
        market_val = "CN" if market == "cn" else "HK" if market == "hk" else "all"
        results = engine.screen(
            codes=stock_pool,
            date=date,
            market=market_val,
            config=self.config,
            min_score=self.min_score,
            max_results=self.max_results,
        )
        return results

    def _get_stock_pool(self, date: str, market: str) -> List[str]:
        """
        按数据来源获取股票池：
        - cn（全部A股）：A 股基本信息表 stock_basic_info 全部代码
        - hk（全部港股）：港股基本信息表 stock_basic_info_hk 全部代码
        - all：上述两表合并（本接口由 API 在 scope=cn/hk 时分别传 market，此处 all 仅作备用）
        """
        try:
            from backend_api.models import StockBasicInfo, StockBasicInfoHK

            if market == "cn":
                rows = self.db.query(StockBasicInfo.code).all()
                codes = [str(r[0]).zfill(6) if isinstance(r[0], int) else str(r[0]) for r in rows if r[0] is not None]
                logger.info(f"GMS 股票池(全部A股): {len(codes)} 只")
            elif market == "hk":
                rows = self.db.query(StockBasicInfoHK.code).all()
                # 港股代码统一为 5 位补零（与 mean_frequency_resonance_indicators 表一致）
                codes = []
                for r in rows:
                    if r[0] is None:
                        continue
                    c = str(r[0]).strip()
                    if c.isdigit():
                        codes.append(c.zfill(5))
                    else:
                        codes.append(c)
                logger.info(f"GMS 股票池(全部港股): {len(codes)} 只")
            elif market == "all":
                cn_rows = self.db.query(StockBasicInfo.code).all()
                cn_codes = [str(r[0]).zfill(6) if isinstance(r[0], int) else str(r[0]) for r in cn_rows if r[0] is not None]
                hk_rows = self.db.query(StockBasicInfoHK.code).all()
                hk_codes = []
                for r in hk_rows:
                    if r[0] is None:
                        continue
                    c = str(r[0]).strip()
                    hk_codes.append(c.zfill(5) if c.isdigit() else c)
                codes = cn_codes + hk_codes
                logger.info(f"GMS 股票池(全部A+港股): {len(codes)} 只")
            else:
                return []

            return codes
        except Exception as e:
            logger.error(f"GMS 获取股票池失败: {e}", exc_info=True)
            return []
