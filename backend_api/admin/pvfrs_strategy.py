"""
PVFRS策略管理API接口
提供策略配置、回测任务、结果查询等功能
"""

import os
import json
import pandas as pd
from datetime import datetime, date
import asyncio
import traceback
from typing import List, Dict, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import cast, Date as SA_Date

from backend_api.database import get_db
from backend_api.models import (
    MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK,
    PVFRSBacktestTask, PVFRSBacktestResult, PVFRSTradeRecord, PVFRSEquityCurve
)
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
from backend_core.strategies.pvfrs.pvfrs_backtest_runner import PVFRSBacktestRunner
from backend_core.strategies.pvfrs.pvfrs_data_loader import PVFRSDataLoader
from backend_core.strategies.pvfrs.pvfrs_performance_analyzer import PVFRSPerformanceAnalyzer, PVFRSReportGenerator

router = APIRouter(prefix="/api/admin/pvfrs", tags=["PVFRS策略管理"])

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
    "backend_core/strategies/pvfrs/pvfars_config.json"
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
    stock_codes: Optional[List[str]] = None  # 批量回测时的股票代码列表

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
    request: BacktestRequest,
    db: Session = Depends(get_db)
):
    """提交回测任务"""
    try:
        print(f"[DEBUG] submit_backtest called: mode={request.mode}, code={request.code}, market={request.market}")
        # 解析股票代码
        stock_codes = []
        if request.mode == "single":
            stock_codes = [request.code]
        elif request.mode == "batch":
            if request.stock_codes:
                # 使用请求中的股票代码列表
                stock_codes = request.stock_codes
            else:
                # 从数据库获取所有股票
                loader = PVFRSDataLoader(db)
                stock_codes = loader.get_available_stocks(request.market)
        elif request.mode == "optimize":
            stock_codes = [request.code]

        # 生成任务ID
        task_id = f"pvfrs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建数据库任务记录
        db_task = PVFRSBacktestTask(
            task_id=task_id,
            mode=request.mode,
            stock_codes=json.dumps(stock_codes),
            market=request.market,
            start_date=datetime.strptime(request.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.end_date, "%Y-%m-%d").date(),
            initial_capital=request.initial_capital,
            status="running",
            progress=0,
            current_step="正在准备数据..."
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        # 创建任务状态（用于前端显示）
        running_tasks[task_id] = TaskStatus(
            id=task_id,
            step=1,
            progress=0,
            status="active",
            message="正在准备数据...",
            log=""
        )
        
        print(f"[DEBUG] about to schedule async task for task_id={task_id}")
        # 异步执行回测任务
        asyncio.create_task(execute_backtest_task(task_id, request, None, db))
        
        return running_tasks[task_id]
        
    except Exception as e:
        print(f"[ERROR] submit_backtest exception: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"提交回测任务失败: {str(e)}")

@router.post("/backtest/upload", response_model=TaskStatus)
async def submit_backtest_with_file(
    mode: str = Form(...),
    market: str = Form("CN"),
    start_date: str = Form(...),
    end_date: str = Form(...),
    code: Optional[str] = Form(None),
    initial_capital: float = Form(100000),
    stock_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """提交回测任务（文件上传版本）"""
    try:
        # 构建request对象
        backtest_request = BacktestRequest(
            mode=mode,
            market=market,
            start_date=start_date,
            end_date=end_date,
            code=code,
            initial_capital=initial_capital
        )
        
        # 解析股票代码
        stock_codes = []
        if backtest_request.mode == "single":
            stock_codes = [backtest_request.code]
        elif backtest_request.mode == "batch":
            if stock_file:
                content = await stock_file.read()
                stock_codes = [line.strip() for line in content.decode('utf-8').split('\n') if line.strip()]
                backtest_request.stock_codes = stock_codes
            else:
                # 从数据库获取所有股票
                loader = PVFRSDataLoader(db)
                stock_codes = loader.get_available_stocks(backtest_request.market)
        elif backtest_request.mode == "optimize":
            stock_codes = [backtest_request.code]

        # 生成任务ID
        task_id = f"pvfrs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建数据库任务记录
        db_task = PVFRSBacktestTask(
            task_id=task_id,
            mode=backtest_request.mode,
            stock_codes=json.dumps(stock_codes),
            market=backtest_request.market,
            start_date=datetime.strptime(backtest_request.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(backtest_request.end_date, "%Y-%m-%d").date(),
            initial_capital=backtest_request.initial_capital,
            status="running",
            progress=0,
            current_step="正在准备数据..."
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        # 创建任务状态（用于前端显示）
        running_tasks[task_id] = TaskStatus(
            id=task_id,
            step=1,
            progress=0,
            status="active",
            message="正在准备数据...",
            log=""
        )
        
        # 异步执行回测任务
        asyncio.create_task(execute_backtest_task(task_id, backtest_request, None, db))
        
        return running_tasks[task_id]
        
    except Exception as e:
        db.rollback()
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
                MeanFrequencyResonanceIndicators.market_type == market_type
            ).first() is not None

        def _ensure_pvfrs(code: str, market_type: str):
            if not _has_pvfrs(code, market_type):
                calculator = MeanFrequencyResonanceCalculator()
                history_rows = _get_history_rows(code, market_type)
                if len(history_rows) >= 20:
                    data = calculator.calculate_for_dataframe(history_rows)
                    for _, row in data.iterrows():
                        indicator = MeanFrequencyResonanceIndicators(
                            code=code,
                            date=row['date'],
                            market_type=market_type,
                            macro_displacement_delta=row['macro_displacement_delta'],
                            ratio_d20=row.get('ratio_d20'),
                            ratio_d1=row.get('ratio_d1'),
                            instant_deviation=row['instant_deviation'],
                            rising_days_z=row['rising_days_z'],
                            falling_days_f=row['falling_days_f'],
                            efficiency_m20_minus_m=row['efficiency_m20_minus_m'],
                            ma20_d=row['ma20_d'],
                            mavol20_m=row['mavol20_m'],
                            bias=row['bias']
                        )
                        db.merge(indicator)
                    db.commit()

        def _update_task_status(step: int, progress: int, message: str, status: str = "running"):
            # 更新内存中的任务状态
            if task_id in running_tasks:
                running_tasks[task_id].step = step
                running_tasks[task_id].progress = progress
                running_tasks[task_id].message = message
                if status != "running":
                    running_tasks[task_id].status = status
            
            # 更新数据库中的任务状态
            db_task = db.query(PVFRSBacktestTask).filter(PVFRSBacktestTask.task_id == task_id).first()
            if db_task:
                db_task.progress = progress
                db_task.current_step = message
                if status == "completed":
                    db_task.status = "completed"
                    db_task.completed_at = datetime.now()
                elif status == "failed":
                    db_task.status = "failed"
                    db_task.error_message = message
                db.commit()

        # 获取股票代码
        stock_codes = []
        if request.mode == "single":
            stock_codes = [request.code]
        elif request.mode == "batch":
            if request.stock_codes:
                # 使用请求中的股票代码列表
                stock_codes = request.stock_codes
            elif stock_file:
                content = await stock_file.read()
                stock_codes = [line.strip() for line in content.decode('utf-8').split('\n') if line.strip()]
            else:
                # 从数据库获取所有股票
                loader = PVFRSDataLoader(db)
                stock_codes = loader.get_available_stocks(request.market)
        elif request.mode == "optimize":
            stock_codes = [request.code]

        if request.mode == "single":
            # 单股回测
            _update_task_status(2, 30, "正在准备数据...")
            
            if _get_history_rows(request.code, request.market):
                _ensure_pvfrs(request.code, request.market)
            
            _update_task_status(3, 60, "正在执行回测...")
            
            runner = PVFRSBacktestRunner()
            
            # 加载策略参数
            try:
                config = load_jsonc(CONFIG_FILE_PATH)
                custom_params = config.get("strategy_params", {})
            except:
                custom_params = None
            
            result = runner.run_single_backtest(
                request.code,
                request.market,
                request.start_date,
                request.end_date,
                params=custom_params,
                initial_capital=request.initial_capital
            )
            
            _update_task_status(4, 90, "正在保存结果...")
            
            # 保存结果到数据库
            save_result_to_db(task_id, result, request, db)
            
            _update_task_status(4, 100, "回测完成", "completed")
            
        elif request.mode == "batch":
            # 批量回测
            _update_task_status(2, 30, f"正在批量回测 {len(stock_codes)} 只股票...")

            # 批量场景：尽量为每只股票补 PVFRS 指标（如果有历史行情）
            for c in stock_codes:
                try:
                    if _get_history_rows(c, request.market):
                        _ensure_pvfrs(c, request.market)
                except Exception:
                    # 忽略单只股票指标计算失败，回测时会自然跳过无数据股票
                    continue
            
            runner = PVFRSBacktestRunner()
            
            # 加载策略参数
            try:
                config = load_jsonc(CONFIG_FILE_PATH)
                custom_params = config.get("strategy_params", {})
            except:
                custom_params = None
            
            results = runner.run_batch_backtest(
                stock_codes,
                request.market,
                request.start_date,
                request.end_date,
                params=custom_params,
                initial_capital=request.initial_capital
            )
            
            _update_task_status(3, 80, "正在分析结果...")
            
            # 保存批量结果到数据库
            save_batch_results_to_db(task_id, results, request, db)
            
            _update_task_status(4, 100, f"批量回测完成，共 {len(results)} 个结果", "completed")
            
        elif request.mode == "optimize":
            # 参数优化
            _update_task_status(2, 30, "正在优化参数...")
            
            if _get_history_rows(request.code, request.market):
                _ensure_pvfrs(request.code, request.market)
            
            _update_task_status(3, 60, "正在执行优化...")
            
            runner = PVFRSBacktestRunner()
            
            # 加载策略参数
            try:
                config = load_jsonc(CONFIG_FILE_PATH)
                custom_params = config.get("strategy_params", {})
            except:
                custom_params = None
            
            optimization_result = runner.run_parameter_optimization(
                request.code,
                request.market,
                request.start_date,
                request.end_date,
                param_grid=custom_params
            )
            
            _update_task_status(4, 90, "正在保存优化结果...")
            
            # 保存优化结果到数据库
            save_optimization_result_to_db(task_id, optimization_result, request, db)
            
            _update_task_status(4, 100, "参数优化完成", "completed")
                
    except Exception as e:
        # 更新任务状态为失败
        db_task = db.query(PVFRSBacktestTask).filter(PVFRSBacktestTask.task_id == task_id).first()
        if db_task:
            db_task.status = "failed"
            db_task.error_message = str(e)
            db.commit()
        
        if task_id in running_tasks:
            running_tasks[task_id].status = "failed"
            running_tasks[task_id].message = f"回测失败: {str(e)}"
        
        print(f"回测任务 {task_id} 执行失败: {e}")

@router.get("/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id in running_tasks:
        return running_tasks[task_id]
    else:
        raise HTTPException(status_code=404, detail="任务不存在")

@router.get("/results", response_model=List[BacktestResult])
async def get_backtest_results(db: Session = Depends(get_db)):
    """获取回测结果列表"""
    try:
        results = get_backtest_results_from_db(db)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测结果失败: {str(e)}")

@router.delete("/results")
async def clear_backtest_results(db: Session = Depends(get_db)):
    """清空回测结果"""
    try:
        clear_backtest_results_from_db(db)
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
            initial_capital=float(result.initial_capital),
            final_capital=float(result.final_capital),
            total_return=float(result.total_return),
            annual_return=float(result.annual_return),
            max_drawdown=float(result.max_drawdown),
            sharpe_ratio=float(result.sharpe_ratio),
            win_rate=float(result.win_rate),
            profit_factor=float(result.profit_factor),
            total_trades=int(result.total_trades),
            avg_holding_period=float(result.avg_holding_period),
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
                    initial_capital=float(result.initial_capital),
                    final_capital=float(result.final_capital),
                    total_return=float(result.total_return),
                    annual_return=float(result.annual_return),
                    max_drawdown=float(result.max_drawdown),
                    sharpe_ratio=float(result.sharpe_ratio),
                    win_rate=float(result.win_rate),
                    profit_factor=float(result.profit_factor),
                    total_trades=int(result.total_trades),
                    avg_holding_period=float(result.avg_holding_period),
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
                initial_capital=float(best.initial_capital),
                final_capital=float(best.final_capital),
                total_return=float(best.total_return),
                annual_return=float(best.annual_return),
                max_drawdown=float(best.max_drawdown),
                sharpe_ratio=float(best.sharpe_ratio),
                win_rate=float(best.win_rate),
                profit_factor=float(best.profit_factor),
                total_trades=int(best.total_trades),
                avg_holding_period=float(best.avg_holding_period),
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

def _parse_date_compat(value) -> date:
    if value is None:
        raise ValueError("date is None")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        raise ValueError("empty date")
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    if len(s) == 8 and s.isdigit():
        return datetime.strptime(s, "%Y%m%d").date()
    raise ValueError(f"unsupported date format: {s}")

def save_result_to_db(task_id: str, result, request: BacktestRequest, db: Session):
    """保存单个回测结果到数据库"""
    try:
        # 使用实际回测数据区间（优先取权益曲线日期范围），避免仅使用用户输入区间
        actual_start_date = _parse_date_compat(request.start_date)
        actual_end_date = _parse_date_compat(request.end_date)
        try:
            equity_records = result.equity_curve.to_dict('records') if getattr(result, 'equity_curve', None) is not None else []
            if equity_records:
                equity_dates = []
                for item in equity_records:
                    d = item.get("date")
                    if d:
                        equity_dates.append(_parse_date_compat(d))
                if equity_dates:
                    actual_start_date = min(equity_dates)
                    actual_end_date = max(equity_dates)
        except Exception:
            # 回退使用用户输入区间
            pass

        # 创建回测结果记录
        db_result = PVFRSBacktestResult(
            task_id=task_id,
            stock_code=result.stock_code,
            market=result.market_type,
            backtest_date=datetime.now().date(),
            start_date=actual_start_date,
            end_date=actual_end_date,
            initial_capital=float(result.initial_capital),
            final_capital=float(result.final_capital),
            total_return=float(result.total_return),
            annual_return=float(result.annual_return),
            max_drawdown=float(result.max_drawdown),
            sharpe_ratio=float(result.sharpe_ratio),
            win_rate=float(result.win_rate),
            profit_factor=float(result.profit_factor),
            total_trades=int(result.total_trades),
            avg_holding_period=float(result.avg_holding_period)
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        
        # 保存交易记录
        for trade in result.trades:
            trade_record = PVFRSTradeRecord(
                result_id=db_result.id,
                stock_code=result.stock_code,
                market=result.market_type,
                entry_date=_parse_date_compat(trade.entry_date),
                exit_date=_parse_date_compat(trade.exit_date),
                entry_price=float(trade.entry_price),
                exit_price=float(trade.exit_price),
                pnl=float(trade.pnl),
                pnl_percent=float(trade.pnl_percent),
                exit_reason=trade.exit_reason
            )
            db.add(trade_record)
        
        # 保存收益曲线
        for item in result.equity_curve.to_dict('records'):
            curve_record = PVFRSEquityCurve(
                result_id=db_result.id,
                stock_code=result.stock_code,
                market=result.market_type,
                curve_date=_parse_date_compat(item["date"]),
                equity=float(item["equity"])
            )
            db.add(curve_record)
        
        db.commit()
        print(f"成功保存回测结果到数据库: {result.stock_code}")
        
    except Exception as e:
        db.rollback()
        print(f"保存回测结果到数据库失败: {e}")

def save_batch_results_to_db(task_id: str, results: List, request: BacktestRequest, db: Session):
    """保存批量回测结果到数据库"""
    try:
        for result in results:
            if result:  # 跳过None结果
                save_result_to_db(f"{task_id}_{result.stock_code}", result, request, db)
        print(f"成功保存批量回测结果到数据库: {len(results)} 个结果")
        
    except Exception as e:
        print(f"保存批量回测结果到数据库失败: {e}")

def save_optimization_result_to_db(task_id: str, optimization_result: Dict, request: BacktestRequest, db: Session):
    """保存参数优化结果到数据库"""
    try:
        # 保存最佳结果
        if optimization_result.get("best_result"):
            best = optimization_result["best_result"]
            save_result_to_db(f"{task_id}_best", best, request, db)
        print(f"成功保存优化结果到数据库")
        
    except Exception as e:
        print(f"保存优化结果到数据库失败: {e}")

def get_backtest_results_from_db(db: Session) -> List[Dict]:
    """从数据库获取回测结果"""
    try:
        # 查询所有回测结果
        results = db.query(PVFRSBacktestResult).order_by(PVFRSBacktestResult.created_at.desc()).all()
        
        result_list = []
        for result in results:
            # 获取交易记录
            trades = db.query(PVFRSTradeRecord).filter(
                PVFRSTradeRecord.result_id == result.id
            ).all()
            
            # 获取收益曲线
            equity_curve = db.query(PVFRSEquityCurve).filter(
                PVFRSEquityCurve.result_id == result.id
            ).order_by(PVFRSEquityCurve.curve_date.asc()).all()
            
            result_data = {
                "id": result.task_id,
                "code": result.stock_code,
                "market": result.market,
                "date": result.backtest_date.strftime('%Y-%m-%d'),
                "start_date": result.start_date.strftime('%Y-%m-%d'),
                "end_date": result.end_date.strftime('%Y-%m-%d'),
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
                "total_return": result.total_return,
                "annual_return": result.annual_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
                "avg_holding_period": result.avg_holding_period,
                "trades": [
                    {
                        "entryDate": trade.entry_date.strftime('%Y-%m-%d'),
                        "exitDate": trade.exit_date.strftime('%Y-%m-%d'),
                        "entryPrice": trade.entry_price,
                        "exitPrice": trade.exit_price,
                        "pnl": trade.pnl,
                        "pnlPercent": trade.pnl_percent,
                        "exitReason": trade.exit_reason
                    }
                    for trade in trades
                ],
                "equity_curve": [
                    {
                        "date": item.curve_date.strftime('%Y-%m-%d'),
                        "equity": item.equity
                    }
                    for item in equity_curve
                ]
            }
            result_list.append(result_data)
        
        return result_list
        
    except Exception as e:
        print(f"从数据库获取回测结果失败: {e}")
        return []

def clear_backtest_results_from_db(db: Session):
    """清空数据库中的回测结果"""
    try:
        # 删除所有相关记录
        db.query(PVFRSEquityCurve).delete()
        db.query(PVFRSTradeRecord).delete()
        db.query(PVFRSBacktestResult).delete()
        db.query(PVFRSBacktestTask).delete()
        db.commit()
        print("成功清空数据库中的回测结果")
        
    except Exception as e:
        db.rollback()
        print(f"清空数据库回测结果失败: {e}")
