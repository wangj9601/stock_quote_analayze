#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
30日涨跌幅计算脚本
支持手动触发和批量计算历史行情数据的30日涨跌幅
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal  # noqa: E402
from backend_core.data_collectors.tushare.thirty_day_change_calculator import (  # noqa: E402
    ThirtyDayChangeCalculator,
)

# 配置日志（.env 中 LOG_TO_FILE=true 时才写文件）
from backend_core.logging_utils import should_log_to_file
_handlers = [logging.StreamHandler()]
if should_log_to_file():
    _handlers.append(logging.FileHandler("thirty_day_change_calculation.log", encoding="utf-8"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=_handlers)
logger = logging.getLogger(__name__)


def calculate_for_date(target_date: str) -> bool:
    """为指定日期计算30日涨跌幅"""
    try:
        logger.info("开始为日期 %s 计算30日涨跌幅", target_date)

        session = SessionLocal()
        calculator = ThirtyDayChangeCalculator(session)

        result = calculator.calculate_for_date(target_date)

        logger.info("日期 %s 的30日涨跌幅计算完成:", target_date)
        logger.info("  总计股票: %s", result["total"])
        logger.info("  成功计算: %s", result["success"])
        logger.info("  失败计算: %s", result["failed"])

        if result["failed"] > 0:
            logger.warning("部分股票计算失败:")
            for detail in result["details"]:
                logger.warning("  - %s", detail)

        session.close()
        return result["failed"] == 0

    except Exception as e:
        logger.error("为日期 %s 计算30日涨跌幅失败: %s", target_date, e)
        return False


def calculate_for_date_range(start_date: str, end_date: str) -> bool:
    """为指定日期范围计算30日涨跌幅"""
    try:
        logger.info("开始为日期范围 %s 到 %s 计算30日涨跌幅", start_date, end_date)

        session = SessionLocal()
        calculator = ThirtyDayChangeCalculator(session)

        result = calculator.calculate_batch_for_date_range(start_date, end_date)

        logger.info("日期范围 %s 到 %s 的30日涨跌幅计算完成:", start_date, end_date)
        logger.info("  总计日期: %s", result["total_dates"])
        logger.info("  总计成功: %s", result["total_success"])
        logger.info("  总计失败: %s", result["total_failed"])

        if result["total_failed"] > 0:
            logger.warning("部分计算失败:")
            for detail in result["details"]:
                logger.warning("  - %s", detail)

        session.close()
        return result["total_failed"] == 0

    except Exception as e:
        logger.error("为日期范围 %s 到 %s 计算30日涨跌幅失败: %s", start_date, end_date, e)
        return False


def get_calculation_status(target_date: str) -> None:
    """获取指定日期的计算状态"""
    try:
        logger.info("获取日期 %s 的30日涨跌幅计算状态", target_date)

        session = SessionLocal()
        calculator = ThirtyDayChangeCalculator(session)

        status = calculator.get_calculation_status(target_date)

        logger.info("日期 %s 的计算状态:", target_date)
        logger.info("  总记录数: %s", status["total_records"])
        logger.info("  已计算记录数: %s", status["calculated_records"])
        logger.info("  待计算记录数: %s", status["pending_records"])
        logger.info("  完成率: %s%%", status["completion_rate"])

        if "error" in status:
            logger.error("获取状态时出错: %s", status["error"])

        session.close()

    except Exception as e:
        logger.error("获取日期 %s 的计算状态失败: %s", target_date, e)


def calculate_recent_days(days: int) -> bool:
    """计算最近N天的30日涨跌幅"""
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        logger.info("计算最近 %d 天 (%s 到 %s) 的30日涨跌幅", days, start_date, end_date)

        return calculate_for_date_range(start_date, end_date)

    except Exception as e:
        logger.error("计算最近 %d 天的30日涨跌幅失败: %s", days, e)
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="30日涨跌幅计算工具")
    parser.add_argument(
        "--mode",
        choices=["date", "range", "recent", "status"],
        required=True,
        help="计算模式: date(单日期), range(日期范围), recent(最近N天), status(查看状态)",
    )
    parser.add_argument("--date", type=str, help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="最近天数")

    args = parser.parse_args()

    try:
        if args.mode == "date":
            if not args.date:
                logger.error("单日期模式需要指定 --date 参数")
                return False
            return calculate_for_date(args.date)

        if args.mode == "range":
            if not args.start_date or not args.end_date:
                logger.error("日期范围模式需要指定 --start-date 和 --end-date 参数")
                return False
            return calculate_for_date_range(args.start_date, args.end_date)

        if args.mode == "recent":
            if not args.days:
                logger.error("最近N天模式需要指定 --days 参数")
                return False
            return calculate_recent_days(args.days)

        if args.mode == "status":
            if not args.date:
                logger.error("状态查看模式需要指定 --date 参数")
                return False
            get_calculation_status(args.date)
            return True

    except Exception as e:
        logger.error("执行失败: %s", e)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

