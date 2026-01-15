"""
PVFRS策略管理API接口
提供策略配置、回测任务、结果查询等功能
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import cast, Date as SA_Date

from backend_api.database import get_db
from backend_api.models import MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
from backend_core.strategies.pvfrs.pvfrs_backtest_runner import PVFRSBacktestRunner
from backend_core.strategies.pvfrs.pvfrs_data_loader import PVFRSDataLoader
from backend_core.strategies.pvfrs.pvfrs_performance_analyzer import PVFRSPerformanceAnalyzer, PVFRSReportGenerator

router = APIRouter(prefix="/api/admin/pvfrs", tags=["PVFRS策略管理"])

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
    "backend_core/strategies/pvfrs/pvfrs_config.json"
)

# 全局任务存储（生产环境建议使用数据库或Redis）
running_tasks = {}

class StrategyConfigResponse(BaseModel):
    """策略配置响应"""
    strategy_params: Dict
    backtest_config: Dict
    optimization_config: Dict
    reporting: Dict

class BacktestRequest(BaseModel):
    """回测请求"""
    mode: str  # single, batch, optimize
    code: Optional[str] = None
    market: str = "CN"
    start_date: str
    end_date: str
    initial_capital: float = 100000

class TaskStatus(BaseModel):
    """任务状态"""
    id: str
    step: int
    progress: int
    status: str  # active, completed, failed
    message: str
    log: Optional[str] = None

class BacktestResult(BaseModel):
    """回测结果"""
    id: str
    code: str
    market: str
    date: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_period: float
    trades: List[Dict]
    equity_curve: List[Dict]

def load_jsonc(file_path: str) -> Dict:
    """加载带注释的JSON文件"""
    import re
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 /* ... */ 注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.S)
    
    # 移除 // 注释
    content = re.sub(r'(^|\s)//.*$', r'\1', content, flags=re.M)
    
    return json.loads(content)

def save_jsonc(file_path: str, data: Dict):
    """保存带注释的JSON文件"""
    # 读取原文件，保留注释
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except:
        original_content = json.dumps(data, indent=2, ensure_ascii=False)
    
    # 更新配置部分
    config = load_jsonc(file_path) if os.path.exists(file_path) else {}
    config.update(data)
    
    # 保存时尽量保留原有注释格式
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

@router.get("/config", response_model=StrategyConfigResponse)
async def get_strategy_config():
    """获取策略配置"""
    try:
        config = load_jsonc(CONFIG_FILE_PATH)
        return StrategyConfigResponse(
            strategy_params=config.get("strategy_params", {}),
            backtest_config=config.get("backtest_config", {}),
            optimization_config=config.get("optimization_config", {}),
            reporting=config.get("reporting", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取配置失败: {str(e)}")

@router.post("/config")
async def save_strategy_config(config: Dict):
    """保存策略配置"""
    try:
        save_jsonc(CONFIG_FILE_PATH, config)
        return {"message": "配置保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")

@router.post("/backtest", response_model=TaskStatus)
async def submit_backtest(
    mode: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    market: str = Form("CN"),
    code: Optional[str] = Form(None),
    initial_capital: float = Form(100000),
    stock_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """提交回测任务"""
    try:
        request = BacktestRequest(
            mode=mode,
            code=code,
            market=market,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )

        # 生成任务ID
        task_id = f"pvfrs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建任务状态
        running_tasks[task_id] = TaskStatus(
            id=task_id,
            step=1,
            progress=0,
            status="active",
            message="正在准备数据...",
            log=""
        )
        
        # 异步执行回测任务
        asyncio.create_task(execute_backtest_task(task_id, request, stock_file, db))
        
        return running_tasks[task_id]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交回测任务失败: {str(e)}")

async def execute_backtest_task(task_id: str, request: BacktestRequest, stock_file: Optional[UploadFile], db: Session):
    """执行回测任务"""
    try:
        def _get_history_rows(code: str, market_type: str):
            if market_type == 'CN':
                start_dt = datetime.strptime(request.start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(request.end_date, "%Y-%m-%d").date()
                date_col = cast(HistoricalQuotes.date, SA_Date)
                return db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code == code,
                    date_col >= start_dt,
                    date_col <= end_dt
                ).order_by(date_col.asc()).all()
            return db.query(HistoricalQuotesHK).filter(
                HistoricalQuotesHK.code == code,
                HistoricalQuotesHK.date >= request.start_date,
                HistoricalQuotesHK.date <= request.end_date
            ).order_by(HistoricalQuotesHK.date.asc()).all()

        def _has_pvfrs(code: str, market_type: str) -> bool:
            return db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date >= request.start_date,
                MeanFrequencyResonanceIndicators.date <= request.end_date
            ).first() is not None

        def _ensure_pvfrs(code: str, market_type: str):
            if _has_pvfrs(code, market_type):
                return

            history_rows = _get_history_rows(code, market_type)
            if not history_rows:
                return

            closes = [float(r.close or 0) for r in history_rows]
            volumes = [float(r.volume or 0) for r in history_rows]
            calc = MeanFrequencyResonanceCalculator()
            pvfrs_list = calc.calculate(closes, volumes)

            for i, row in enumerate(history_rows):
                if i >= len(pvfrs_list):
                    break
                pv = pvfrs_list[i]
                if pv is None:
                    continue
                if market_type == 'CN':
                    date_str = str(getattr(row, 'date', None))[:10] if getattr(row, 'date', None) is not None else None
                else:
                    date_str = row.date
                if not date_str:
                    continue
                if date_str < request.start_date or date_str > request.end_date:
                    continue

                db.merge(MeanFrequencyResonanceIndicators(
                    code=code,
                    date=date_str,
                    market_type=market_type,
                    ma20_d=pv.get('ma20_d'),
                    mavol20_m=pv.get('mavol20_m'),
                    macro_displacement_delta=pv.get('macro_displacement_delta'),
                    instant_deviation=pv.get('instant_deviation'),
                    efficiency_m20_minus_m=pv.get('efficiency_m20_minus_m'),
                    rising_days_z=pv.get('rising_days_z'),
                    falling_days_f=pv.get('falling_days_f'),
                    bias=pv.get('bias')
                ))

            db.commit()

        # 更新任务状态
        running_tasks[task_id].step = 1
        running_tasks[task_id].progress = 20
        running_tasks[task_id].message = "正在准备数据..."
        
        # 创建回测运行器
        runner = PVFRSBacktestRunner()
        
        if request.mode == "single":
            # 单股回测
            running_tasks[task_id].step = 2
            running_tasks[task_id].progress = 40
            running_tasks[task_id].message = f"正在回测股票 {request.code}..."

            history_rows = _get_history_rows(request.code, request.market)
            if not history_rows:
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = "回测失败：数据库中缺少该股票的历史行情数据（HistoricalQuotes）"
                return

            _ensure_pvfrs(request.code, request.market)
            if not _has_pvfrs(request.code, request.market):
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = "回测失败：数据库中缺少PVFRS指标数据（mean_frequency_resonance_indicators）"
                return
            
            result = runner.run_single_backtest(
                request.code,
                request.market,
                request.start_date,
                request.end_date,
                initial_capital=request.initial_capital
            )
            
            if result:
                running_tasks[task_id].step = 3
                running_tasks[task_id].progress = 80
                running_tasks[task_id].message = "正在分析结果..."
                
                # 保存结果
                save_backtest_result(task_id, result, request)
                
                running_tasks[task_id].step = 4
                running_tasks[task_id].progress = 100
                running_tasks[task_id].status = "completed"
                running_tasks[task_id].message = "回测完成"
            else:
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = "回测失败：无有效数据"
                
        elif request.mode == "batch":
            # 批量回测
            stock_codes = []
            
            if stock_file:
                # 从文件读取股票代码
                content = await stock_file.read()
                stock_codes = [line.strip() for line in content.decode('utf-8').split('\n') if line.strip()]
            else:
                # 从数据库获取所有股票
                loader = PVFRSDataLoader(db)
                stock_codes = loader.get_available_stocks(request.market)
            
            running_tasks[task_id].step = 2
            running_tasks[task_id].progress = 30
            running_tasks[task_id].message = f"正在批量回测 {len(stock_codes)} 只股票..."

            # 批量场景：尽量为每只股票补 PVFRS 指标（如果有历史行情）
            for c in stock_codes:
                try:
                    if _get_history_rows(c, request.market):
                        _ensure_pvfrs(c, request.market)
                except Exception:
                    # 忽略单只股票指标计算失败，回测时会自然跳过无数据股票
                    continue
            
            results = runner.run_batch_backtest(
                stock_codes,
                request.market,
                request.start_date,
                request.end_date,
                initial_capital=request.initial_capital
            )
            
            running_tasks[task_id].step = 3
            running_tasks[task_id].progress = 80
            running_tasks[task_id].message = "正在分析结果..."
            
            # 保存批量结果
            save_batch_results(task_id, results, request)
            
            running_tasks[task_id].step = 4
            running_tasks[task_id].progress = 100
            running_tasks[task_id].status = "completed"
            running_tasks[task_id].message = f"批量回测完成，共 {len(results)} 个结果"
            
        elif request.mode == "optimize":
            # 参数优化
            running_tasks[task_id].step = 2
            running_tasks[task_id].progress = 30
            running_tasks[task_id].message = f"正在优化参数 {request.code}..."

            history_rows = _get_history_rows(request.code, request.market)
            if not history_rows:
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = "优化失败：数据库中缺少该股票的历史行情数据（HistoricalQuotes）"
                return

            _ensure_pvfrs(request.code, request.market)
            if not _has_pvfrs(request.code, request.market):
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = "优化失败：数据库中缺少PVFRS指标数据（mean_frequency_resonance_indicators）"
                return
            
            optimization_result = runner.run_parameter_optimization(
                request.code,
                request.market,
                request.start_date,
                request.end_date
            )
            
            running_tasks[task_id].step = 3
            running_tasks[task_id].progress = 80
            running_tasks[task_id].message = "正在分析优化结果..."
            
            # 保存优化结果
            save_optimization_result(task_id, optimization_result, request)
            
            running_tasks[task_id].step = 4
            running_tasks[task_id].progress = 100
            running_tasks[task_id].status = "completed"
            running_tasks[task_id].message = "参数优化完成"
            
    except Exception as e:
        running_tasks[task_id].status = "failed"
        running_tasks[task_id].message = f"任务执行失败: {str(e)}"
        running_tasks[task_id].log = str(e)

@router.get("/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id in running_tasks:
        return running_tasks[task_id]
    else:
        raise HTTPException(status_code=404, detail="任务不存在")

@router.get("/results", response_model=List[BacktestResult])
async def get_backtest_results():
    """获取回测结果列表"""
    try:
        results = load_backtest_results()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测结果失败: {str(e)}")

@router.delete("/results")
async def clear_backtest_results():
    """清空回测结果"""
    try:
        # 清空结果文件
        results_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "backend_core/strategies/pvfrs/backtest_results.json"
        )
        if os.path.exists(results_file):
            os.remove(results_file)
        
        return {"message": "回测结果已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空回测结果失败: {str(e)}")

def save_backtest_result(task_id: str, result, request: BacktestRequest):
    """保存单个回测结果"""
    try:
        # 读取现有结果
        results = load_backtest_results()
        
        # 构建结果对象
        result_data = BacktestResult(
            id=task_id,
            code=result.stock_code,
            market=result.market_type,
            date=datetime.now().strftime('%Y-%m-%d'),
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=result.initial_capital,
            final_capital=result.final_capital,
            total_return=result.total_return,
            annual_return=result.annual_return,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            total_trades=result.total_trades,
            avg_holding_period=result.avg_holding_period,
            trades=[
                {
                    "entryDate": trade.entry_date,
                    "exitDate": trade.exit_date,
                    "entryPrice": trade.entry_price,
                    "exitPrice": trade.exit_price,
                    "pnl": trade.pnl,
                    "pnlPercent": trade.pnl_percent,
                    "exitReason": trade.exit_reason
                }
                for trade in result.trades
            ],
            equity_curve=[
                {
                    "date": item["date"],
                    "equity": item["equity"]
                }
                for item in result.equity_curve.to_dict('records')
            ]
        )
        
        # 添加到结果列表
        results.append(result_data.dict())
        
        # 保存结果
        save_backtest_results(results)
        
    except Exception as e:
        print(f"保存回测结果失败: {e}")

def save_batch_results(task_id: str, results: List, request: BacktestRequest):
    """保存批量回测结果"""
    try:
        # 读取现有结果
        existing_results = load_backtest_results()
        
        # 为每个结果创建记录
        for result in results:
            if result:  # 跳过None结果
                result_data = BacktestResult(
                    id=f"{task_id}_{result.stock_code}",
                    code=result.stock_code,
                    market=result.market_type,
                    date=datetime.now().strftime('%Y-%m-%d'),
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=result.initial_capital,
                    final_capital=result.final_capital,
                    total_return=result.total_return,
                    annual_return=result.annual_return,
                    max_drawdown=result.max_drawdown,
                    sharpe_ratio=result.sharpe_ratio,
                    win_rate=result.win_rate,
                    profit_factor=result.profit_factor,
                    total_trades=result.total_trades,
                    avg_holding_period=result.avg_holding_period,
                    trades=[
                        {
                            "entryDate": trade.entry_date,
                            "exitDate": trade.exit_date,
                            "entryPrice": trade.entry_price,
                            "exitPrice": trade.exit_price,
                            "pnl": trade.pnl,
                            "pnlPercent": trade.pnl_percent,
                            "exitReason": trade.exit_reason
                        }
                        for trade in result.trades
                    ],
                    equity_curve=[
                        {
                            "date": item["date"],
                            "equity": item["equity"]
                        }
                        for item in result.equity_curve.to_dict('records')
                    ]
                ).dict()
                
                existing_results.append(result_data)
        
        # 保存结果
        save_backtest_results(existing_results)
        
    except Exception as e:
        print(f"保存批量回测结果失败: {e}")

def save_optimization_result(task_id: str, optimization_result: Dict, request: BacktestResult):
    """保存参数优化结果"""
    try:
        # 读取现有结果
        results = load_backtest_results()
        
        # 保存最佳结果
        if optimization_result.get("best_result"):
            best = optimization_result["best_result"]
            result_data = BacktestResult(
                id=f"{task_id}_best",
                code=request.code,
                market=request.market,
                date=datetime.now().strftime('%Y-%m-%d'),
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=best.initial_capital,
                final_capital=best.final_capital,
                total_return=best.total_return,
                annual_return=best.annual_return,
                max_drawdown=best.max_drawdown,
                sharpe_ratio=best.sharpe_ratio,
                win_rate=best.win_rate,
                profit_factor=best.profit_factor,
                total_trades=best.total_trades,
                avg_holding_period=best.avg_holding_period,
                trades=[],
                equity_curve=[]
            ).dict()
            
            results.append(result_data)
        
        # 保存结果
        save_backtest_results(results)
        
    except Exception as e:
        print(f"保存优化结果失败: {e}")

def load_backtest_results() -> List[Dict]:
    """加载回测结果"""
    results_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "backend_core/strategies/pvfrs/backtest_results.json"
    )
    
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    else:
        return []

def save_backtest_results(results: List[Dict]):
    """保存回测结果"""
    results_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "backend_core/strategies/pvfrs/backtest_results.json"
    )
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
