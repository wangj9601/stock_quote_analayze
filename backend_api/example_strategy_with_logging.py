#!/usr/bin/env python3
"""
一阳穿三线策略使用示例（带日志功能）
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_strategy_with_logging():
    """运行策略并记录日志"""
    try:
        # 导入必要的模块
        from stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        print("=" * 60)
        print("🚀 一阳穿三线策略执行示例")
        print("=" * 60)
        
        # 数据库连接配置（请根据实际情况修改）
        DATABASE_URL = "postgresql://username:password@localhost:5432/stock_db"
        
        # 创建数据库连接
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            # 执行策略（测试模式，只处理前50只股票）
            print("📊 开始执行策略（测试模式）...")
            results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
                db=db,
                limit=50,  # 测试模式，只处理50只股票
                min_increase_percent=3.0,
                min_body_ratio=0.7,
                min_cross_lines=3,
                min_volume_ratio=2.0,
                min_turnover_rate=3.0,
                max_turnover_rate=10.0
            )
            
            print(f"\n✅ 策略执行完成！")
            print(f"📈 找到 {len(results)} 只符合条件的股票")
            
            # 显示前5个结果
            if results:
                print("\n🏆 前5个信号:")
                for i, stock in enumerate(results[:5], 1):
                    print(f"{i}. {stock['code']} {stock['name']}")
                    print(f"   评分: {stock['signal_score']}")
                    print(f"   价格: ¥{stock['current_price']}")
                    print(f"   穿越: {stock['crossed_count']}条均线")
                    print(f"   位置: {stock['position_type']}")
                    print(f"   成交量倍数: {stock['volume_ratio']}")
                    print(f"   换手率: {stock['turnover_rate']}%")
                    if stock['risk_warnings']:
                        print(f"   风险提示: {', '.join(stock['risk_warnings'])}")
                    print()
            
            print("📁 详细日志请查看 backend_api/logs/ 目录")
            
        finally:
            db.close()
            
        return True
        
    except Exception as e:
        print(f"❌ 策略执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def run_production_strategy():
    """运行生产模式策略"""
    try:
        from stock.one_yang_three_lines_strategy import OneYangThreeLinesStrategy
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        print("=" * 60)
        print("🏭 一阳穿三线策略生产模式")
        print("=" * 60)
        
        # 数据库连接配置
        DATABASE_URL = "postgresql://username:password@localhost:5432/stock_db"
        
        # 创建数据库连接
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            # 执行策略（生产模式，处理所有股票）
            print("📊 开始执行策略（生产模式）...")
            results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(
                db=db,
                limit=None,  # 生产模式，处理所有股票
                min_increase_percent=3.0,
                min_body_ratio=0.7,
                min_cross_lines=3,
                min_volume_ratio=2.0,
                min_turnover_rate=3.0,
                max_turnover_rate=10.0
            )
            
            print(f"\n✅ 生产模式执行完成！")
            print(f"📈 找到 {len(results)} 只符合条件的股票")
            
            # 保存结果到文件
            if results:
                import json
                output_file = f"strategy_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = os.path.join("logs", output_file)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                
                print(f"📄 结果已保存到: {output_path}")
            
            print("📁 详细日志请查看 backend_api/logs/ 目录")
            
        finally:
            db.close()
            
        return True
        
    except Exception as e:
        print(f"❌ 生产模式执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("一阳穿三线策略执行工具")
    print("=" * 40)
    print("1. 测试模式（处理50只股票）")
    print("2. 生产模式（处理所有股票）")
    print("3. 退出")
    print("=" * 40)
    
    while True:
        choice = input("请选择模式 (1-3): ").strip()
        
        if choice == "1":
            print("\n🧪 启动测试模式...")
            success = run_strategy_with_logging()
            if success:
                print("\n✅ 测试模式执行成功！")
            break
            
        elif choice == "2":
            print("\n🏭 启动生产模式...")
            print("⚠️ 注意：生产模式会处理所有A股股票，可能需要较长时间")
            confirm = input("确认继续？(y/N): ").strip().lower()
            if confirm == 'y':
                success = run_production_strategy()
                if success:
                    print("\n✅ 生产模式执行成功！")
            break
            
        elif choice == "3":
            print("👋 退出程序")
            break
            
        else:
            print("❌ 无效选项，请重新选择")

if __name__ == "__main__":
    main()
