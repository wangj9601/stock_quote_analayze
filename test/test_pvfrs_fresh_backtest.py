"""
清空旧结果并运行新的PVFRS回测
"""
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.models import (
    PVFRSBacktestTask, PVFRSBacktestResult, 
    PVFRSTradeRecord, PVFRSEquityCurve
)
from backend_core.strategies.pvfrs.pvfrs_backtest_runner import PVFRSBacktestRunner

def clear_old_results():
    """清空旧的回测结果"""
    print("=" * 80)
    print("清空旧的回测结果...")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        # 删除所有相关记录
        equity_count = db.query(PVFRSEquityCurve).delete()
        trade_count = db.query(PVFRSTradeRecord).delete()
        result_count = db.query(PVFRSBacktestResult).delete()
        task_count = db.query(PVFRSBacktestTask).delete()
        db.commit()
        
        print(f"✓ 已删除 {equity_count} 条权益曲线记录")
        print(f"✓ 已删除 {trade_count} 条交易记录")
        print(f"✓ 已删除 {result_count} 条回测结果")
        print(f"✓ 已删除 {task_count} 条回测任务")
        print()
        
    except Exception as e:
        db.rollback()
        print(f"✗ 清空失败: {e}")
    finally:
        db.close()

def run_fresh_backtest():
    """运行新的回测"""
    print("=" * 80)
    print("运行新的回测...")
    print("=" * 80)
    
    # 创建回测运行器
    runner = PVFRSBacktestRunner()
    
    # 回测参数
    code = "688114"
    market = "CN"
    start_date = "2022-10-14"
    end_date = "2026-01-16"
    
    print(f"\n股票代码: {code}")
    print(f"市场类型: {market}")
    print(f"回测区间: {start_date} 到 {end_date}")
    print(f"回测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 运行回测（使用默认参数，即代码中的新参数）
    result = runner.run_single_backtest(
        code=code,
        market_type=market,
        start_date=start_date,
        end_date=end_date,
        params=None,  # 使用默认参数
        initial_capital=100000
    )
    
    if result:
        print("\n" + "=" * 80)
        print("回测结果:")
        print("=" * 80)
        print(f"总收益率: {result.total_return:.2%}")
        print(f"年化收益率: {result.annual_return:.2%}")
        print(f"最大回撤: {result.max_drawdown:.2%}")
        print(f"夏普比率: {result.sharpe_ratio:.2f}")
        print(f"胜率: {result.win_rate:.2%}")
        print(f"盈亏比: {result.profit_factor:.2f}")
        print(f"交易次数: {result.total_trades}")
        print(f"平均持有天数: {result.avg_holding_period:.1f}")
        print("=" * 80)
        
        # 显示交易明细
        print("\n交易明细:")
        print("-" * 80)
        for i, trade in enumerate(result.trades, 1):
            print(f"{i}. {trade.entry_date} -> {trade.exit_date}")
            print(f"   买入: ¥{trade.entry_price:.2f}, 卖出: ¥{trade.exit_price:.2f}")
            print(f"   盈亏: ¥{trade.pnl:.2f} ({trade.pnl_percent:.2%})")
            print(f"   原因: {trade.exit_reason}")
            print()
        
        return True
    else:
        print("✗ 回测失败")
        return False

if __name__ == "__main__":
    # 1. 清空旧结果
    clear_old_results()
    
    # 2. 运行新回测
    success = run_fresh_backtest()
    
    if success:
        print("\n✓ 回测完成！请刷新前端页面查看新结果。")
    else:
        print("\n✗ 回测失败！请检查日志。")
