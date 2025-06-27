#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import logging
import sys
import os
from datetime import datetime

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_stock_research_report.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_stock_research_report_em():
    """测试akshare的stock_research_report_em函数"""
    
    logger.info("=== 开始测试 stock_research_report_em 函数 ===")
    
    # 测试股票代码列表
    test_stocks = [
        "603667"  # 五洲新春
    ]
    
    for stock_code in test_stocks:
        try:
            logger.info(f"正在测试股票代码: {stock_code}")
            
            # 调用akshare的stock_research_report_em函数
            df = ak.stock_research_report_em(symbol=stock_code)
            
            if df is not None and not df.empty:
                logger.info(f"成功获取股票 {stock_code} 的研报数据")
                logger.info(f"数据行数: {len(df)}")
                logger.info(f"数据列名: {df.columns.tolist()}")
                
                # 显示前几条数据
                logger.info("前3条数据:")
                for i in range(min(3, len(df))):
                    row = df.iloc[i]
                    logger.info(f"  第{i+1}条: {dict(row)}")
                
                # 显示数据统计信息
                logger.info(f"数据类型统计:")
                for col in df.columns:
                    logger.info(f"  {col}: {df[col].dtype}")
                
            else:
                logger.warning(f"股票 {stock_code} 未获取到研报数据或数据为空")
                
        except Exception as e:
            logger.error(f"测试股票 {stock_code} 时发生错误: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}")
            
        logger.info("-" * 50)
    
    logger.info("=== 测试完成 ===")

def test_stock_notice_report():
    """测试akshare的stock_notice_report相关函数"""
    
    logger.info("=== 开始测试 stock_notice_report 相关函数 ===")
    
    # 测试股票代码列表
    test_stocks = [
        "603667"  # 五洲新春
    ]
    
    # 可能的公告相关函数名
    notice_functions = [
        'stock_notice_report',
        'stock_notice_report_em', 
        'stock_board_notice_em',
        'stock_individual_detail_em',
        'stock_announcement_em'
    ]
    
    # 检查哪些函数可用
    available_functions = []
    for func_name in notice_functions:
        if hasattr(ak, func_name):
            available_functions.append(func_name)
            logger.info(f"✓ 找到函数: {func_name}")
        else:
            logger.info(f"✗ 函数不存在: {func_name}")
    
    if not available_functions:
        logger.warning("未找到任何公告相关函数，尝试搜索包含'notice'的函数")
        notice_funcs = [name for name in dir(ak) if 'notice' in name.lower()]
        logger.info(f"包含'notice'的函数: {notice_funcs}")
        
        logger.warning("尝试搜索包含'announcement'的函数")
        announcement_funcs = [name for name in dir(ak) if 'announcement' in name.lower()]
        logger.info(f"包含'announcement'的函数: {announcement_funcs}")
        
        logger.warning("尝试搜索包含'board'的函数")
        board_funcs = [name for name in dir(ak) if 'board' in name.lower()]
        logger.info(f"包含'board'的函数: {board_funcs}")
        return
    
    # 测试可用的函数
    for func_name in available_functions:
        logger.info(f"\n=== 测试函数: {func_name} ===")
        
        try:
            func = getattr(ak, func_name)
            logger.info(f"函数对象: {func}")
            
            # 尝试获取函数文档
            if hasattr(func, '__doc__') and func.__doc__:
                logger.info(f"函数文档: {func.__doc__}")
            else:
                logger.info("函数无文档说明")
            
            # 测试每个股票代码
            for stock_code in test_stocks:
                try:
                    logger.info(f"正在测试股票代码 {stock_code} 使用函数 {func_name}")
                    
                    # 尝试不同的参数调用方式
                    df = None
                    try:
                        # 尝试 symbol 参数
                        df = func(symbol=stock_code)
                    except Exception as e1:
                        logger.info(f"尝试symbol参数失败: {e1}")
                        try:
                            # 尝试 code 参数
                            df = func(code=stock_code)
                        except Exception as e2:
                            logger.info(f"尝试code参数失败: {e2}")
                            try:
                                # 尝试无参数调用
                                df = func()
                            except Exception as e3:
                                logger.info(f"尝试无参数调用失败: {e3}")
                    
                    if df is not None and not df.empty:
                        logger.info(f"成功获取股票 {stock_code} 的公告数据")
                        logger.info(f"数据行数: {len(df)}")
                        logger.info(f"数据列名: {df.columns.tolist()}")
                        
                        # 显示前几条数据
                        logger.info("前3条数据:")
                        for i in range(min(3, len(df))):
                            row = df.iloc[i]
                            logger.info(f"  第{i+1}条: {dict(row)}")
                        
                        # 显示数据统计信息
                        logger.info(f"数据类型统计:")
                        for col in df.columns:
                            logger.info(f"  {col}: {df[col].dtype}")
                        
                    else:
                        logger.warning(f"股票 {stock_code} 未获取到公告数据或数据为空")
                        
                except Exception as e:
                    logger.error(f"测试股票 {stock_code} 使用函数 {func_name} 时发生错误: {str(e)}")
                    logger.error(f"错误详情: {type(e).__name__}")
                
                logger.info("-" * 30)
                
        except Exception as e:
            logger.error(f"测试函数 {func_name} 时发生错误: {str(e)}")
        
        logger.info("-" * 50)
    
    logger.info("=== 公告函数测试完成 ===")

def test_stock_research_report_detailed():
    """详细测试stock_research_report_em函数的参数和返回值"""
    
    logger.info("=== 开始详细测试 stock_research_report_em 函数 ===")
    
    try:
        # 使用用户指定的股票代码进行详细测试
        test_code = "603667"  # 五洲新春
        
        logger.info(f"详细测试股票代码: {test_code}")
        
        # 获取研报数据
        df = ak.stock_research_report_em(symbol=test_code)
        
        if df is not None and not df.empty:
            logger.info("=== 数据结构分析 ===")
            logger.info(f"数据形状: {df.shape}")
            logger.info(f"列名: {list(df.columns)}")
            
            # 分析每列的数据类型和示例值
            logger.info("=== 列详细信息 ===")
            for col in df.columns:
                logger.info(f"列名: {col}")
                logger.info(f"  数据类型: {df[col].dtype}")
                logger.info(f"  非空值数量: {df[col].count()}")
                logger.info(f"  示例值: {df[col].iloc[0] if len(df) > 0 else 'N/A'}")
                logger.info("")
            
            # 显示完整的前几条记录
            logger.info("=== 完整记录示例 ===")
            for i in range(min(2, len(df))):
                logger.info(f"第{i+1}条记录:")
                row = df.iloc[i]
                for col in df.columns:
                    logger.info(f"  {col}: {row[col]}")
                logger.info("")
                
        else:
            logger.warning("未获取到研报数据")
            
    except Exception as e:
        logger.error(f"详细测试时发生错误: {str(e)}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")

def test_function_availability():
    """测试函数是否可用"""
    
    logger.info("=== 测试函数可用性 ===")
    
    try:
        # 检查akshare是否有research report函数
        if hasattr(ak, 'stock_research_report_em'):
            logger.info("✓ stock_research_report_em 函数存在")
            
            # 获取函数信息
            func = getattr(ak, 'stock_research_report_em')
            logger.info(f"函数对象: {func}")
            
            # 尝试获取函数文档
            if hasattr(func, '__doc__') and func.__doc__:
                logger.info(f"函数文档: {func.__doc__}")
            else:
                logger.info("函数无文档说明")
                
        else:
            logger.error("✗ stock_research_report_em 函数不存在")
            
            # 列出akshare中包含research的函数
            research_funcs = [name for name in dir(ak) if 'research' in name.lower()]
            logger.info(f"akshare中包含'research'的函数: {research_funcs}")
            
            # 列出akshare中包含report的函数
            report_funcs = [name for name in dir(ak) if 'report' in name.lower()]
            logger.info(f"akshare中包含'report'的函数: {report_funcs}")
        
        # 检查公告相关函数
        logger.info("\n=== 检查公告相关函数 ===")
        notice_related_funcs = []
        for name in dir(ak):
            if any(keyword in name.lower() for keyword in ['notice', 'announcement', 'board']):
                notice_related_funcs.append(name)
        
        if notice_related_funcs:
            logger.info(f"找到公告相关函数: {notice_related_funcs}")
        else:
            logger.info("未找到公告相关函数")
            
    except Exception as e:
        logger.error(f"测试函数可用性时发生错误: {str(e)}")

if __name__ == "__main__":
    logger.info(f"测试开始时间: {datetime.now()}")
    logger.info(f"akshare版本: {ak.__version__ if hasattr(ak, '__version__') else '未知'}")
    
    # 运行所有测试
    test_function_availability()
    test_stock_research_report_em()
    test_stock_notice_report()  # 新增的公告测试
    test_stock_research_report_detailed()
    
    logger.info(f"测试结束时间: {datetime.now()}") 