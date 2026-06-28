"""
选股策略API路由
提供创业板中线选股策略接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import asyncio
import math
import os
from typing import Optional, Dict, Any, List

# PVFRS 选股为 CPU 密集型，允许较长超时（秒）；Nginx 的 proxy_read_timeout 需 >= 此值
PVFRS_SCREENING_TIMEOUT = 300
# GMS 选股计算量大（全 A 约 6000+ 只），默认 600 秒；生产若仍出现 502，多为网关超时小于此值。
# 环境变量 GMS_SCREENING_TIMEOUT（秒）可覆盖；部署时请同步调大 Nginx location 的 proxy_read_timeout / send_timeout。
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


GMS_SCREENING_TIMEOUT = max(60, _int_env("GMS_SCREENING_TIMEOUT", 600))
VSB_SCREENING_TIMEOUT = max(60, _int_env("VSB_SCREENING_TIMEOUT", 600))

from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from backend_api.auth import SECRET_KEY, ALGORITHM
from backend_api.models import Watchlist, TokenData

from backend_api.database import get_db, SessionLocal
from backend_api.models import MeanFrequencyResonanceIndicators
from .stock_screening import StockScreeningStrategy
from .high_tight_flag_strategy import HighTightFlagStrategy
from .keep_increasing_strategy import KeepIncreasingStrategy
from .long_lower_shadow_strategy import LongLowerShadowStrategy
from .low_nine_strategy import LowNineStrategy
from .one_yang_three_lines_strategy import OneYangThreeLinesStrategy

logger = logging.getLogger(__name__)
logger.info(
    "选股接口超时: PVFRS_SCREENING_TIMEOUT=%ss, GMS_SCREENING_TIMEOUT=%ss, VSB_SCREENING_TIMEOUT=%ss（全A股请保证网关超时≥此值）",
    PVFRS_SCREENING_TIMEOUT,
    GMS_SCREENING_TIMEOUT,
    VSB_SCREENING_TIMEOUT,
)

router = APIRouter(prefix="/api/screening", tags=["screening"])


def _fill_gms_indicator_fallback(db: Session, code: str, target_date: str, market_type: str) -> Optional[Dict[str, Any]]:
    """
    兜底：当 GMS 引擎输出的关键指标字段缺失/为空时，从指标表补齐。
    取 date<=target_date 的最近一条。
    """
    try:
        from sqlalchemy import desc
        row = (
            db.query(MeanFrequencyResonanceIndicators)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date <= str(target_date).strip()[:10],
            )
            .order_by(desc(MeanFrequencyResonanceIndicators.date))
            .first()
        )
        if not row:
            return None
        # 映射到前端需要的字段名（与 screening.js 的列一致）
        delta = getattr(row, "macro_displacement_delta", None)
        d = getattr(row, "ma20_d", None)
        rising_days = getattr(row, "rising_days_z", None)
        falling_days = getattr(row, "falling_days_f", None)
        ratio_d20 = getattr(row, "ratio_d20", None)
        ratio_d1 = getattr(row, "ratio_d1", None)
        instant_deviation = getattr(row, "instant_deviation", None)
        ratio_d = getattr(row, "bias", None)  # Δ20/d
        avg_volume_20d = getattr(row, "mavol20_m", None)  # m
        current_volume = None
        eff_m20_m = getattr(row, "efficiency_m20_minus_m", None)
        try:
            if avg_volume_20d is not None:
                current_volume = float(avg_volume_20d) + float(eff_m20_m or 0)  # m20
        except Exception:
            current_volume = None
        # F/Z
        fz_ratio = None
        try:
            if rising_days and float(rising_days) != 0:
                fz_ratio = float(falling_days or 0) / float(rising_days)
        except Exception:
            fz_ratio = None
        ratio_relative = None
        try:
            if delta is not None and d not in (None, 0):
                ratio_relative = float(delta) / float(d)
        except Exception:
            ratio_relative = None
        return {
            "delta": delta,
            "d_ma20": d,
            "rising_days": rising_days,
            "falling_days": falling_days,
            "ratio_d20": ratio_d20,
            "ratio_d1": ratio_d1,
            "ratio_d": ratio_d,
            "fz_ratio": fz_ratio,
            "ratio_relative": ratio_relative,
            "instant_deviation": instant_deviation,
            "avg_volume_20d": avg_volume_20d,
            "current_volume": current_volume,
        }
    except Exception:
        logger.debug("GMS 指标兜底补全失败 code=%s", code, exc_info=True)
        return None


def _resolve_gms_stock_name(db: Session, code: str, market_type_hint: Optional[str] = None) -> str:
    """
    GMS 列表展示用证券简称：与引擎 market 划分一致——A 股走 stock_basic_info，
    港股走 stock_basic_info_hk，沪深 ETF（如 159xxx/510xxx）走 fund_basic_info。
    """
    code = str(code).strip()
    if not code:
        return "股票"
    mt = (market_type_hint or "").strip().upper()

    from backend_api.models import StockBasicInfo, StockBasicInfoHK, FundBasicInfo

    if mt == "HK":
        info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
        if info and info.name:
            return info.name

    info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
    if not info and code.startswith("SZ"):
        info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code[2:]).first()
    if not info and code.startswith("SH"):
        info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code[2:]).first()
    if info and info.name:
        return info.name

    if mt == "ETF":
        finfo = db.query(FundBasicInfo).filter(FundBasicInfo.code == code).first()
        if finfo and finfo.name:
            return finfo.name

    # 159xxx 等深市 ETF：历史上会被误判进「港股」分支但不在 HK 表，此处统一从基金表兜底
    if len(code) >= 6 and code.isdigit():
        finfo = db.query(FundBasicInfo).filter(FundBasicInfo.code == code).first()
        if finfo and finfo.name:
            return finfo.name

    if len(code) == 5 and code.isdigit():
        info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
        if info and info.name:
            return info.name

    if mt != "HK":
        info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
        if info and info.name:
            return info.name

    return f"股票{code}"


def _fallback_gms_indicator_market_type(symbol: str, scope: str, cn_codes: set) -> str:
    """与 strategy_engine 一致：用于指标表兜底查询的 market_type（CN / ETF / HK）。"""
    s = str(symbol or "").strip()
    if scope == "etf":
        return "ETF"
    if s in cn_codes:
        return "CN"
    if len(s) >= 6 and s.isdigit():
        if s[0] in "6039":
            return "CN"
        if s[0] in "518":
            return "ETF"
        return "HK"
    if len(s) == 5 and s.isdigit():
        return "HK"
    return "CN"


def _gms_strategy_config_meta(config_mgr, config_id: int, config: dict) -> dict:
    """当前 GMS 策略参数版本摘要（供前端得分明细展示）。"""
    row = config_mgr.get_config_row(int(config_id)) if config_id else None
    mechanism = (config.get("scoring") or {}).get("mechanism") or "tiered_dual_max"
    label = mechanism
    try:
        from backend_core.strategies.gms.scoring import get_mechanism_meta

        label = get_mechanism_meta(mechanism).get("label") or mechanism
    except Exception:
        pass
    return {
        "config_id": int(config_id),
        "config_name": (row.name if row else "") or "",
        "scoring_mechanism": mechanism,
        "scoring_mechanism_label": label,
        "strategy_config_id": int(config_id),
        "strategy_config_name": (row.name if row else "") or "",
    }


def _inject_gms_score_detail_meta(sd: Optional[dict], meta: dict) -> dict:
    if not isinstance(sd, dict):
        sd = {}
    for k in (
        "strategy_config_id",
        "strategy_config_name",
        "scoring_mechanism",
        "scoring_mechanism_label",
    ):
        if meta.get(k) is not None and sd.get(k) in (None, ""):
            sd[k] = meta[k]
    return sd


def _fill_gms_score_fallback(db: Session, code: str, target_date: str, market_type: str, config: dict) -> Optional[Dict[str, Any]]:
    """
    兜底：当 score_detail 为空或得分字段缺失时，使用指标表 + 当前配置重新计算得分明细。
    """
    try:
        from sqlalchemy import desc
        from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator
        from backend_core.strategies.gms.signal_detector import GMSSignalDetector
        from backend_core.strategies.gms.data_loader import GMSDataLoader
        from backend_core.strategies.gms.scoring._helpers import resolve_mechanism_id

        date_str = str(target_date).strip()[:10]
        row = (
            db.query(MeanFrequencyResonanceIndicators)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date <= date_str,
            )
            .order_by(desc(MeanFrequencyResonanceIndicators.date))
            .first()
        )
        if not row:
            return None

        # 构造 calculator 需要的 row dict（对齐 GMSDataLoader 输出字段名）
        delta = getattr(row, "macro_displacement_delta", None)
        d = getattr(row, "ma20_d", None)
        mavol20_m = getattr(row, "mavol20_m", None)
        eff_m20_m = getattr(row, "efficiency_m20_minus_m", None)
        current_volume = (float(mavol20_m or 0) + float(eff_m20_m or 0)) if mavol20_m is not None else 0.0
        volume_ratio = (current_volume / float(mavol20_m)) if mavol20_m not in (None, 0) else None

        calc_row = {
            "code": code,
            "date": str(getattr(row, "date", date_str))[:10],
            "market_type": market_type,
            "macro_displacement_delta": delta,
            "ma20_d": d,
            "ratio_d20": getattr(row, "ratio_d20", None),
            "ratio_d1": getattr(row, "ratio_d1", None),
            "instant_deviation": getattr(row, "instant_deviation", None),
            "rising_days_z": getattr(row, "rising_days_z", 0),
            "falling_days_f": getattr(row, "falling_days_f", 0),
            "mavol20_m": mavol20_m,
            "efficiency_m20_minus_m": eff_m20_m,
            "ratio_d": getattr(row, "bias", None),
            "current_volume": current_volume,
            "volume_ratio": volume_ratio,
            "d1": getattr(row, "d1", None),
            "d1_date": getattr(row, "d1_date", None),
            "d20": getattr(row, "d20", None),
            "d20_date": getattr(row, "d20_date", None),
            "ma60_d": getattr(row, "ma60_d", None),
        }
        from backend_core.strategies.gms.ma60_source import enrich_rows_ma60_d

        enrich_rows_ma60_d(db, [calc_row])

        # 站稳 N 日：取最近 N 日的 instant_deviation 序列（最后一项为当日）
        stable_days = int((config.get("scoring") or {}).get("instant_deviation_stable_days", 3) or 3)
        series_rows = (
            db.query(MeanFrequencyResonanceIndicators.instant_deviation)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date <= date_str,
            )
            .order_by(desc(MeanFrequencyResonanceIndicators.date))
            .limit(max(1, stable_days))
            .all()
        )
        series = [float(r[0]) for r in reversed(series_rows) if r and r[0] is not None]  # 升序，末尾为当日
        ind = GMSIndicatorsCalculator(config).calculate(calc_row, instant_deviation_series=series if series else None)
        if not ind:
            return None

        detector = GMSSignalDetector(config)
        left = detector.detect_left_buy(ind)
        right = detector.detect_right_buy(ind)
        sell = detector.detect_sell(ind)
        buy_type_fb = "左侧" if left else ("右侧" if right else "")

        # 复用 strategy_engine 的 score_detail 结构（前端得分明细依赖这些 key）
        calculator = GMSIndicatorsCalculator(config)
        score_detail = {
            "score_accumulation": ind.score_accumulation,
            "score_balance": ind.score_balance,
            "score_momentum": ind.score_momentum,
            "score_total": ind.score_total,
            "accumulation_grade": getattr(ind, "accumulation_grade", ""),
            "momentum_grade": getattr(ind, "momentum_grade", ""),
            "accumulation_fz_min": calculator.accumulation_fz_min,
            "balance_ratio_max": calculator.balance_ratio_max,
            "momentum_volume_ratio_min": calculator.momentum_volume_ratio_min,
            "accumulation_s_threshold": calculator.acc_s_threshold,
            "accumulation_a_threshold": calculator.acc_a_threshold,
            "momentum_full_threshold": calculator.mom_full_threshold,
            "momentum_batch_threshold": calculator.mom_batch_threshold,
            "score_acc_fz": getattr(ind, "score_acc_fz", 0),
            "score_acc_balance": getattr(ind, "score_acc_balance", 0),
            "score_acc_volume": getattr(ind, "score_acc_volume", 0),
            "score_mom_ratio_d1": getattr(ind, "score_mom_ratio_d1", 0),
            "score_mom_deviation": getattr(ind, "score_mom_deviation", 0),
            "score_mom_volume": getattr(ind, "score_mom_volume", 0),
            "acc_fz_tiers": calculator.acc_fz_tiers,
            "balance_tiers": calculator.balance_tiers,
            "vol_shrink_tiers": calculator.vol_shrink_tiers,
            "ratio_d1_tiers": calculator.ratio_d1_tiers,
            "vol_attack_tiers": calculator.vol_attack_tiers,
            "weight_acc_fz": calculator.weight_acc_fz,
            "weight_acc_balance": calculator.weight_acc_balance,
            "weight_acc_volume": calculator.weight_acc_volume,
            "weight_mom_ratio_d1": calculator.weight_mom_ratio_d1,
            "weight_mom_deviation": calculator.weight_mom_deviation,
            "weight_mom_volume": calculator.weight_mom_volume,
            "acc_fz_judge": getattr(ind, "acc_fz_judge", ""),
            "acc_balance_judge": getattr(ind, "acc_balance_judge", ""),
            "acc_volume_judge": getattr(ind, "acc_volume_judge", ""),
            "mom_ratio_d1_judge": getattr(ind, "mom_ratio_d1_judge", ""),
            "mom_deviation_judge": getattr(ind, "mom_deviation_judge", ""),
            "mom_volume_judge": getattr(ind, "mom_volume_judge", ""),
            "delta": ind.delta,
            "d": ind.d,
            "d20": ind.d + ind.instant_deviation,
            "d1": ind.d + ind.instant_deviation - ind.delta,
            "d1_date": (ind.raw_row.get("d1_date") if ind.raw_row else None) or None,
            "d20_date": (ind.raw_row.get("d20_date") if ind.raw_row else None) or ind.date,
            "ratio_d20": ind.ratio_d20,
            "ratio_d1": ind.ratio_d1,
            "ratio_d": ind.ratio_d,
            "rising_days": ind.rising_days,
            "falling_days": ind.falling_days,
            "avg_volume_20d": ind.avg_volume_20d,
            "current_volume": ind.current_volume,
            "volume_ratio": ind.volume_ratio,
            "fz_ratio": ind.fz_ratio,
            "instant_deviation": ind.instant_deviation,
            "ma60_d": calc_row.get("ma60_d"),
            "scoring_mechanism": getattr(ind, "scoring_mechanism", "") or resolve_mechanism_id(config),
            "score_base_total": getattr(ind, "score_base_total", ind.score_total),
            "score_penalty_deduction": getattr(ind, "score_penalty_deduction", 0.0),
            "penalties": getattr(ind, "penalty_details", []) or [],
        }

        return {
            "score_total": ind.score_total,
            "score_accumulation": ind.score_accumulation,
            "score_momentum": ind.score_momentum,
            "accumulation_grade": getattr(ind, "accumulation_grade", ""),
            "momentum_grade": getattr(ind, "momentum_grade", ""),
            "score_detail": score_detail,
            "left_buy_signal": left,
            "right_buy_signal": right,
            "sell_signal": sell,
            "buy_type": buy_type_fb,
            # 同时补齐顶层关键指标，避免表格列仍为 --
            "delta": ind.delta,
            "d_ma20": ind.d,
            "rising_days": ind.rising_days,
            "falling_days": ind.falling_days,
            "ratio_d20": ind.ratio_d20,
            "ratio_d1": ind.ratio_d1,
            "fz_ratio": ind.fz_ratio,
        }
    except Exception:
        logger.debug("GMS 得分兜底计算失败 code=%s", code, exc_info=True)
        return None

# OAuth2 scheme (optional auth)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# 添加调试日志
logger.info("stock_screening_routes.py 模块加载完成，开始注册路由...")
print("[DEBUG] stock_screening_routes.py 模块加载完成")

# 尝试导入PVFRS前端接口与配置
try:
    from backend_core.strategies.pvfrs.frontend_interface import create_frontend_interface
    from backend_core.strategies.pvfrs.config import PVFRSConfigManager
    from backend_core.strategies.pvfrs.pvfrs_system import PVFRSSystem
    print(" DEBUG: PVFRS前端接口导入成功")
    logger.info("PVFRS前端接口导入成功")
    PVFRS_AVAILABLE = True
except Exception as e:
    print(f"🔧 DEBUG: PVFRS前端接口导入失败: {e}")
    logger.error(f"PVFRS前端接口导入失败: {e}")
    PVFRS_AVAILABLE = False

# 尝试导入 GMS 前端接口
try:
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface
    from backend_core.strategies.gms.config import GMSConfigManager as GMSConfigManagerCls
    GMS_AVAILABLE = True
except Exception as e:
    print(f"GMS 前端接口导入失败: {e}")
    logger.warning(f"GMS 前端接口导入失败: {e}")
    GMS_AVAILABLE = False

try:
    from backend_core.strategies.volume_shrink_breakout import VolumeShrinkBreakoutFrontendInterface

    VSB_AVAILABLE = True
except Exception as e:
    VolumeShrinkBreakoutFrontendInterface = None  # type: ignore
    VSB_AVAILABLE = False
    logger.warning("VSB 策略模块导入失败: %s", e)

# PVFRS 策略参数（供选股界面显示与编辑）
PVFRS_PARAM_KEYS = [
    "observation_period", "buy_ratio_d20_max", "buy_exclude_sideways",
    "amplitude_flat_threshold", "buy_macro_displacement_min", "buy_instant_deviation_min",
    "buy_bias_min", "buy_relative_displacement_min",
]


@router.get("/pvfrs-params")
async def get_pvfrs_params():
    """获取 PVFARS 选股策略参数（供前端显示与编辑）"""
    if not PVFRS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "PVFARS 暂不可用", "data": {}}
        )
    try:
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        config = config_manager.get_current_config()
        params = {k: config.get(k) for k in PVFRS_PARAM_KEYS if k in config}
        params.setdefault("observation_period", 20)
        params.setdefault("buy_ratio_d20_max", 0.5)
        params.setdefault("buy_exclude_sideways", True)
        params.setdefault("amplitude_flat_threshold", 1e-6)
        params.setdefault("buy_macro_displacement_min", 0)
        params.setdefault("buy_instant_deviation_min", 0)
        params.setdefault("buy_bias_min", 0.02)
        params.setdefault("buy_relative_displacement_min", 0.05)
        return JSONResponse({"success": True, "data": params})
    except Exception as e:
        logger.exception("获取 PVFRS 参数失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e), "data": {}}
        )


@router.post("/pvfrs-params")
async def save_pvfrs_params(body: Dict[str, Any] = Body(...)):
    """保存 PVFARS 选股策略参数"""
    if not PVFRS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "PVFARS 暂不可用"}
        )
    try:
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        updates = {k: v for k, v in body.items() if k in PVFRS_PARAM_KEYS}
        if not updates:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "无有效参数"}
            )
        config_manager.update_config(updates)
        return JSONResponse({"success": True, "message": "参数已保存"})
    except Exception as e:
        logger.exception("保存 PVFRS 参数失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )


# PVFRS 路由定义
print("[DEBUG] 即将定义 /pvfrs-strategy 路由")
@router.get("/pvfrs-strategy")
async def get_pvfrs_strategy(
    date: str = Query(None, description="目标日期，格式：YYYY-MM-DD，不提供则使用当前日期"),
    limit: int = Query(None, ge=1, description="最大返回结果数量，不限制则返回所有符合条件的股票"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值，默认0.3"),
    scope: str = Query("all", description="股票范围：all(全部), watchlist(自选)"),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
):
    """PVFARS量价频幅度共振策略选股"""
    print(f"🔧 DEBUG: PVFRS路由被调用 - 日期: {date}, 限制: {limit}, 最低强度: {min_strength}")
    logger.info(f"开始执行PVFARS策略选股 - 日期: {date or '当前'}, 限制: {limit}, 最低强度: {min_strength}")
    
    # 检查PVFRS是否可用
    if not PVFRS_AVAILABLE:
        logger.error("PVFRS前端接口不可用")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "PVFARS策略暂时不可用，请稍后重试",
                "error": "PVFARS frontend interface not available",
                "data": []
            }
        )
    
    try:
        
        # 参数验证
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="日期格式错误，应为 YYYY-MM-DD"
                )
        
        # 加载策略配置并创建前端接口（使选股使用当前保存的 PVFRS 参数）
        config_manager = PVFRSConfigManager()
        config_manager.load_config()
        config = config_manager.get_current_config()
        pvfrs_system = PVFRSSystem(config)
        frontend_interface = create_frontend_interface(pvfrs_system=pvfrs_system)
        
        # 设置选股配置：【我的自选】时返回全部筛选结果（含信号强度30%以下），其他范围使用传入的最低强度
        effective_min_strength = 0.0 if scope == 'watchlist' else min_strength
        if limit is not None:
            frontend_interface.set_selection_config(max_results=limit, min_strength=effective_min_strength)
        else:
            frontend_interface.set_selection_config(max_results=10000, min_strength=effective_min_strength)
        
        # 获取选股结果
        stock_pool = None
        market = 'all'  # 默认为全部（A股+港股）
        
        # 处理不同的 scope
        if scope == 'watchlist':
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="查看自选股需要登录",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            try:
                # 验证 token
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username: str = payload.get("sub")
                if username is None:
                    raise HTTPException(status_code=401, detail="无效的认证凭据")
                
                # 获取用户信息
                from backend_api.models import User
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    raise HTTPException(status_code=401, detail="用户不存在")
                
                # 查询自选股
                watchlist_items = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
                if not watchlist_items:
                    # 如果自选股为空，直接返回空结果
                    return JSONResponse({
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": date or datetime.now().strftime("%Y-%m-%d"),
                        "strategy_name": "PVFARS量价频幅度共振策略",
                        "scope": "watchlist",
                        "message": "您的自选股列表为空"
                    })
                
                stock_pool = [item.stock_code for item in watchlist_items]
                logger.info(f"用户 {username} 请求筛选自选股，共 {len(stock_pool)} 只")
                
            except JWTError:
                raise HTTPException(status_code=401, detail="无效的认证凭据")
        elif scope in ['cn', 'hk', 'all']:
            # 设置市场范围
            market = scope
            logger.info(f"请求筛选市场: {market}")
        else:
            # 兼容旧版本，如果传入的是其他值，默认也作为 'all' 处理
            market = 'all'
            logger.info(f"未知 scope '{scope}'，默认使用 'all'")
        
        # 选股为 CPU 密集型同步调用，放入线程池执行并设置超时，避免阻塞事件循环与网关超时
        loop = asyncio.get_event_loop()
        def _run_screening():
            return frontend_interface.get_selection_results(date, stock_pool=stock_pool, market=market)
        try:
            selection_results = await asyncio.wait_for(
                loop.run_in_executor(None, _run_screening),
                timeout=PVFRS_SCREENING_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"PVFARS选股超时({PVFRS_SCREENING_TIMEOUT}s)，scope={scope}")
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": f"选股计算超时（超过{PVFRS_SCREENING_TIMEOUT}秒），请缩小范围（如先选 A股 或 港股）或稍后重试",
                    "data": []
                }
            )
        
        # 批量获取实时行情数据（用于获取当前价格和涨跌幅）
        from backend_api.models import StockRealtimeQuote, StockRealtimeQuoteHK, HistoricalQuotes
        from sqlalchemy import func
        import pandas as pd
        
        # 获取所有股票代码
        stock_codes = [result.symbol for result in selection_results]
        
        # 从历史行情数据库获取最新日期（用于查询PVFRS指标数据）
        # 查询 historical_quotes 表中的最新日期
        try:
            latest_date_result = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest_date_result:
                # 将日期转换为字符串格式 YYYY-MM-DD（与PVFRS指标表中的date格式一致）
                if isinstance(latest_date_result, str):
                    target_date = latest_date_result.strip()
                elif hasattr(latest_date_result, 'strftime'):
                    # date 对象
                    target_date = latest_date_result.strftime("%Y-%m-%d")
                else:
                    # 其他类型，尝试转换为字符串
                    target_date = str(latest_date_result).strip()
                logger.info(f"[DEBUG] 从历史行情数据库获取最新日期: {target_date} (用于查询PVFRS指标数据)")
            else:
                # 如果历史行情表中没有数据，使用传入的日期或当前日期
                target_date = date or datetime.now().strftime("%Y-%m-%d")
                logger.warning(f"[WARNING] 历史行情数据库中没有数据，使用日期: {target_date}")
        except Exception as e:
            # 如果查询失败，使用传入的日期或当前日期
            target_date = date or datetime.now().strftime("%Y-%m-%d")
            logger.error(f"[ERROR] 查询历史行情数据库最新日期失败: {str(e)}，使用日期: {target_date}")
        
        # 初始化结果数据列表（提前定义，避免后续使用时未定义错误）
        results_data = []
        
        # 批量查询PVFRS指标数据（价格维度和频率维度）
        # 注意：CN和HK数据在同一张表中，不需要区分market_type
        pvfrs_indicators_map = {}  # {stock_code: {price_dim: ..., freq_dim: ...}}
        if stock_codes:
            # 确保日期格式正确（去除可能的空格）
            target_date_clean = target_date.strip()
            
            # 批量查询所有股票的PVFRS指标（不区分市场类型）
            pvfrs_indicators = db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code.in_(stock_codes),
                MeanFrequencyResonanceIndicators.date == target_date_clean
            ).all()
            
            for indicator in pvfrs_indicators:
                pvfrs_indicators_map[indicator.code] = {
                    'macro_displacement_delta': indicator.macro_displacement_delta,
                    'ratio_d20': getattr(indicator, 'ratio_d20', None),
                    'ratio_d1': getattr(indicator, 'ratio_d1', None),
                    'rising_days_z': indicator.rising_days_z,
                    'falling_days_f': indicator.falling_days_f,
                    'market_type': indicator.market_type
                }
            
            logger.info(f"[DEBUG] 从PVFRS指标表查询数据: 目标日期='{target_date_clean}', 查询到{len(pvfrs_indicators)}条记录, "
                      f"股票代码={stock_codes[:5] if len(stock_codes) > 5 else stock_codes}...")  # 只显示前5个代码
            
            # 详细日志：显示前几条查询结果
            if len(pvfrs_indicators) > 0 and len(results_data) == 0:  # 只在第一次循环时显示
                for idx, ind in enumerate(pvfrs_indicators[:3]):
                    logger.info(f"[DEBUG] 查询结果示例 {idx+1}: 代码={ind.code}, 日期={ind.date}, 市场类型={ind.market_type}, "
                              f"上涨天数={ind.rising_days_z}, 下跌天数={ind.falling_days_f}")
            
            # 检查是否有股票在数据库中找不到数据
            missing_codes = [code for code in stock_codes if code not in pvfrs_indicators_map]
            if missing_codes and len(missing_codes) <= 10:  # 如果缺失的股票不多，记录日志
                logger.warning(f"[DEBUG] 以下股票在PVFRS指标表中未找到数据 (日期={target_date_clean}): {missing_codes}")
        
        if stock_codes:
            # 获取最新交易日期
            latest_date_result = pd.read_sql_query("""
                SELECT MAX(trade_date) as latest_date 
                FROM stock_realtime_quote 
                WHERE change_percent IS NOT NULL
            """, db.bind)
            
            latest_trade_date = None
            if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
                latest_trade_date = latest_date_result.iloc[0]['latest_date']
            
            # 批量查询实时行情（A股）
            realtime_quotes_a = {}
            if latest_trade_date:
                quotes_a = db.query(StockRealtimeQuote).filter(
                    StockRealtimeQuote.code.in_(stock_codes),
                    StockRealtimeQuote.trade_date == latest_trade_date
                ).all()
                realtime_quotes_a = {q.code: q for q in quotes_a}
            
            # 批量查询实时行情（港股）
            hk_codes = [code for code in stock_codes if (len(code) <= 5 and code.isdigit()) or (code.startswith('0') and len(code) == 5)]
            realtime_quotes_hk = {}
            if hk_codes and latest_trade_date:
                quotes_hk = db.query(StockRealtimeQuoteHK).filter(
                    StockRealtimeQuoteHK.code.in_(hk_codes),
                    StockRealtimeQuoteHK.trade_date == latest_trade_date
                ).all()
                realtime_quotes_hk = {q.code: q for q in quotes_hk}
        else:
            realtime_quotes_a = {}
            realtime_quotes_hk = {}
        
        # 转换为API响应格式（results_data已在上面初始化）
        for result in selection_results:
            result_dict = result.to_dict()
            
            # 确保股票名称字段是真实的真实名称
            current_name = result_dict.get('name', '')
            if not current_name or current_name.startswith('股票'):
                # 如果没有名称字段、名称为空，或者名称是以"股票"开头的默认值，尝试从数据库查询真实名称
                from backend_api.models import StockBasicInfo, StockBasicInfoHK
                
                # 清理股票代码格式
                stock_code = str(result.symbol).strip()
                
                # 尝试多种查询方式
                stock_info = None
                
                # 1. 判断是否为港股 (通常是5位数字，如 00700)
                is_hk = False
                if len(stock_code) <= 5 and stock_code.isdigit():
                    is_hk = True
                elif not (stock_code.startswith('6') or stock_code.startswith('0') or stock_code.startswith('3') or 
                          stock_code.startswith('SZ') or stock_code.startswith('SH')):
                    is_hk = True
                
                if is_hk:
                    # 查询港股基础信息
                    stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == stock_code).first()
                    # 如果没找到且代码长度小于5，尝试补全为5位
                    if not stock_info and len(stock_code) < 5:
                        padded_code = stock_code.zfill(5)
                        stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == padded_code).first()
                else:
                    # 查询A股基础信息
                    # 方式1：直接查询
                    stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == stock_code).first()
                    
                    # 方式2：如果失败，尝试去掉SZ前缀
                    if not stock_info and stock_code.startswith('SZ'):
                        clean_code = stock_code[2:]
                        stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == clean_code).first()
                    
                    # 方式3：如果失败，尝试去掉SH前缀
                    if not stock_info and stock_code.startswith('SH'):
                        clean_code = stock_code[2:]
                        stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == clean_code).first()
                
                if stock_info and stock_info.name:
                    result_dict['name'] = stock_info.name
                    logger.debug(f"[DEBUG] 从数据库查询真实name: {stock_code} -> {stock_info.name}")
                else:
                    # 如果数据库中也没有，保留原样或使用股票代码作为名称
                    if not result_dict.get('name'):
                        result_dict['name'] = f"股票{stock_code}"
                    logger.warning(f"[WARNING] 无法找到股票真实名称，代码: {stock_code}")
            
            # 调试日志：检查name字段
            if len(results_data) < 3:  # 只打印前3条数据
                logger.info(f"[DEBUG] 股票 {result.symbol} 的name字段: '{result_dict.get('name', 'MISSING')}'")
            
            # 提取指标信息
            indicators = result_dict.get('indicators', {})
            
            # 从 resonance_analysis.details 中获取维度信息
            resonance_analysis = indicators.get('resonance_analysis', {})
            resonance_details = resonance_analysis.get('details', {})
            
            # 调试日志：输出指标结构信息
            if len(results_data) < 1:  # 只打印第一条数据的调试信息，避免日志过多
                logger.info(f"[DEBUG] resonance_details keys: {list(resonance_details.keys())}")
                logger.info(f"[DEBUG] indicators keys: {list(indicators.keys())}")
            
            # 优先从 resonance_analysis.details 中获取，如果不存在则从顶层 indicators 中获取
            price_indicators = resonance_details.get('price_indicators') or indicators.get('price_dimension') or {}
            frequency_indicators = resonance_details.get('frequency_indicators') or indicators.get('frequency_dimension') or {}
            volume_indicators = resonance_details.get('volume_indicators') or indicators.get('volume_dimension') or {}
            
            # log debug info if still empty
            if not price_indicators:
                logger.debug(f"Stock {result.symbol} missing price_indicators")
            entry_timing_analysis = indicators.get('entry_timing_analysis', {})
            
            # 从PVFRS指标数据表中获取价格维度和频率维度数据
            stock_code = result.symbol
            pvfrs_data = pvfrs_indicators_map.get(stock_code)
            
            # 价格维度状态 - 位移幅度数据（|Δ|、Δ/d₂₀、Δ/d₁、横盘）
            parts = []
            ampl = price_indicators.get('amplitude') if price_indicators and isinstance(price_indicators, dict) else None
            if ampl is not None:
                parts.append(f"位移幅度: {float(ampl):.2f}")
            rd20 = None
            if price_indicators and isinstance(price_indicators, dict) and price_indicators.get('ratio_d20') is not None:
                rd20 = price_indicators['ratio_d20']
            elif pvfrs_data and pvfrs_data.get('ratio_d20') is not None:
                rd20 = pvfrs_data['ratio_d20']
            if rd20 is not None:
                parts.append(f"Δ/d₂₀: {float(rd20) * 100:.2f}%")
            rd1 = None
            if price_indicators and isinstance(price_indicators, dict) and price_indicators.get('ratio_d1') is not None:
                rd1 = price_indicators['ratio_d1']
            elif pvfrs_data and pvfrs_data.get('ratio_d1') is not None:
                rd1 = pvfrs_data['ratio_d1']
            if rd1 is not None:
                parts.append(f"Δ/d₁: {float(rd1) * 100:.2f}%")
            sideways = price_indicators.get('is_sideways') if price_indicators and isinstance(price_indicators, dict) else None
            if sideways is not None:
                parts.append(f"横盘: {'是' if sideways else '否'}")
            price_dimension_status = " | ".join(parts) if parts else "--"
            
            # 频率维度状态 - 从PVFRS指标表获取（优先使用数据库数据）
            if pvfrs_data:
                # 注意：0 是有效值，不能使用 or 0，应该使用 is not None 判断
                rising_days_z = pvfrs_data.get('rising_days_z')
                falling_days_f = pvfrs_data.get('falling_days_f')
                
                if rising_days_z is not None and falling_days_f is not None:
                    # 使用数据库中的值（强制使用，不使用策略分析的值）
                    rising_days = int(rising_days_z)
                    falling_days = int(falling_days_f)
                    frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    
                    # 调试日志：对比数据库值和策略分析值
                    if len(results_data) < 3:  # 只打印前3条数据的调试信息
                        strategy_rising = frequency_indicators.get('rising_days') if frequency_indicators else None
                        strategy_falling = frequency_indicators.get('falling_days') if frequency_indicators else None
                        logger.info(f"[DEBUG] 股票 {stock_code} 频率维度 - 使用数据库值: 上涨{rising_days}天/下跌{falling_days}天, "
                                  f"策略分析值: 上涨{strategy_rising}天/下跌{strategy_falling}天, "
                                  f"目标日期: {target_date}")
                else:
                    # 如果数据库中有记录但字段为None，记录警告并尝试使用策略分析值
                    logger.warning(f"股票 {stock_code} 在PVFRS指标表中存在记录，但上涨/下跌天数字段为None，尝试使用策略分析值")
                    if frequency_indicators and isinstance(frequency_indicators, dict) and frequency_indicators:
                        rising_days = frequency_indicators.get('rising_days', 0) or 0
                        falling_days = frequency_indicators.get('falling_days', 0) or 0
                        frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    else:
                        frequency_dimension_status = "--"
            else:
                # 如果PVFRS表中没有数据，尝试从策略分析结果中获取（向后兼容）
                if frequency_indicators and isinstance(frequency_indicators, dict) and frequency_indicators:
                    rising_days = frequency_indicators.get('rising_days', 0) or 0
                    falling_days = frequency_indicators.get('falling_days', 0) or 0
                    frequency_dimension_status = f"上涨{rising_days}天/下跌{falling_days}天"
                    
                    # 调试日志：记录使用策略分析值的情况（重要警告）
                    if len(results_data) < 3:
                        logger.warning(f"[WARNING] 股票 {stock_code} 在PVFRS指标表中未找到数据 (日期={target_date})，使用策略分析值: "
                                     f"上涨{rising_days}天/下跌{falling_days}天。请检查数据库中是否有该股票该日期的数据。")
                else:
                    frequency_dimension_status = "--"
            
            # 成交量维度状态 - 显示实际数值
            if volume_indicators and isinstance(volume_indicators, dict) and volume_indicators:
                efficiency_ratio = volume_indicators.get('efficiency_ratio', 0) or 0
                # 显示效率比
                volume_dimension_status = f"效率比: {efficiency_ratio:.2f}"
            else:
                volume_dimension_status = "--"
            
            # 获取条件验证信息
            conditions_met = result_dict.get('conditions_met', {})
            
            # 共振状态
            resonance_detected = conditions_met.get("resonance_detected", False)
            three_dimension_resonance = conditions_met.get("three_dimension_resonance", False)
            if three_dimension_resonance or resonance_detected:
                resonance_status = "三维共振"
            elif conditions_met.get("price_dimension_met", False) and \
                 (conditions_met.get("frequency_dimension_met", False) or conditions_met.get("volume_dimension_met", False)):
                resonance_status = "部分共振"
            else:
                resonance_status = "--"
            
            # 入场时机状态（从 entry_timing_analysis 中提取）
            entry_timing_status = "--"
            if entry_timing_analysis and isinstance(entry_timing_analysis, dict):
                comprehensive_assessment = entry_timing_analysis.get('comprehensive_assessment', {})
                if comprehensive_assessment and isinstance(comprehensive_assessment, dict):
                    timing_score = comprehensive_assessment.get('score', 0)
                    optimal_timing = comprehensive_assessment.get('optimal_timing', False)
                    good_timing = comprehensive_assessment.get('good_timing', False)
                    
                    if optimal_timing:
                        entry_timing_status = f"最佳时机({timing_score:.2f})"
                    elif good_timing:
                        entry_timing_status = f"良好时机({timing_score:.2f})"
                    elif timing_score > 0:
                        entry_timing_status = f"评分:{timing_score:.2f}"
                else:
                    # 尝试直接获取评分
                    timing_score = entry_timing_analysis.get('timing_score', 0)
                    if timing_score > 0:
                        entry_timing_status = f"评分:{timing_score:.2f}"
            
            # 如果没有从 entry_timing_analysis 中获取到，尝试从 conditions_met 中获取
            if entry_timing_status == "--":
                entry_timing_met = conditions_met.get("entry_timing_optimized", False)
                if entry_timing_met:
                    entry_timing_status = "满足"
                else:
                    entry_timing_status = "--"
            
            # 获取当前价格和涨跌幅（从实时行情表）
            current_price = result_dict.get('price', None)  # 先使用历史数据中的价格
            change_percent = None
            
            # 优先从实时行情表获取
            realtime_quote = realtime_quotes_a.get(stock_code) or realtime_quotes_hk.get(stock_code)
            if realtime_quote:
                if hasattr(realtime_quote, 'current_price') and realtime_quote.current_price:
                    current_price = float(realtime_quote.current_price)
                if hasattr(realtime_quote, 'change_percent') and realtime_quote.change_percent is not None:
                    change_percent = float(realtime_quote.change_percent)
            
            # 投资建议（从 indicators 中提取）
            investment_advice_dict = indicators.get('investment_advice', {})
            if isinstance(investment_advice_dict, dict):
                investment_advice = investment_advice_dict.get('recommendation', '--')
                # 如果是英文，转换为中文
                if investment_advice == 'BUY':
                    investment_advice = '买入'
                elif investment_advice == 'HOLD':
                    investment_advice = '持有'
                elif investment_advice == 'WAIT':
                    investment_advice = '等待'
                elif investment_advice == 'SELL':
                    investment_advice = '卖出'
            else:
                investment_advice = "--"
            
            # 得分明细（供前端展示：共振强度、各维度得分）
            score_detail = indicators.get("score_detail", {})
            if not score_detail and resonance_analysis:
                resonance_details = resonance_analysis.get("details", {})
                dim_scores = resonance_details.get("dimension_scores", resonance_details.get("dimension_scores") or {})
                if isinstance(dim_scores, dict):
                    score_detail = {
                        "resonance_strength": resonance_analysis.get("resonance_strength") or resonance_details.get("resonance_strength"),
                        "price_score": dim_scores.get("price_score"),
                        "frequency_score": dim_scores.get("frequency_score"),
                        "volume_score": dim_scores.get("volume_score"),
                    }
            
            # 添加选股策略特有的字段
            result_dict.update({
                "strategy_type": "PVFARS",
                "signal_date": date or datetime.now().strftime("%Y-%m-%d"),
                # 添加前端期望的字段
                "current_price": current_price,  # 使用从实时行情表获取的价格
                "price_dimension_status": price_dimension_status,
                "frequency_dimension_status": frequency_dimension_status,
                "volume_dimension_status": volume_dimension_status,
                "resonance_status": resonance_status,
                "entry_timing_status": entry_timing_status,
                "investment_advice": investment_advice,
                "current_change_percent": change_percent if change_percent is not None else 0.0,  # 添加当前涨跌幅（前端期望的字段名）
                "score_detail": score_detail,  # 得分明细：共振强度、价格/频率/成交量维度得分
                # 保留原有的 analysis_dimensions 字段
                "analysis_dimensions": {
                    "price_dimension": conditions_met.get("price_dimension_met", False),
                    "frequency_dimension": conditions_met.get("frequency_dimension_met", False),
                    "volume_dimension": conditions_met.get("volume_dimension_met", False),
                    "resonance_detected": resonance_detected
                }
            })
            results_data.append(result_dict)
        
        logger.info(f"PVFARS策略选股执行完成，找到 {len(results_data)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results_data,
            "total": len(results_data),
            "search_date": date or datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "PVFARS量价频幅度共振策略",
            "parameters": {
                "limit": limit or "无限制",
                "min_strength": min_strength,
                "scope": scope
            }
        })
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"执行PVFARS策略选股失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PVFARS策略选股执行失败: {str(e)}"
        )
print("[DEBUG] /pvfrs-strategy 路由定义完成")

# 添加一个简单的测试路由
@router.get("/test-pvfrs")
async def test_pvfrs():
    """测试PVFRS路由是否工作"""
    return JSONResponse({
        "success": True,
        "message": "PVFRS测试路由工作正常",
        "pvfrs_available": PVFRS_AVAILABLE
    })


def _normalize_stock_code_for_gms_pool(c: str) -> str:
    """与自选股池一致：归一化代码以便匹配指标表（A 股 6 位、港股 5 位等）。"""
    s = str(c).strip()
    if not s:
        return s
    if s.isdigit():
        if len(s) == 6 and s[0] in "603":
            return s.zfill(6)
        if len(s) <= 5:
            return s.zfill(5)
        return s.zfill(6)
    return s


def _normalize_gms_board_codes(
    raw: Optional[List[str]],
    *,
    upper: bool = False,
) -> List[str]:
    """解析 GMS 行业/概念板块代码列表（支持重复 query 参数或逗号分隔）。"""
    if not raw:
        return []
    out: List[str] = []
    for item in raw:
        for part in str(item or "").split(","):
            code = part.strip()
            if not code:
                continue
            if upper:
                code = code.upper()
            if code not in out:
                out.append(code)
    return out


def _resolve_gms_stock_code_from_input(db: Session, raw: str) -> Optional[str]:
    """
    将用户输入的代码或名称解析为 GMS 可用的证券代码。
    支持 6 位 A 股、5 位港股、SH/SZ 前缀及简称/代码模糊匹配。
    """
    s = str(raw or "").strip()
    if not s:
        return None
    upper = s.upper()
    if upper.startswith(("SH", "SZ")) and len(s) > 2:
        s = s[2:].strip()
    if s.isdigit():
        norm = _normalize_stock_code_for_gms_pool(s)
        return norm if norm else None

    from backend_api.models import StockBasicInfo, StockBasicInfoHK, FundBasicInfo

    def _code_from_row(row) -> str:
        return str(getattr(row, "code", "") or "").strip()

    for Model in (StockBasicInfo, StockBasicInfoHK, FundBasicInfo):
        row = db.query(Model).filter(Model.code == s).first()
        if row:
            return _code_from_row(row)
        norm = _normalize_stock_code_for_gms_pool(s)
        if norm and norm != s:
            row = db.query(Model).filter(Model.code == norm).first()
            if row:
                return _code_from_row(row)

    for Model in (StockBasicInfo, StockBasicInfoHK, FundBasicInfo):
        row = db.query(Model).filter(Model.name == s).first()
        if row:
            return _code_from_row(row)

    like = f"%{s}%"
    for Model in (StockBasicInfo, StockBasicInfoHK, FundBasicInfo):
        row = (
            db.query(Model)
            .filter((Model.code.like(like)) | (Model.name.like(like)))
            .first()
        )
        if row:
            return _code_from_row(row)
    return None


# GMS 策略选股路由（以前端页面参数为准，与前端共用同一套参数）
@router.get("/gms-strategy")
async def get_gms_strategy(
    date: str = Query(None, description="目标日期 YYYY-MM-DD"),
    limit: int = Query(None, ge=1, description="最大返回数量"),
    min_score: float = Query(0, ge=0, le=100, description="最低总分阈值"),
    scope: str = Query("all", description="股票范围: all/cn/hk/etf/watchlist/gms_watchlist/industry_board/concept_board"),
    watchlist_user_id: Optional[int] = Query(
        None,
        ge=1,
        description="scope=watchlist 时可选：指定该用户的自选股；需携带管理员 JWT（payload.is_admin=true）",
    ),
    gms_watchlist_market: str = Query(
        "all",
        description="scope=gms_watchlist 时筛选市场: all(全部) / cn(A股) / hk(港股)，对应表字段 market A/HK",
    ),
    industry_board_code: Optional[List[str]] = Query(
        None,
        description="scope=industry_board 时必填：行业板块 BK 编码，可传多个（兼容历史名称，将自动解析）",
    ),
    concept_board_code: Optional[List[str]] = Query(
        None,
        description="scope=concept_board 时必填：概念板块代码，可传多个（如 BK0428）",
    ),
    exclude_st: bool = Query(
        False,
        description="为 true 时剔除 A 股 ST 类股票（名称含 ST，适用于各数据来源）",
    ),
    # 前端传入的策略参数（覆盖 gms_config.json 默认值）
    accumulation_fz_min: Optional[float] = Query(None, description="蓄势 F/Z 下限"),
    balance_ratio_max: Optional[float] = Query(None, description="平衡 |Δ/d₂₀| 上限"),
    volume_ratio_min: Optional[float] = Query(None, description="动量量比下限"),
    ratio_d20_max: Optional[float] = Query(None, description="左侧买点 Δ/d₂₀ 上限"),
    volume_ratio_max: Optional[float] = Query(None, description="左侧买点地量 m₂₀/m 上限"),
    left_buy_min_accumulation: Optional[float] = Query(
        None,
        ge=0,
        le=100,
        description="左侧买点额外要求：均值收敛态得分≥此值，0 或不传沿用配置（默认 0 关闭）",
    ),
    watch_threshold: Optional[float] = Query(None, description="重点关注分数"),
    alert_threshold: Optional[float] = Query(None, description="动量突变预警分数"),
    overbought_ratio: Optional[float] = Query(None, description="乖离过大退出阈值"),
    # 双模块阶梯与执行标准（精细化评分）
    accumulation_s_threshold: Optional[float] = Query(None, description="均值收敛态 S 级阈值"),
    accumulation_a_threshold: Optional[float] = Query(None, description="均值收敛态 A 级阈值"),
    momentum_full_threshold: Optional[float] = Query(None, description="动量溢出态全速切入阈值"),
    momentum_batch_threshold: Optional[float] = Query(None, description="动量溢出态分批买入阈值"),
    instant_deviation_stable_days: Optional[int] = Query(None, description="推力支撑站稳天数"),
    # 评分权重（可配置）
    weight_acc_fz: Optional[float] = Query(None, description="均值收敛态 时间耗散 F/Z 权重"),
    weight_acc_balance: Optional[float] = Query(None, description="均值收敛态 引力粘合 |Δ/d| 权重"),
    weight_acc_volume: Optional[float] = Query(None, description="均值收敛态 成交量缩 权重"),
    weight_mom_ratio_d1: Optional[float] = Query(None, description="动量溢出态 盈亏反转 Δ/d₁ 权重"),
    weight_mom_deviation: Optional[float] = Query(None, description="动量溢出态 推力支撑 d₂₀-d 权重"),
    weight_mom_volume: Optional[float] = Query(None, description="动量溢出态 攻击强度 m₂₀/m 权重"),
    code: Optional[str] = Query(None, description="单个股票代码（如果提供，则忽略 scope）"),
    trace_only: bool = Query(
        False,
        description="为 true 时仅从 gms_signal_trace 读缓存，不触发缺失股票的实时计算（前端可先快显再二次请求全量）",
    ),
    config_id: Optional[int] = Query(
        None,
        ge=1,
        description="GMS 策略参数版本 ID，不传则用默认版本；gms_watchlist 可自动使用观察股分组绑定的版本",
    ),
    use_pagination: bool = Query(
        False,
        description="为 true 时对返回列表分页（仍先完成全量选股与组装，再截取当前页）；默认 false 保持与其它客户端兼容",
    ),
    page: int = Query(1, ge=1, description="分页页码，从 1 开始"),
    page_size: int = Query(100, ge=1, le=500, description="每页条数，默认 100"),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
):
    """
    GMS 均值引力与动量突变策略选股。
    数据来源由 scope 决定：watchlist=当前用户自选股；gms_watchlist=管理端 GMS 观察股表（启用版本且 status=active）；
    industry_board=指定行业板块成分股；concept_board=指定概念板块成分股；cn/hk/etf=全市场对应品种。
    """
    if not GMS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "GMS策略暂不可用", "data": []},
        )

    try:
        # 未传日期时，从 mean_frequency_resonance_indicators 或历史行情获取最新可用日期
        if date:
            try:
                datetime.strptime(str(date).strip()[:10], "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
            target_date = str(date).strip()[:10]
        else:
            try:
                from backend_api.models import MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK
                from sqlalchemy import func
                candidates = []
                latest_hq_a = db.query(func.max(HistoricalQuotes.date)).scalar()
                if latest_hq_a:
                    d = latest_hq_a.strftime("%Y-%m-%d") if hasattr(latest_hq_a, "strftime") else str(latest_hq_a).strip()[:10]
                    candidates.append(d)
                latest_hq_hk = db.query(func.max(HistoricalQuotesHK.date)).scalar()
                if latest_hq_hk:
                    d = str(latest_hq_hk).strip()[:10]
                    candidates.append(d)
                if candidates:
                    target_date = max(candidates)
                    logger.info(f"GMS 使用历史行情表最近日期: {target_date}")
                else:
                    latest_ind = db.query(func.max(MeanFrequencyResonanceIndicators.date)).scalar()
                    if latest_ind:
                        target_date = str(latest_ind).strip()[:10]
                        logger.info(f"GMS 使用指标表最新日期: {target_date}")
                    else:
                        target_date = datetime.now().strftime("%Y-%m-%d")
                        logger.warning(f"GMS 无可用日期，使用当天: {target_date}")
            except Exception as e:
                target_date = datetime.now().strftime("%Y-%m-%d")
                logger.warning(f"GMS 获取最新日期失败: {e}，使用当天: {target_date}")

        stock_pool = None
        market = "all"
        resolved_industry_board_codes: Optional[List[str]] = None
        stock_pool_size = 0
        if code:
            resolved_code = _resolve_gms_stock_code_from_input(db, code)
            if not resolved_code:
                return JSONResponse(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": target_date,
                        "strategy_name": "GMS均值引力动量策略",
                        "scope": "single",
                        "message": f"未找到与「{str(code).strip()}」匹配的股票，请检查代码或名称",
                        "paging": {
                            "enabled": use_pagination,
                            "page": 1,
                            "page_size": page_size if use_pagination else 0,
                            "total": 0,
                            "total_pages": 0,
                        },
                    }
                )
            stock_pool = [resolved_code]
            logger.info("GMS 单个股票查询: input=%s resolved=%s", code, resolved_code)
            market = "all"
        elif scope == "watchlist":
            if not token:
                raise HTTPException(status_code=401, detail="查看自选股需要登录")
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                from backend_api.models import User
                if watchlist_user_id is not None:
                    if not payload.get("is_admin"):
                        raise HTTPException(status_code=403, detail="仅管理员可指定 watchlist_user_id")
                    user = db.query(User).filter(User.id == int(watchlist_user_id)).first()
                    if not user:
                        raise HTTPException(status_code=404, detail="指定用户不存在")
                else:
                    username = payload.get("sub")
                    if not username:
                        raise HTTPException(status_code=401, detail="无效的认证凭据")
                    user = db.query(User).filter(User.username == username).first()
                    if not user:
                        raise HTTPException(status_code=401, detail="用户不存在")
                watchlist_items = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
                if not watchlist_items:
                    return JSONResponse({
                        "success": True, "data": [], "total": 0,
                        "search_date": target_date, "strategy_name": "GMS均值引力动量策略",
                        "scope": "watchlist", "message": "您的自选股列表为空",
                        "paging": {
                            "enabled": use_pagination,
                            "page": 1,
                            "page_size": page_size if use_pagination else 0,
                            "total": 0,
                            "total_pages": 0,
                        },
                    })
                # 自选股代码归一化：与指标表一致（A 股 6 位、港股 5 位），便于匹配 mean_frequency_resonance_indicators
                stock_pool = list(
                    dict.fromkeys(_normalize_stock_code_for_gms_pool(item.stock_code) for item in watchlist_items)
                )
                stock_pool = [c for c in stock_pool if c]
                stock_pool_size = len(stock_pool)
                logger.info(f"GMS 数据来源=我的自选, 股票数={len(stock_pool)}")
                market = "all"
            except JWTError:
                raise HTTPException(status_code=401, detail="无效的认证凭据")
        elif scope == "gms_watchlist":
            from backend_api.models import GMSStrategyVersion, GMSStrategyVersionStock

            mraw = (gms_watchlist_market or "all").strip().lower()
            q_gms = (
                db.query(GMSStrategyVersionStock.stock_code)
                .join(GMSStrategyVersion, GMSStrategyVersion.id == GMSStrategyVersionStock.version_id)
                .filter(
                    GMSStrategyVersion.is_active == True,
                    func.lower(func.trim(func.coalesce(GMSStrategyVersionStock.status, ""))) == "active",
                )
            )
            if config_id is None:
                bound_ver = (
                    db.query(GMSStrategyVersion)
                    .filter(
                        GMSStrategyVersion.is_active == True,
                        GMSStrategyVersion.config_id.isnot(None),
                    )
                    .order_by(GMSStrategyVersion.id.asc())
                    .first()
                )
                if bound_ver and bound_ver.config_id:
                    config_id = int(bound_ver.config_id)
            if mraw in ("cn", "a"):
                q_gms = q_gms.filter(GMSStrategyVersionStock.market == "A")
            elif mraw in ("hk", "h"):
                q_gms = q_gms.filter(GMSStrategyVersionStock.market == "HK")
            rows_gms = q_gms.distinct().all()
            raw_codes = [str(r[0]).strip() for r in rows_gms if r[0] is not None and str(r[0]).strip()]
            stock_pool = list(dict.fromkeys(_normalize_stock_code_for_gms_pool(c) for c in raw_codes))
            stock_pool = [c for c in stock_pool if c]
            stock_pool_size = len(stock_pool)
            if not stock_pool:
                return JSONResponse(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": target_date,
                        "strategy_name": "GMS均值引力动量策略",
                        "scope": "gms_watchlist",
                        "message": "GMS观察股列表为空（请在管理端「观察股管理」维护启用版本下的股票）",
                        "paging": {
                            "enabled": use_pagination,
                            "page": 1,
                            "page_size": page_size if use_pagination else 0,
                            "total": 0,
                            "total_pages": 0,
                        },
                    }
                )
            market = "all"
            logger.info("GMS 数据来源=GMS观察股 market_filter=%s 股票数=%s", mraw, len(stock_pool))
        elif scope == "industry_board":
            from backend_api.models import IndustryBoardConstituent
            from backend_api.utils.bk_board_code import resolve_industry_board_codes

            bcodes = resolve_industry_board_codes(
                db, _normalize_gms_board_codes(industry_board_code)
            )
            resolved_industry_board_codes = bcodes
            if not bcodes:
                raw = _normalize_gms_board_codes(industry_board_code)
                raise HTTPException(
                    status_code=400,
                    detail=f"未找到行业板块：{('、'.join(raw) if raw else '请传 industry_board_code')}",
                )
            rows_ib = (
                db.query(IndustryBoardConstituent)
                .filter(IndustryBoardConstituent.board_code.in_(bcodes))
                .all()
            )
            raw_codes = [
                str(getattr(r, "stock_code", "") or "").strip()
                for r in rows_ib
                if getattr(r, "stock_code", None) is not None and str(getattr(r, "stock_code", "")).strip()
            ]
            stock_pool = list(dict.fromkeys(_normalize_stock_code_for_gms_pool(c) for c in raw_codes))
            stock_pool = [c for c in stock_pool if c]
            stock_pool_size = len(stock_pool)
            if not stock_pool:
                board_label = "、".join(bcodes)
                return JSONResponse(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": target_date,
                        "strategy_name": "GMS均值引力动量策略",
                        "scope": "industry_board",
                        "industry_board_code": bcodes[0] if len(bcodes) == 1 else None,
                        "industry_board_codes": bcodes,
                        "message": f"行业板块「{board_label}」成分股为空（请在管理端维护板块成分股）",
                        "paging": {
                            "enabled": use_pagination,
                            "page": 1,
                            "page_size": page_size if use_pagination else 0,
                            "total": 0,
                            "total_pages": 0,
                        },
                    }
                )
            market = "cn"
            logger.info("GMS 数据来源=行业板块 boards=%s 股票数=%s", bcodes, len(stock_pool))
        elif scope == "concept_board":
            from backend_api.models import ConceptBoardConstituent

            bcodes = _normalize_gms_board_codes(concept_board_code, upper=True)
            if not bcodes:
                raise HTTPException(status_code=400, detail="scope=concept_board 时需传 concept_board_code")
            rows_cb = (
                db.query(ConceptBoardConstituent)
                .filter(ConceptBoardConstituent.board_code.in_(bcodes))
                .all()
            )
            raw_codes = [
                str(getattr(r, "stock_code", "") or "").strip()
                for r in rows_cb
                if getattr(r, "stock_code", None) is not None and str(getattr(r, "stock_code", "")).strip()
            ]
            stock_pool = list(dict.fromkeys(_normalize_stock_code_for_gms_pool(c) for c in raw_codes))
            stock_pool = [c for c in stock_pool if c]
            stock_pool_size = len(stock_pool)
            if not stock_pool:
                board_label = "、".join(bcodes)
                return JSONResponse(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": target_date,
                        "strategy_name": "GMS均值引力动量策略",
                        "scope": "concept_board",
                        "concept_board_code": bcodes[0] if len(bcodes) == 1 else None,
                        "concept_board_codes": bcodes,
                        "message": f"概念板块「{board_label}」成分股为空（请在管理端维护板块成分股）",
                        "paging": {
                            "enabled": use_pagination,
                            "page": 1,
                            "page_size": page_size if use_pagination else 0,
                            "total": 0,
                            "total_pages": 0,
                        },
                    }
                )
            market = "cn"
            logger.info("GMS 数据来源=概念板块 boards=%s 股票数=%s", bcodes, len(stock_pool))
        elif scope == "cn":
            market = "cn"
        elif scope == "hk":
            market = "hk"
        elif scope == "etf":
            market = "etf"
        else:
            market = "all"

        config_mgr = GMSConfigManagerCls()
        resolved_config_id = config_mgr.resolve_config_id(config_id)
        config = config_mgr.get_config(resolved_config_id) if GMS_AVAILABLE else {}
        gms_config_meta = _gms_strategy_config_meta(config_mgr, resolved_config_id, config) if GMS_AVAILABLE else {}
        # 以前端传入参数覆盖 config（前后端共用同一套参数）
        if accumulation_fz_min is not None:
            config.setdefault("scoring", {})["accumulation_fz_min"] = accumulation_fz_min
        if balance_ratio_max is not None:
            config.setdefault("scoring", {})["balance_ratio_max"] = balance_ratio_max
        if volume_ratio_min is not None:
            config.setdefault("scoring", {})["momentum_volume_ratio_min"] = volume_ratio_min
        if watch_threshold is not None:
            config.setdefault("scoring", {})["watch_threshold"] = watch_threshold
        if alert_threshold is not None:
            config.setdefault("scoring", {})["alert_threshold"] = alert_threshold
        if ratio_d20_max is not None:
            config.setdefault("left_buy", {})["ratio_d20_abs_max"] = ratio_d20_max
        if volume_ratio_max is not None:
            config.setdefault("left_buy", {})["volume_ratio_max"] = volume_ratio_max
        if left_buy_min_accumulation is not None:
            config.setdefault("left_buy", {})["min_accumulation_score"] = left_buy_min_accumulation
        if overbought_ratio is not None:
            config.setdefault("exit", {})["overbought_ratio"] = overbought_ratio
        if volume_ratio_min is not None:
            config.setdefault("right_buy", {})["volume_ratio_min"] = volume_ratio_min
        if accumulation_s_threshold is not None:
            config.setdefault("scoring", {})["accumulation_s_threshold"] = accumulation_s_threshold
        if accumulation_a_threshold is not None:
            config.setdefault("scoring", {})["accumulation_a_threshold"] = accumulation_a_threshold
        if momentum_full_threshold is not None:
            config.setdefault("scoring", {})["momentum_full_threshold"] = momentum_full_threshold
        if momentum_batch_threshold is not None:
            config.setdefault("scoring", {})["momentum_batch_threshold"] = momentum_batch_threshold
        if instant_deviation_stable_days is not None:
            config.setdefault("scoring", {})["instant_deviation_stable_days"] = instant_deviation_stable_days
        if weight_acc_fz is not None:
            config.setdefault("scoring", {})["weight_acc_fz"] = weight_acc_fz
        if weight_acc_balance is not None:
            config.setdefault("scoring", {})["weight_acc_balance"] = weight_acc_balance
        if weight_acc_volume is not None:
            config.setdefault("scoring", {})["weight_acc_volume"] = weight_acc_volume
        if weight_mom_ratio_d1 is not None:
            config.setdefault("scoring", {})["weight_mom_ratio_d1"] = weight_mom_ratio_d1
        if weight_mom_deviation is not None:
            config.setdefault("scoring", {})["weight_mom_deviation"] = weight_mom_deviation
        if weight_mom_volume is not None:
            config.setdefault("scoring", {})["weight_mom_volume"] = weight_mom_volume
        max_results = limit or 10000

        # 在 executor 内使用独立 Session，避免请求的 db 跨线程或已关闭导致 "identity map is no longer valid"
        def _run_gms(
            _target_date: str,
            _config: dict,
            _config_id: int,
            _min_score: float,
            _max_results: int,
            _trace_only: bool,
            _exclude_st: bool,
        ):
            session = SessionLocal()
            try:
                gms_if = GMSFrontendInterface(session, _config, config_id=_config_id)
                gms_if.set_selection_config(min_score=_min_score, max_results=_max_results)
                return gms_if.get_selection_results(
                    _target_date,
                    stock_pool,
                    market,
                    trace_only=_trace_only,
                    return_meta=True,
                    exclude_st=_exclude_st,
                )
            finally:
                session.close()

        loop = asyncio.get_event_loop()
        gms_meta: dict = dict(gms_config_meta)
        selection_results, gms_meta_run = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: _run_gms(
                    target_date, config, resolved_config_id, min_score, max_results, trace_only, exclude_st
                ),
            ),
            timeout=GMS_SCREENING_TIMEOUT,
        )
        gms_meta.update(gms_meta_run or {})

        # 当指定日期无数据时，回退到指标表最新可用日期
        user_specified_date = bool(date)
        fallback_used = False
        if not selection_results and user_specified_date and stock_pool:
            try:
                from backend_api.models import MeanFrequencyResonanceIndicators
                from sqlalchemy import func
                fallback_date = db.query(func.max(MeanFrequencyResonanceIndicators.date)).scalar()
                if fallback_date:
                    fallback_date_str = str(fallback_date).strip()[:10]
                    if fallback_date_str != target_date:
                        logger.info(f"GMS 所选日期 {target_date} 无数据，回退到指标表最新日期 {fallback_date_str}")
                        selection_results, gms_meta = await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                lambda: _run_gms(
                                    fallback_date_str,
                                    config,
                                    resolved_config_id,
                                    min_score,
                                    max_results,
                                    trace_only,
                                    exclude_st,
                                ),
                            ),
                            timeout=GMS_SCREENING_TIMEOUT,
                        )
                        target_date = fallback_date_str
                        fallback_used = bool(selection_results)
            except Exception as e:
                logger.warning(f"GMS 回退日期失败: {e}")

        if not selection_results:
            msg = f"所选日期 {target_date} 暂无指标数据" if user_specified_date else ""
            return JSONResponse({
                "success": True,
                "data": [],
                "total": 0,
                "search_date": target_date,
                "strategy_name": "GMS均值引力动量策略",
                "message": msg,
                "gms_trace_meta": gms_meta,
                "trace_only": trace_only,
                "paging": {
                    "enabled": use_pagination,
                    "page": 1,
                    "page_size": page_size if use_pagination else 0,
                    "total": 0,
                    "total_pages": 0,
                },
            })

        from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
        from sqlalchemy import func

        stock_codes = [str(r["symbol"]).strip() for r in selection_results]
        code_to_gms_mt = {str(r["symbol"]).strip(): r.get("market_type") for r in selection_results}
        # 6 位：6/0/3 为 A 股，9 为沪市 B 股，均从 A 股行情/基本信息表取数
        cn_codes = [c for c in stock_codes if c and len(c) >= 6 and c.isdigit() and c[0] in "6039"]
        cn_code_set = set(cn_codes)
        hk_codes = [c for c in stock_codes if c and c not in cn_codes]

        # 从历史行情表获取最近交易日收盘价（A股、港股分别查）
        hist_quotes_a = {}
        hist_quotes_hk = {}
        if cn_codes:
            latest_date_a = db.query(func.max(HistoricalQuotes.date)).scalar()
            if latest_date_a:
                quotes_a = db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code.in_(cn_codes),
                    HistoricalQuotes.date == latest_date_a,
                ).all()
                hist_quotes_a = {q.code: q for q in quotes_a}
        if hk_codes:
            latest_date_hk_row = db.query(func.max(HistoricalQuotesHK.date)).scalar()
            latest_date_hk = str(latest_date_hk_row).strip()[:10] if latest_date_hk_row else None
            if latest_date_hk:
                quotes_hk = db.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code.in_(hk_codes),
                    HistoricalQuotesHK.date == latest_date_hk,
                ).all()
                hist_quotes_hk = {q.code: q for q in quotes_hk}

        results_data = []
        def _normalize_buy_type(raw_buy_type, left_signal, right_signal):
            """
            统一买点类型展示，避免历史 trace 脏值导致前端显示异常。
            优先按信号位判定，其次兼容旧值映射。
            """
            if left_signal:
                return "左侧"
            if right_signal:
                return "右侧"
            s = str(raw_buy_type or "").strip().lower()
            if s in ("左侧", "left", "left_buy", "leftbuy"):
                return "左侧"
            if s in ("右侧", "right", "right_buy", "rightbuy"):
                return "右侧"
            # 兼容历史值：如“左侧买入/右侧买入/left entry/right entry”等
            if ("左侧" in s) or ("left" in s):
                return "左侧"
            if ("右侧" in s) or ("right" in s):
                return "右侧"
            return "--"

        for r in selection_results:
            code = str(r["symbol"]).strip()
            name = _resolve_gms_stock_name(db, code, r.get("market_type"))

            current_price = r.get("d") or 0
            change_percent = None
            quote = hist_quotes_a.get(code) or hist_quotes_hk.get(code)
            if quote and hasattr(quote, "close") and quote.close is not None:
                current_price = float(quote.close)
            if quote and hasattr(quote, "change_percent") and quote.change_percent is not None:
                change_percent = float(quote.change_percent)

            st = r.get("score_total")
            signal_strength = (float(st) / 100.0) if st is not None and st > 0 else (r.get("signal_strength") or 0.0)
            left_signal = bool(r.get("left_buy_signal", False))
            right_signal = bool(r.get("right_buy_signal", False))
            buy_type_text = _normalize_buy_type(r.get("buy_type"), left_signal, right_signal)
            results_data.append({
                "symbol": code,
                "code": code,
                "name": name,
                "signal_date": target_date,
                "score_total": r["score_total"],
                "score_accumulation": r.get("score_accumulation"),
                "score_momentum": r.get("score_momentum"),
                "accumulation_grade": r.get("accumulation_grade", ""),
                "momentum_grade": r.get("momentum_grade", ""),
                "signal_strength": signal_strength,
                "buy_type": buy_type_text,
                "current_price": current_price,
                "ratio_d20": r.get("ratio_d20"),
                "ratio_d1": r.get("ratio_d1"),
                "ratio_d": r.get("ratio_d"),
                "fz_ratio": r.get("fz_ratio"),
                "delta": r.get("delta"),
                "falling_days": r.get("falling_days"),
                "rising_days": r.get("rising_days"),
                "d_ma20": r.get("d"),
                "avg_volume_20d": r.get("avg_volume_20d"),
                "current_volume": r.get("current_volume"),
                "ratio_relative": (r.get("delta") / r.get("d")) if r.get("delta") is not None and r.get("d") is not None and r.get("d") != 0 else None,
                "current_change_percent": change_percent if change_percent is not None else 0.0,
                "score_detail": r.get("score_detail", {}),
                "left_buy_signal": left_signal,
                "right_buy_signal": right_signal,
                "sell_signal": r.get("sell_signal", False),
            })

        # 兜底补全：避免前端出现“有信号但 Δ/F/Z/d 全空白 / 得分明细为空”
        # 仅对缺失关键字段的条目补全，且尽量不增加全市场的额外负担
        for item in results_data:
            need_fill = (
                item.get("delta") is None
                or item.get("d_ma20") is None
                or item.get("rising_days") is None
                or item.get("falling_days") is None
                or item.get("ratio_d") is None
                or item.get("avg_volume_20d") is None
                or item.get("current_volume") is None
            )
            _sym = str(item.get("symbol") or "").strip()
            _gmt = code_to_gms_mt.get(_sym)
            if _gmt in ("CN", "HK", "ETF"):
                mt = _gmt
            else:
                mt = _fallback_gms_indicator_market_type(_sym, scope, cn_code_set)
            if need_fill:
                fallback = _fill_gms_indicator_fallback(db, item.get("symbol"), target_date, mt)
                if fallback:
                    # 仅填空字段，不覆盖已有值
                    for k, v in fallback.items():
                        if item.get(k) is None and v is not None:
                            item[k] = v
                    # ratio_relative 如果仍为空且可算则补
                    if item.get("ratio_relative") is None:
                        try:
                            if item.get("delta") is not None and item.get("d_ma20") not in (None, 0):
                                item["ratio_relative"] = float(item["delta"]) / float(item["d_ma20"])
                        except Exception:
                            pass

            sd = item.get("score_detail")
            # 兼容历史 trace：
            # 1) score_detail 为空/全空；
            # 2) 关键细项缺失（前端“计算指标细项”依赖这几个键）
            score_detail_empty = (
                not isinstance(sd, dict)
                or len(sd) == 0
                or all(v is None or v == "" for v in sd.values())
            )
            score_detail_missing_keys = False
            _mechanism = (config.get("scoring") or {}).get("mechanism") or "tiered_dual_max"
            if isinstance(sd, dict):
                required_keys = ("ratio_d", "avg_volume_20d", "current_volume")
                for k in required_keys:
                    if sd.get(k) is None or sd.get(k) == "":
                        score_detail_missing_keys = True
                        break
                if sd.get("ma60_d") is None:
                    score_detail_missing_keys = True
                if _mechanism == "tiered_dual_penalty" and sd.get("score_penalty_deduction") is None:
                    score_detail_missing_keys = True

            if score_detail_empty or score_detail_missing_keys:
                score_fallback = _fill_gms_score_fallback(db, item.get("symbol"), target_date, mt, config)
                if score_fallback:
                    for k, v in score_fallback.items():
                        if k == "score_detail":
                            item["score_detail"] = v
                            # 同步综合总分与信号强度，确保与 score_detail 一致（避免 trace 中 score_total=0 导致信号强度为 0）
                            sd_total = v.get("score_total") if isinstance(v, dict) else None
                            if sd_total is not None:
                                item["score_total"] = sd_total
                                item["signal_strength"] = float(sd_total) / 100.0 if float(sd_total) > 0 else 0.0
                        elif k in (
                            "left_buy_signal",
                            "right_buy_signal",
                            "sell_signal",
                            "buy_type",
                        ):
                            # 得分兜底已按当前配置重算，同步买点/卖点，避免「明细 100 分但标签仍为 trace 旧值」
                            item[k] = v
                        elif item.get(k) is None:
                            item[k] = v
                    item["buy_type"] = _normalize_buy_type(
                        None,
                        bool(item.get("left_buy_signal")),
                        bool(item.get("right_buy_signal")),
                    )

            item["score_detail"] = _inject_gms_score_detail_meta(item.get("score_detail"), gms_config_meta)

        from backend_api.gms_trade_observe_routes import (
            _normalize_code as _gms_industry_norm_code,
            batch_resolve_industries_by_pairs,
        )

        _gms_industry_pairs: List[tuple[str, str]] = []
        for item in results_data:
            code = str(item.get("symbol") or item.get("code") or "").strip()
            if not code:
                continue
            mt = code_to_gms_mt.get(code)
            if mt not in ("CN", "HK", "ETF"):
                mt = _fallback_gms_indicator_market_type(code, scope, cn_code_set)
            market = "HK" if mt == "HK" else "CN"
            _gms_industry_pairs.append((market, code))
        _gms_industry_map = batch_resolve_industries_by_pairs(db, _gms_industry_pairs)
        for item in results_data:
            code = str(item.get("symbol") or item.get("code") or "").strip()
            if not code:
                item["industry"] = None
                continue
            mt = code_to_gms_mt.get(code)
            if mt not in ("CN", "HK", "ETF"):
                mt = _fallback_gms_indicator_market_type(code, scope, cn_code_set)
            market = "HK" if mt == "HK" else "CN"
            item["market"] = market
            item["industry"] = _gms_industry_map.get((market, _gms_industry_norm_code(code)))

        observe_code_keys: set[str] = set()
        formal_trade_code_keys: set[str] = set()
        if token:
            try:
                from backend_api.models import User
                from backend_api.gms_trade_observe_routes import list_user_trade_observe_code_keys
                from backend_api.gms_formal_trade_routes import list_user_formal_trade_code_keys

                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get("sub")
                if username:
                    observe_user = db.query(User).filter(User.username == username).first()
                    if observe_user:
                        uid = int(observe_user.id)
                        observe_code_keys = set(
                            list_user_trade_observe_code_keys(db, uid)
                        )
                        formal_trade_code_keys = set(
                            list_user_formal_trade_code_keys(db, uid)
                        )
            except (JWTError, Exception):
                observe_code_keys = set()
                formal_trade_code_keys = set()
        observed_code_keys = observe_code_keys | formal_trade_code_keys
        for item in results_data:
            code = str(item.get("symbol") or item.get("code") or "").strip()
            if not code:
                item["in_trade_observe"] = False
                continue
            mt = item.get("market")
            if not mt:
                mt = code_to_gms_mt.get(code)
                if mt not in ("CN", "HK", "ETF"):
                    mt = _fallback_gms_indicator_market_type(code, scope, cn_code_set)
                mt = "HK" if mt == "HK" else "CN"
                item["market"] = mt
            market = "HK" if str(mt).upper() == "HK" else "CN"
            key = f"{market}:{_gms_industry_norm_code(code)}"
            item["in_trade_observe"] = key in observed_code_keys

        # 按信号强度由高到低排列
        def _gms_signal_sort_key(x):
            s = x.get("signal_strength")
            if s is not None:
                return float(s)
            st = x.get("score_total")
            return (float(st) / 100.0) if st is not None else 0.0
        results_data.sort(key=_gms_signal_sort_key, reverse=True)

        total_all = len(results_data)
        page_eff = 1
        total_pages = 0
        if use_pagination:
            total_pages = max(1, math.ceil(total_all / page_size)) if page_size and total_all > 0 else (0 if total_all == 0 else 1)
            page_eff = min(max(1, page), total_pages) if total_pages > 0 else 1
            start_idx = (page_eff - 1) * page_size
            results_data = results_data[start_idx : start_idx + page_size]
        else:
            total_pages = 1 if total_all > 0 else 0
            page_eff = 1

        resp = {
            "success": True,
            "data": results_data,
            "total": total_all,
            "search_date": target_date,
            "strategy_name": "GMS均值引力动量策略",
            "parameters": {
                "limit": limit or "无限制",
                "min_score": min_score,
                "scope": scope,
                "stock_pool_size": stock_pool_size,
                "industry_board_code": (
                    resolved_industry_board_codes[0]
                    if scope == "industry_board" and resolved_industry_board_codes
                    else None
                ),
                "industry_board_codes": (
                    resolved_industry_board_codes
                    if scope == "industry_board"
                    else None
                ),
                "concept_board_code": (
                    _normalize_gms_board_codes(concept_board_code, upper=True)[0]
                    if scope == "concept_board" and _normalize_gms_board_codes(concept_board_code, upper=True)
                    else None
                ),
                "concept_board_codes": (
                    _normalize_gms_board_codes(concept_board_code, upper=True)
                    if scope == "concept_board"
                    else None
                ),
                "exclude_st": exclude_st,
                "use_pagination": use_pagination,
                "page": page_eff,
                "page_size": page_size if use_pagination else total_all,
            },
            "gms_trace_meta": gms_meta,
            "trace_only": trace_only,
            "paging": {
                "enabled": use_pagination,
                "page": page_eff,
                "page_size": page_size if use_pagination else total_all,
                "total": total_all,
                "total_pages": total_pages,
            },
        }
        if fallback_used and user_specified_date:
            resp["message"] = f"所选日期无指标数据，已使用最新可用日期 {target_date}"
        return JSONResponse(resp)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.warning(f"GMS 选股超时({GMS_SCREENING_TIMEOUT}s)，scope={scope}")
        raise HTTPException(
            status_code=504,
            detail=f"GMS选股计算超时（超过{GMS_SCREENING_TIMEOUT}秒），请缩小范围或稍后重试",
        )
    except Exception as e:
        logger.error(f"GMS 策略选股失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"GMS策略选股失败: {str(e)}")


# 调试：打印路由对象中的所有路由
print(f"[DEBUG] router.routes count: {len(router.routes)}")
for route in router.routes:
    if hasattr(route, 'path'):
        print(f"[DEBUG] route path: {route.path}, methods: {getattr(route, 'methods', None)}")


@router.get("/cyb-midline-strategy")
async def get_cyb_midline_strategy(
    months: int = Query(4, ge=3, le=4, description="查询月数（3-4个月）"),
    db: Session = Depends(get_db)
):
    """
    创业板中线选股策略
    
    股票范围:
    - 创业板股票（代码以3开头）
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    策略条件：
    1. 第一个涨停（涨幅>=9.8%）
    2. 第一次回调不跌穿涨停底部
    3. 第二次上涨突破第一个涨停高点
    4. 中间有向上跳空和揉搓线
    5. 当前均线多头排列（MA5>MA10>MA20）
    
    Args:
        months: 查询月数，默认4个月
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info(f"开始执行创业板中线选股策略，查询月数: {months}")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_cyb_midline_strategy(db, months=months)
        
        logger.info(f"选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "months": months,
            "strategy_name": "创业板中线选股策略"
        })
        
    except Exception as e:
        logger.error(f"执行选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"选股策略执行失败: {str(e)}"
        )


@router.get("/parking-apron-strategy")
async def get_parking_apron_strategy(
    db: Session = Depends(get_db)
):
    """
    停机坪选股策略
    
    策略条件：
    1. 最近15日有涨幅大于9.5%，且必须是放量上涨
    2. 紧接的下个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%
    3. 接下2、3个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%，且每天涨跌幅在5%间
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行停机坪选股策略")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_parking_apron_strategy(db)
        
        logger.info(f"停机坪选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "停机坪"
        })
        
    except Exception as e:
        logger.error(f"执行停机坪选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停机坪选股策略执行失败: {str(e)}"
        )


@router.get("/backtrace-ma250-strategy")
async def get_backtrace_ma250_strategy(
    db: Session = Depends(get_db)
):
    """
    回踩年线选股策略
    
    策略条件：
    1. 时间段：前段=最近60交易日最高收盘价之前交易日(长度>0)，后段=最高价当日及后面的交易日
    2. 前段由年线(250日)以下向上突破
    3. 后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间
    4. 回踩伴随缩量：最高价日交易量/后段最低价日交易量>2,后段最低价/最高价<0.8
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行回踩年线选股策略")
        
        # 执行选股策略
        results = StockScreeningStrategy.screening_backtrace_ma250_strategy(db)
        
        logger.info(f"回踩年线选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "回踩年线"
        })
        
    except Exception as e:
        logger.error(f"执行回踩年线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回踩年线选股策略执行失败: {str(e)}"
        )


@router.get("/high-tight-flag-strategy")
async def get_high_tight_flag_strategy(
    db: Session = Depends(get_db)
):
    """
    高而窄的旗形选股策略
    
    策略条件：
    1. 必须至少上市交易60日
    2. 当日收盘价/之前24~10日的最低价>=1.9
    3. 之前24~10日必须连续两天涨幅大于等于9.5%
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行高而窄的旗形选股策略")
        
        # 执行选股策略
        results = HighTightFlagStrategy.screening_high_tight_flag_strategy(db)
        
        logger.info(f"高而窄的旗形选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "高而窄的旗形"
        })
        
    except Exception as e:
        logger.error(f"执行高而窄的旗形选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"高而窄的旗形选股策略执行失败: {str(e)}"
        )


@router.get("/keep-increasing-strategy")
async def get_keep_increasing_strategy(
    db: Session = Depends(get_db)
):
    """
    持续上涨（MA30向上）选股策略
    
    策略条件：
    1. 均线多头：30日前的30日均线 < 20日前的30日均线 < 10日前的30日均线 < 当日的30日均线
    2. 涨幅要求：(当日的30日均线 / 30日前的30日均线) > 1.2
    
    Args:
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info("开始执行持续上涨（MA30向上）选股策略")
        
        # 执行选股策略
        results = KeepIncreasingStrategy.screening_keep_increasing_strategy(db)
        
        logger.info(f"持续上涨（MA30向上）选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "持续上涨（MA30向上）"
        })
        
    except Exception as e:
        logger.error(f"执行持续上涨（MA30向上）选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"持续上涨（MA30向上）选股策略执行失败: {str(e)}"
        )


@router.get("/long-lower-shadow-strategy")
async def get_long_lower_shadow_strategy(
    lower_shadow_ratio: float = Query(1.0, ge=0.5, le=3.0, description="下影线长度 >= 实体长度的倍数（默认1.0倍）"),
    upper_shadow_ratio: float = Query(0.3, ge=0.1, le=0.5, description="上影线 <= 实体长度的比例（默认30%）"),
    min_amplitude: float = Query(0.02, ge=0.01, le=0.1, description="最小振幅要求（默认2%）"),
    recent_days: int = Query(2, ge=1, le=10, description="检查最近N个交易日（默认2天）"),
    db: Session = Depends(get_db)
):
    """
    长下影阳线选股策略（参数化版本）
    
    策略条件:
    1. 下跌趋势: 当日最低价 < MA20（20日移动平均线）
    2. 长下影线: 最近N个交易日内出现(阳线或阴线均可)
       - 下影线长度 >= 实体长度的X倍（可配置）
       - 上影线很短或几乎没有（<= 实体长度的Y%，可配置）
    3. 振幅: 出现长下影线当日振幅超过Z%（可配置）
    
    参数说明:
    - lower_shadow_ratio: 下影线倍数（0.5-3.0），默认1.0
    - upper_shadow_ratio: 上影线比例（0.1-0.5），默认0.3
    - min_amplitude: 最小振幅（0.01-0.1），默认0.02
    - recent_days: 检查天数（1-10），默认2
    
    Args:
        lower_shadow_ratio: 下影线长度倍数
        upper_shadow_ratio: 上影线比例
        min_amplitude: 最小振幅
        recent_days: 检查最近N天
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        logger.info(f"开始执行长下影阳线选股策略 - 参数: 下影线倍数={lower_shadow_ratio}, "
                   f"上影线比例={upper_shadow_ratio}, 最小振幅={min_amplitude}, 检查天数={recent_days}")
        
        # 执行选股策略（传入参数）
        results = LongLowerShadowStrategy.screening_long_lower_shadow_strategy(
            db, 
            lower_shadow_ratio=lower_shadow_ratio,
            upper_shadow_ratio=upper_shadow_ratio,
            min_amplitude=min_amplitude,
            recent_days=recent_days
        )
        
        logger.info(f"长下影阳线选股策略执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "长下影阳线",
            "parameters": {
                "lower_shadow_ratio": lower_shadow_ratio,
                "upper_shadow_ratio": upper_shadow_ratio,
                "min_amplitude": min_amplitude,
                "recent_days": recent_days
            }
        })
        
    except Exception as e:
        logger.error(f"执行长下影阳线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"长下影阳线选股策略执行失败: {str(e)}"
        )


@router.get("/low-nine-strategy")
async def get_low_nine_strategy(
    limit: int = Query(None, description="限制处理股票数量（测试用，None表示处理所有）"),
    db: Session = Depends(get_db)
):
    """
    低九策略选股
    
    策略条件:
    应用于下跌趋势中，构成条件：
    连续 9 根K线（或交易日），每一天的收盘价都低于它前面第4天的收盘价。
    
    股票范围:
    - 全部A股
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    Args:
        limit: 限制处理股票数量（可选，用于测试）
        db: 数据库会话
    
    Returns:
        符合条件的股票列表
    """
    try:
        if limit:
            logger.info(f"开始执行低九策略选股（测试模式：限制 {limit} 只股票）")
        else:
            logger.info("开始执行低九策略选股（生产模式：处理所有股票）")
        
        # 执行选股策略
        results = LowNineStrategy.screening_low_nine_strategy(db, limit=limit)
        
        logger.info(f"低九策略选股执行完成，找到 {len(results)} 只符合条件的股票")
        
        return JSONResponse({
            "success": True,
            "data": results,
            "total": len(results),
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "低九策略",
            "test_mode": limit is not None,
            "limit": limit
        })
        
    except Exception as e:
        logger.error(f"执行低九策略选股失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"低九策略选股执行失败: {str(e)}"
        )


@router.get("/volume-shrink-breakout-strategy")
async def get_volume_shrink_breakout_strategy(
    scope: str = Query("all", description="股票范围: all(全A，可用 limit 压测), watchlist(当前登录用户自选股)"),
    limit: Optional[int] = Query(None, ge=1, description="限制扫描数量（测试用；全市场时强烈建议先设 limit）"),
    date: Optional[str] = Query(
        None,
        description="筛选基准日 YYYY-MM-DD；不传则按当前自然日。若 historical_quotes 无该日或晚于表内最新日，则自动用表内全局最新 date 作为 K 线窗口止日",
    ),
    volume_ratio: Optional[float] = Query(None, ge=1.0, le=30.0, description="爆量相对前一交易日倍数，默认读配置"),
    boom_lookback_min: Optional[int] = Query(None, ge=1, le=250, description="爆量日在最近 K 线中的最小下标"),
    boom_lookback_max: Optional[int] = Query(None, ge=1, le=250, description="爆量日在最近 K 线中的最大下标"),
    boards: Optional[List[str]] = Query(
        None,
        description="板块/代码段过滤，可多传：CYB创业板 KCB科创板 SH_MAIN沪市主板 SZ_MAIN深市主板 SZ_SME中小板；不传=全市场",
    ),
    persist: bool = Query(True, description="为 true 时将选股命中写入 volume_shrink_breakout_signals"),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
):
    """
    3倍量缩量突破策略（独立 core 模块）。
    爆量：volume[k] >= volume_ratio * volume[k+1]；均线多头在爆量日；最新日缩量突破爆量日收盘。
    """
    if not VSB_AVAILABLE or VolumeShrinkBreakoutFrontendInterface is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "3倍量缩量突破策略模块不可用", "data": []},
        )

    stock_codes: Optional[List[str]] = None
    if scope == "watchlist":
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="查看自选股需要登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=401, detail="无效的认证凭据")
            from backend_api.models import User

            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise HTTPException(status_code=401, detail="用户不存在")
            watchlist_items = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
            if not watchlist_items:
                from backend_core.strategies.volume_shrink_breakout.data_loader import VolumeShrinkBreakoutDataLoader

                eff = VolumeShrinkBreakoutDataLoader.resolve_effective_history_end_date(db, date)
                return JSONResponse(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "search_date": eff,
                        "strategy_name": "3倍量缩量突破",
                        "scope": "watchlist",
                        "message": "您的自选股列表为空",
                    }
                )
            stock_codes = [str(item.stock_code).strip() for item in watchlist_items]
        except JWTError:
            raise HTTPException(status_code=401, detail="无效的认证凭据")
    elif scope != "all":
        raise HTTPException(status_code=400, detail="scope 仅支持 all 或 watchlist")

    loop = asyncio.get_event_loop()

    def _run():
        return VolumeShrinkBreakoutFrontendInterface.screen(
            db,
            scope=scope,
            limit=limit,
            stock_codes=stock_codes,
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
            boards=boards,
            persist_signals=persist,
            screening_date=date,
        )

    try:
        payload = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=VSB_SCREENING_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("VSB 选股超时(%ss) scope=%s", VSB_SCREENING_TIMEOUT, scope)
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": f"选股计算超时（超过{VSB_SCREENING_TIMEOUT}秒），请缩小范围或使用 limit",
                "data": [],
            },
        )

    return JSONResponse(payload)


@router.get("/vsb-signals")
async def screening_get_vsb_signals_by_code(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="signal_date 起（含）"),
    end_date: Optional[str] = Query(None, description="signal_date 止（含）"),
    limit: int = Query(200, ge=1, le=2000, description="最大条数"),
    db: Session = Depends(get_db),
):
    """VSB 信号历史（与 GET /api/stock/vsb-signals 同源；便于与选股同前缀走 Nginx）。"""
    from backend_api.services.vsb_signals_service import query_vsb_signals_by_code

    try:
        payload, err = query_vsb_signals_by_code(
            db, code=code, start_date=start_date, end_date=end_date, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "VSB 信号模型不可用", "data": [], "total": 0},
        )
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    if err == "bad_code":
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    return JSONResponse(payload)


@router.get("/vsb-signals/by-date")
async def screening_get_vsb_signals_by_signal_date(
    signal_date: str = Query(..., description="信号日（突破日）YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000, description="最大条数"),
    db: Session = Depends(get_db),
):
    """按 signal_date 查询当日全市场已落库的 VSB 信号（与 GET /api/stock/vsb-signals/by-date 同源）。"""
    from backend_api.services.vsb_signals_service import query_vsb_signals_by_signal_date

    try:
        payload, err = query_vsb_signals_by_signal_date(db, signal_date=signal_date, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "VSB 信号模型不可用", "data": [], "total": 0},
        )
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    return JSONResponse(payload)


VSB_RECALCULATE_TIMEOUT_SEC = 120
VSB_REPLAY_TIMEOUT_SEC = 600


@router.post("/vsb-signals/recalculate")
async def screening_post_vsb_signals_recalculate(
    code: str = Query(..., description="6 位股票代码"),
    name: Optional[str] = Query(None, description="证券简称，可空"),
    search_date: Optional[str] = Query(None, description="落库 run_search_date，默认今日"),
    replay_range: bool = Query(False, description="为 true 时对 start_date～end_date 逐日切片重算并落库"),
    start_date: Optional[str] = Query(None, description="逐日回放起始 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="逐日回放结束 YYYY-MM-DD"),
    volume_ratio: Optional[float] = Query(None, ge=1.0, le=30.0),
    boom_lookback_min: Optional[int] = Query(None, ge=1, le=250),
    boom_lookback_max: Optional[int] = Query(None, ge=1, le=250),
    db: Session = Depends(get_db),
):
    """单股重算 VSB 并落库（与 POST /api/vsb/signals/recalculate 同源）。"""
    if not VSB_AVAILABLE or VolumeShrinkBreakoutFrontendInterface is None:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "3倍量缩量突破策略模块不可用",
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )

    if replay_range:
        rs = (start_date or "").strip()[:10]
        re = (end_date or "").strip()[:10]
        if not rs or not re:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "replay_range=true 时必须同时提供 start_date 与 end_date（YYYY-MM-DD）",
                    "saved": 0,
                    "hit": False,
                    "data": [],
                },
            )
    else:
        rs = ""
        re = ""

    loop = asyncio.get_event_loop()
    timeout_sec = VSB_REPLAY_TIMEOUT_SEC if replay_range else VSB_RECALCULATE_TIMEOUT_SEC

    def _run():
        if replay_range:
            return VolumeShrinkBreakoutFrontendInterface.recalculate_range_replay_and_persist(
                db,
                code=code,
                name=name,
                search_date=search_date,
                replay_start=rs,
                replay_end=re,
                volume_ratio=volume_ratio,
                boom_lookback_min=boom_lookback_min,
                boom_lookback_max=boom_lookback_max,
            )
        return VolumeShrinkBreakoutFrontendInterface.recalculate_single_and_persist(
            db,
            code=code,
            name=name,
            search_date=search_date,
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

    try:
        out = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": (
                    f"VSB 逐日回放超时（>{timeout_sec}s）"
                    if replay_range
                    else f"单股重算超时（>{timeout_sec}s）"
                ),
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )
    if not out.get("success"):
        return JSONResponse(status_code=400, content=out)
    return JSONResponse(content=out)


@router.get("/one-yang-three-lines")
async def get_one_yang_three_lines_strategy(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量，最大500"),
    start_date: str = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    # 一阳穿三线策略参数
    min_increase_percent: float = Query(3.0, ge=0, le=50, description="最小涨幅百分比（默认3%）"),
    min_body_ratio: float = Query(0.7, ge=0.1, le=1.0, description="最小实体占比（默认0.7）"),
    min_cross_lines: int = Query(3, ge=2, le=6, description="最小穿越均线数量（默认3）"),
    min_volume_ratio: float = Query(2.0, ge=0.1, le=10.0, description="最小成交量倍数（默认2.0）"),
    min_turnover_rate: float = Query(3.0, ge=0, le=50, description="最小换手率（默认3%）"),
    max_turnover_rate: float = Query(10.0, ge=0, le=100, description="最大换手率（默认10%）"),
    recent_days: int = Query(1, ge=1, le=10, description="检查最近N个交易日（默认1天）"),
    ma_periods: str = Query("5,10,20,30,60,120", description="均线周期，逗号分隔（默认5,10,20,30,60,120）"),
    db: Session = Depends(get_db)
):
    """
    一阳穿三线选股策略（又称"出水芙蓉"）
    
    策略条件:
    1. 长阳线：收盘价>开盘价，实体占比>=min_body_ratio，涨幅>=min_increase_percent%
    2. 穿越至少min_cross_lines条均线（从ma_periods中选择）
    3. 放量突破：成交量>=前5日平均成交量的min_volume_ratio倍
    4. 换手率范围：min_turnover_rate% - max_turnover_rate%
    5. 位置判别：根据60日最高价回撤幅度判断低位/中位/高位
    6. 乖离率计算：BIAS5/10/30，BIAS30>10%时风险提示
    7. 信号质量评分：综合穿线数量、成交量、换手率、位置、乖离率
    8. 检查天数：最近N个交易日内出现符合上述条件的形态
    
    股票范围:
    - 全部A股
    - 自动排除ST股票（包括ST、*ST、S*ST等所有ST类股票）
    
    Args:
        page: 页码（可选，默认1）
        page_size: 每页数量（可选，默认100，最大500）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        min_increase_percent: 最小涨幅百分比（默认3%）
        min_body_ratio: 最小实体占比（默认0.7）
        min_cross_lines: 最小穿越均线数量（默认3）
        min_volume_ratio: 最小成交量倍数（默认2.0）
        min_turnover_rate: 最小换手率（默认3%）
        max_turnover_rate: 最大换手率（默认10%）
        recent_days: 检查最近N个交易日（默认1天）
        ma_periods: 均线周期，逗号分隔（默认5,10,20,30,60,120）
        db: 数据库会话
    
    Returns:
        符合条件的股票列表，按信号质量评分降序排列
    """
    try:
        logger.info(f"开始执行一阳穿三线选股策略 - 页码: {page}, 每页: {page_size}, 检查最近 {recent_days} 天")
        if start_date:
            logger.info(f"日期范围: {start_date} 至 {end_date or '今天'}")
        
        # 参数验证
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="开始日期格式错误，应为 YYYY-MM-DD"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="结束日期格式错误，应为 YYYY-MM-DD"
                )
        
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期不能晚于结束日期"
            )
        
        # 解析均线周期参数
        try:
            ma_periods_list = [int(x.strip()) for x in ma_periods.split(',')]
            if len(ma_periods_list) < 2:
                raise ValueError("至少需要2个均线周期")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"均线周期参数错误: {str(e)}"
            )
        
        # 构建策略参数
        strategy_params = {
            'min_increase_percent': min_increase_percent,
            'min_body_ratio': min_body_ratio,
            'min_cross_lines': min_cross_lines,
            'min_volume_ratio': min_volume_ratio,
            'min_turnover_rate': min_turnover_rate,
            'max_turnover_rate': max_turnover_rate,
            'recent_days': recent_days,
            'ma_periods': ma_periods_list
        }
        
        logger.info(f"策略参数: {strategy_params}")
        
        # 执行选股策略
        all_results = OneYangThreeLinesStrategy.screening_one_yang_three_lines_strategy(db, **strategy_params)
        
        # 日期范围过滤（如果提供）
        if start_date or end_date:
            filtered_results = []
            for result in all_results:
                signal_date = result.get("signal_date", "")
                if start_date and signal_date < start_date:
                    continue
                if end_date and signal_date > end_date:
                    continue
                filtered_results.append(result)
            all_results = filtered_results
        
        # 分页处理
        total = len(all_results)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = all_results[start_idx:end_idx]
        
        logger.info(f"一阳穿三线选股策略执行完成，找到 {total} 只符合条件的股票，返回第 {page} 页（共 {len(paginated_results)} 只）")
        
        return JSONResponse({
            "success": True,
            "data": paginated_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "search_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "一阳穿三线",
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            } if start_date or end_date else None
        })
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"执行一阳穿三线选股策略失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"一阳穿三线选股策略执行失败: {str(e)}"
        )
