"""
PVFRS策略股票详细信息展示功能
实现单只股票的详细PVFRS分析指标获取和展示
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict

from .models import MarketData, PVFRSIndicators, Signal, SignalType
from .frontend_interface import StockDetail, FrontendInterface

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class DimensionAnalysisDetail:
    """维度分析详情数据结构"""
    dimension_name: str          # 维度名称
    is_valid: bool              # 是否满足条件
    score: float                # 维度评分 (0-1)
    
    # 具体指标
    indicators: Dict[str, Any]   # 指标数值
    conditions: Dict[str, bool]  # 条件检查结果
    
    # 分析说明
    analysis_summary: str        # 分析汇总
    key_points: List[str]       # 关键要点
    risk_factors: List[str]     # 风险因素


@dataclass
class ResonanceAnalysisDetail:
    """共振分析详情数据结构"""
    has_resonance: bool          # 是否存在三维共振
    resonance_strength: float   # 共振强度 (0-1)
    resonance_level: str        # 共振等级
    
    # 各维度贡献
    price_contribution: float    # 价格维度贡献
    frequency_contribution: float # 频率维度贡献
    volume_contribution: float   # 成交量维度贡献
    
    # 共振分析
    resonance_factors: List[str] # 共振因素
    resonance_quality: str      # 共振质量评估
    sustainability: str         # 可持续性评估


@dataclass
class SignalAnalysisDetail:
    """信号分析详情数据结构"""
    has_signal: bool            # 是否有信号
    signal_type: str           # 信号类型
    signal_strength: float     # 信号强度
    signal_confidence: float   # 信号置信度
    
    # 信号详情
    signal_reason: str         # 信号原因
    entry_price: float         # 建议入场价格
    entry_timing: str          # 入场时机评估
    
    # 风险控制
    stop_loss_price: float     # 止损价格
    take_profit_price: float   # 止盈价格
    position_size_suggestion: float  # 建议仓位大小
    
    # 信号质量
    signal_quality_factors: List[str]  # 信号质量因素
    risk_warnings: List[str]          # 风险警告


@dataclass
class InvestmentAdviceDetail:
    """投资建议详情数据结构"""
    recommendation: str         # 投资建议 (买入/持有/卖出)
    confidence_level: str      # 置信水平
    investment_horizon: str    # 投资时间范围
    
    # 建议详情
    reasons: List[str]         # 建议理由
    key_advantages: List[str]  # 主要优势
    main_risks: List[str]      # 主要风险
    
    # 操作建议
    entry_strategy: str        # 入场策略
    exit_strategy: str         # 出场策略
    position_management: str   # 仓位管理
    
    # 监控要点
    monitoring_points: List[str]  # 监控要点
    trigger_conditions: List[str] # 触发条件


class StockDetailFormatter:
    """股票详细信息格式化器
    
    负责将股票的完整PVFRS分析结果格式化为适合前端展示的详细信息。
    """
    
    def __init__(self):
        """初始化格式化器"""
        # 维度评分权重
        self.dimension_weights = {
            'price': 0.4,      # 价格维度权重
            'frequency': 0.3,  # 频率维度权重
            'volume': 0.3      # 成交量维度权重
        }
        
        # 共振强度等级
        self.resonance_levels = {
            'strong': (0.8, 1.0),    # 强共振
            'medium': (0.5, 0.8),    # 中等共振
            'weak': (0.0, 0.5)       # 弱共振
        }
        
        # 信号置信度等级
        self.confidence_levels = {
            'high': (0.8, 1.0),      # 高置信度
            'medium': (0.5, 0.8),    # 中等置信度
            'low': (0.0, 0.5)        # 低置信度
        }
    
    def format_stock_detail(self, stock_detail: StockDetail) -> Dict:
        """格式化股票详细信息
        
        Args:
            stock_detail: 原始股票详细信息
            
        Returns:
            Dict: 格式化后的详细信息
        """
        try:
            # 格式化各维度分析
            price_analysis = self._format_price_dimension(stock_detail.price_dimension)
            frequency_analysis = self._format_frequency_dimension(stock_detail.frequency_dimension)
            volume_analysis = self._format_volume_dimension(stock_detail.volume_dimension)
            
            # 格式化共振分析
            resonance_analysis = self._format_resonance_analysis(stock_detail.resonance_analysis)
            
            # 格式化信号分析
            signal_analysis = self._format_signal_analysis(stock_detail.signal_analysis)
            
            # 格式化投资建议
            investment_advice = self._format_investment_advice(stock_detail.investment_advice)
            
            # 计算综合评分
            overall_score = self._calculate_overall_score(
                price_analysis, frequency_analysis, volume_analysis, resonance_analysis
            )
            
            formatted_detail = {
                # 基本信息
                'basic_info': {
                    'symbol': stock_detail.symbol,
                    'name': stock_detail.name,
                    'current_price': stock_detail.current_price,
                    'analysis_date': stock_detail.analysis_date,
                    'analysis_timestamp': datetime.now().isoformat()
                },
                
                # 综合评估
                'overall_assessment': {
                    'overall_score': overall_score,
                    'score_level': self._get_score_level(overall_score),
                    'key_strengths': self._extract_key_strengths(
                        price_analysis, frequency_analysis, volume_analysis
                    ),
                    'main_concerns': self._extract_main_concerns(
                        price_analysis, frequency_analysis, volume_analysis
                    )
                },
                
                # 三维分析详情
                'dimension_analysis': {
                    'price_dimension': price_analysis.to_dict(),
                    'frequency_dimension': frequency_analysis.to_dict(),
                    'volume_dimension': volume_analysis.to_dict()
                },
                
                # 共振分析详情
                'resonance_analysis': resonance_analysis.to_dict(),
                
                # 信号分析详情
                'signal_analysis': signal_analysis.to_dict(),
                
                # 投资建议详情
                'investment_advice': investment_advice.to_dict(),
                
                # 风险评估
                'risk_assessment': self._format_risk_assessment(stock_detail.risk_assessment),
                
                # 策略评估
                'strategy_assessment': self._format_strategy_assessment(stock_detail.strategy_assessment)
            }
            
            logger.info(f"成功格式化股票 {stock_detail.symbol} 详细信息")
            return formatted_detail
            
        except Exception as e:
            logger.error(f"格式化股票详细信息失败: {str(e)}")
            return {
                'error': f"格式化股票详细信息失败: {str(e)}",
                'basic_info': {
                    'symbol': stock_detail.symbol if hasattr(stock_detail, 'symbol') else 'unknown',
                    'analysis_timestamp': datetime.now().isoformat()
                }
            }
    
    def _format_price_dimension(self, price_dimension: Dict) -> DimensionAnalysisDetail:
        """格式化价格维度分析
        
        Args:
            price_dimension: 价格维度数据
            
        Returns:
            DimensionAnalysisDetail: 格式化后的价格维度分析
        """
        # 提取关键指标
        macro_displacement = price_dimension.get('macro_displacement', 0)
        instant_deviation = price_dimension.get('instant_deviation', 0)
        avg_price_20d = price_dimension.get('avg_price_20d', 1)
        amplitude_ratio = macro_displacement / avg_price_20d if avg_price_20d > 0 else 0
        
        # 条件检查
        conditions = {
            'macro_displacement_positive': macro_displacement > 0,
            'instant_deviation_positive': instant_deviation > 0,
            'amplitude_ratio_valid': 0.005 <= amplitude_ratio <= 0.5
        }
        
        # 计算维度评分
        score = sum(conditions.values()) / len(conditions)
        is_valid = price_dimension.get('price_dimension_valid', False)
        
        # 生成分析要点
        key_points = []
        risk_factors = []
        
        if conditions['macro_displacement_positive']:
            key_points.append(f"宏观位移向上 ({macro_displacement:.2f})")
        else:
            risk_factors.append("宏观位移为负，价格趋势向下")
        
        if conditions['instant_deviation_positive']:
            key_points.append(f"即时强度向上 ({instant_deviation:.2f})")
        else:
            risk_factors.append("即时强度为负，当前价格低于平均价格")
        
        if conditions['amplitude_ratio_valid']:
            key_points.append(f"幅度系数合理 ({amplitude_ratio:.3f})")
        else:
            risk_factors.append(f"幅度系数异常 ({amplitude_ratio:.3f})")
        
        # 生成分析汇总
        if is_valid:
            analysis_summary = "价格维度表现良好，满足强势演化条件"
        else:
            analysis_summary = "价格维度存在不足，未完全满足条件"
        
        return DimensionAnalysisDetail(
            dimension_name="价格维度",
            is_valid=is_valid,
            score=score,
            indicators={
                'macro_displacement': macro_displacement,
                'instant_deviation': instant_deviation,
                'avg_price_20d': avg_price_20d,
                'amplitude_ratio': amplitude_ratio
            },
            conditions=conditions,
            analysis_summary=analysis_summary,
            key_points=key_points,
            risk_factors=risk_factors
        )
    
    def _format_frequency_dimension(self, frequency_dimension: Dict) -> DimensionAnalysisDetail:
        """格式化频率维度分析
        
        Args:
            frequency_dimension: 频率维度数据
            
        Returns:
            DimensionAnalysisDetail: 格式化后的频率维度分析
        """
        # 提取关键指标
        rising_days = frequency_dimension.get('rising_days', 0)
        falling_days = frequency_dimension.get('falling_days', 0)
        frequency_advantage = frequency_dimension.get('frequency_advantage', False)
        has_false_prosperity = frequency_dimension.get('has_false_prosperity', False)
        
        # 条件检查
        conditions = {
            'frequency_advantage': frequency_advantage,
            'no_false_prosperity': not has_false_prosperity,
            'sufficient_rising_days': rising_days >= 8
        }
        
        # 计算维度评分
        score = sum(conditions.values()) / len(conditions)
        is_valid = frequency_dimension.get('frequency_dimension_valid', False)
        
        # 生成分析要点
        key_points = []
        risk_factors = []
        
        if frequency_advantage:
            key_points.append(f"上涨天数优势明显 (上涨{rising_days}天 vs 下跌{falling_days}天)")
        else:
            risk_factors.append(f"上涨天数不足 (上涨{rising_days}天 vs 下跌{falling_days}天)")
        
        if not has_false_prosperity:
            key_points.append("无虚假繁荣现象，趋势稳定")
        else:
            risk_factors.append("存在虚假繁荣，需谨慎对待")
        
        if conditions['sufficient_rising_days']:
            key_points.append("上涨天数充足，市场共识良好")
        else:
            risk_factors.append("上涨天数不足，市场共识有待加强")
        
        # 生成分析汇总
        if is_valid:
            analysis_summary = "频率维度表现优秀，市场微观共识强烈"
        else:
            analysis_summary = "频率维度有待改善，市场共识不够稳定"
        
        return DimensionAnalysisDetail(
            dimension_name="频率维度",
            is_valid=is_valid,
            score=score,
            indicators={
                'rising_days': rising_days,
                'falling_days': falling_days,
                'frequency_advantage': frequency_advantage,
                'has_false_prosperity': has_false_prosperity
            },
            conditions=conditions,
            analysis_summary=analysis_summary,
            key_points=key_points,
            risk_factors=risk_factors
        )
    
    def _format_volume_dimension(self, volume_dimension: Dict) -> DimensionAnalysisDetail:
        """格式化成交量维度分析
        
        Args:
            volume_dimension: 成交量维度数据
            
        Returns:
            DimensionAnalysisDetail: 格式化后的成交量维度分析
        """
        # 提取关键指标
        avg_volume_20d = volume_dimension.get('avg_volume_20d', 0)
        current_volume = volume_dimension.get('current_volume', 0)
        efficiency_ratio = volume_dimension.get('efficiency_ratio', 0)
        volume_price_resonance = volume_dimension.get('volume_price_resonance', False)
        strong_fund_support = volume_dimension.get('strong_fund_support', False)
        
        # 条件检查
        conditions = {
            'volume_efficiency': current_volume > avg_volume_20d,
            'volume_price_resonance': volume_price_resonance,
            'strong_fund_support': strong_fund_support,
            'efficiency_ratio_good': efficiency_ratio > 1.2
        }
        
        # 计算维度评分
        score = sum(conditions.values()) / len(conditions)
        is_valid = volume_dimension.get('volume_dimension_valid', False)
        
        # 生成分析要点
        key_points = []
        risk_factors = []
        
        if conditions['volume_efficiency']:
            key_points.append(f"成交量效率良好 (当前{current_volume:.0f} vs 平均{avg_volume_20d:.0f})")
        else:
            risk_factors.append("成交量不足，资金动力有限")
        
        if volume_price_resonance:
            key_points.append("量价共振明显，资金推动有力")
        else:
            risk_factors.append("量价配合不佳，上涨缺乏资金支撑")
        
        if strong_fund_support:
            key_points.append("资金支撑强劲，趋势可持续性好")
        else:
            risk_factors.append("资金支撑不足，趋势可持续性存疑")
        
        if conditions['efficiency_ratio_good']:
            key_points.append(f"效率比优秀 ({efficiency_ratio:.2f})")
        else:
            risk_factors.append(f"效率比偏低 ({efficiency_ratio:.2f})")
        
        # 生成分析汇总
        if is_valid:
            analysis_summary = "成交量维度表现出色，资金动力充足"
        else:
            analysis_summary = "成交量维度表现一般，资金支撑有待加强"
        
        return DimensionAnalysisDetail(
            dimension_name="成交量维度",
            is_valid=is_valid,
            score=score,
            indicators={
                'avg_volume_20d': avg_volume_20d,
                'current_volume': current_volume,
                'efficiency_ratio': efficiency_ratio,
                'volume_price_resonance': volume_price_resonance,
                'strong_fund_support': strong_fund_support
            },
            conditions=conditions,
            analysis_summary=analysis_summary,
            key_points=key_points,
            risk_factors=risk_factors
        )
    
    def _format_resonance_analysis(self, resonance_analysis: Dict) -> ResonanceAnalysisDetail:
        """格式化共振分析
        
        Args:
            resonance_analysis: 共振分析数据
            
        Returns:
            ResonanceAnalysisDetail: 格式化后的共振分析
        """
        # 提取共振信息
        signal = resonance_analysis.get('signal')
        details = resonance_analysis.get('details', {})
        
        has_resonance = signal is not None
        resonance_strength = details.get('resonance_result', {}).get('resonance_strength', 0)
        
        # 确定共振等级
        resonance_level = 'weak'
        for level, (min_val, max_val) in self.resonance_levels.items():
            if min_val <= resonance_strength < max_val:
                resonance_level = level
                break
        
        # 计算各维度贡献（简化计算）
        price_contribution = resonance_strength * 0.4
        frequency_contribution = resonance_strength * 0.3
        volume_contribution = resonance_strength * 0.3
        
        # 生成共振因素
        resonance_factors = []
        if has_resonance:
            resonance_factors.append("三维条件同时满足")
            if resonance_strength >= 0.8:
                resonance_factors.append("共振强度极高")
            elif resonance_strength >= 0.5:
                resonance_factors.append("共振强度良好")
            
            resonance_factors.append("高效率演化轨道确认")
        
        # 共振质量评估
        if resonance_strength >= 0.8:
            resonance_quality = "优秀"
            sustainability = "高"
        elif resonance_strength >= 0.5:
            resonance_quality = "良好"
            sustainability = "中等"
        else:
            resonance_quality = "一般"
            sustainability = "较低"
        
        return ResonanceAnalysisDetail(
            has_resonance=has_resonance,
            resonance_strength=resonance_strength,
            resonance_level=resonance_level,
            price_contribution=price_contribution,
            frequency_contribution=frequency_contribution,
            volume_contribution=volume_contribution,
            resonance_factors=resonance_factors,
            resonance_quality=resonance_quality,
            sustainability=sustainability
        )
    
    def _format_signal_analysis(self, signal_analysis: Dict) -> SignalAnalysisDetail:
        """格式化信号分析
        
        Args:
            signal_analysis: 信号分析数据
            
        Returns:
            SignalAnalysisDetail: 格式化后的信号分析
        """
        signals = signal_analysis.get('signals', [])
        signal_summary = signal_analysis.get('signal_summary', {})
        entry_timing_analysis = signal_analysis.get('entry_timing_analysis', {})
        
        # 检查是否有买入信号
        buy_signals = [s for s in signals if s.get('signal_type') == 'buy']
        has_signal = len(buy_signals) > 0
        
        if has_signal:
            # 取最强的买入信号
            strongest_signal = max(buy_signals, key=lambda x: x.get('strength', 0))
            signal_type = strongest_signal.get('signal_type', 'buy')
            signal_strength = strongest_signal.get('strength', 0)
            signal_reason = strongest_signal.get('reason', '')
            entry_price = strongest_signal.get('price', 0)
        else:
            signal_type = 'hold'
            signal_strength = 0
            signal_reason = '未满足买入条件'
            entry_price = 0
        
        # 计算信号置信度
        signal_confidence = signal_strength * 0.9 if has_signal else 0
        
        # 确定置信度等级
        confidence_level = 'low'
        for level, (min_val, max_val) in self.confidence_levels.items():
            if min_val <= signal_confidence < max_val:
                confidence_level = level
                break
        
        # 入场时机评估
        entry_timing = "良好" if has_signal and signal_strength >= 0.7 else "一般" if has_signal else "不建议"
        
        # 风险控制建议（简化计算）
        stop_loss_price = entry_price * 0.95 if entry_price > 0 else 0
        take_profit_price = entry_price * 1.15 if entry_price > 0 else 0
        position_size_suggestion = min(0.1, signal_strength * 0.15) if has_signal else 0
        
        # 信号质量因素
        signal_quality_factors = []
        risk_warnings = []
        
        if has_signal:
            if signal_strength >= 0.8:
                signal_quality_factors.append("信号强度极高")
            elif signal_strength >= 0.5:
                signal_quality_factors.append("信号强度良好")
            
            signal_quality_factors.append("三维共振确认")
            
            if signal_strength < 0.6:
                risk_warnings.append("信号强度偏低，建议谨慎")
        else:
            risk_warnings.append("无买入信号，不建议入场")
        
        return SignalAnalysisDetail(
            has_signal=has_signal,
            signal_type=signal_type,
            signal_strength=signal_strength,
            signal_confidence=signal_confidence,
            signal_reason=signal_reason,
            entry_price=entry_price,
            entry_timing=entry_timing,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            position_size_suggestion=position_size_suggestion,
            signal_quality_factors=signal_quality_factors,
            risk_warnings=risk_warnings
        )
    
    def _format_investment_advice(self, investment_advice: Dict) -> InvestmentAdviceDetail:
        """格式化投资建议
        
        Args:
            investment_advice: 投资建议数据
            
        Returns:
            InvestmentAdviceDetail: 格式化后的投资建议
        """
        recommendation = investment_advice.get('recommendation', 'HOLD')
        confidence = investment_advice.get('confidence', 0)
        reasons = investment_advice.get('reasons', [])
        risk_level = investment_advice.get('risk_level', 'MEDIUM')
        suggested_position_size = investment_advice.get('suggested_position_size', 0)
        
        # 转换推荐类型
        recommendation_map = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有'
        }
        recommendation_cn = recommendation_map.get(recommendation, '持有')
        
        # 确定置信水平
        if confidence >= 0.8:
            confidence_level = '高'
        elif confidence >= 0.5:
            confidence_level = '中等'
        else:
            confidence_level = '低'
        
        # 投资时间范围
        if recommendation == 'BUY':
            investment_horizon = '短中期 (1-3个月)'
        else:
            investment_horizon = '观望'
        
        # 主要优势和风险
        key_advantages = []
        main_risks = []
        
        if recommendation == 'BUY':
            key_advantages.extend([
                "三维共振信号确认",
                "技术指标支持上涨",
                "资金面表现良好"
            ])
            main_risks.extend([
                "市场整体波动风险",
                "个股基本面变化风险"
            ])
        else:
            main_risks.extend([
                "技术指标不够强烈",
                "市场环境不确定性"
            ])
        
        # 操作策略
        if recommendation == 'BUY':
            entry_strategy = "分批建仓，控制仓位"
            exit_strategy = "设置止盈止损，动态调整"
            position_management = f"建议仓位: {suggested_position_size:.1%}"
        else:
            entry_strategy = "暂不建议入场"
            exit_strategy = "继续观望"
            position_management = "空仓观望"
        
        # 监控要点
        monitoring_points = [
            "关注三维指标变化",
            "监控成交量变化",
            "注意市场整体走势"
        ]
        
        # 触发条件
        trigger_conditions = []
        if recommendation == 'BUY':
            trigger_conditions.extend([
                "信号强度持续维持",
                "成交量配合良好"
            ])
        else:
            trigger_conditions.extend([
                "等待更强烈的买入信号",
                "关注技术指标改善"
            ])
        
        return InvestmentAdviceDetail(
            recommendation=recommendation_cn,
            confidence_level=confidence_level,
            investment_horizon=investment_horizon,
            reasons=reasons,
            key_advantages=key_advantages,
            main_risks=main_risks,
            entry_strategy=entry_strategy,
            exit_strategy=exit_strategy,
            position_management=position_management,
            monitoring_points=monitoring_points,
            trigger_conditions=trigger_conditions
        )
    
    def _format_risk_assessment(self, risk_assessment: Dict) -> Dict:
        """格式化风险评估
        
        Args:
            risk_assessment: 风险评估数据
            
        Returns:
            Dict: 格式化后的风险评估
        """
        overall_risk_score = risk_assessment.get('overall_risk_score', 0.5)
        risk_factors = risk_assessment.get('risk_factors', [])
        risk_level = risk_assessment.get('risk_level', 'MEDIUM')
        
        # 风险等级映射
        risk_level_map = {
            'LOW': '低风险',
            'MEDIUM': '中等风险',
            'HIGH': '高风险'
        }
        risk_level_cn = risk_level_map.get(risk_level, '中等风险')
        
        return {
            'overall_risk_score': overall_risk_score,
            'risk_level': risk_level_cn,
            'risk_factors': risk_factors,
            'risk_description': self._get_risk_description(overall_risk_score),
            'risk_mitigation': self._get_risk_mitigation_suggestions(risk_level)
        }
    
    def _format_strategy_assessment(self, strategy_assessment: Dict) -> Dict:
        """格式化策略评估
        
        Args:
            strategy_assessment: 策略评估数据
            
        Returns:
            Dict: 格式化后的策略评估
        """
        return {
            'has_buy_signal': strategy_assessment.get('has_buy_signal', False),
            'max_signal_strength': strategy_assessment.get('max_signal_strength', 0),
            'three_dimension_resonance': strategy_assessment.get('three_dimension_resonance', False),
            'high_efficiency_trajectory': strategy_assessment.get('high_efficiency_trajectory', False),
            'overall_score': strategy_assessment.get('overall_score', 0),
            'strategy_summary': self._generate_strategy_summary(strategy_assessment)
        }
    
    def _calculate_overall_score(self, price_analysis: DimensionAnalysisDetail,
                               frequency_analysis: DimensionAnalysisDetail,
                               volume_analysis: DimensionAnalysisDetail,
                               resonance_analysis: ResonanceAnalysisDetail) -> float:
        """计算综合评分
        
        Args:
            price_analysis: 价格维度分析
            frequency_analysis: 频率维度分析
            volume_analysis: 成交量维度分析
            resonance_analysis: 共振分析
            
        Returns:
            float: 综合评分 (0-1)
        """
        # 维度评分加权
        dimension_score = (
            price_analysis.score * self.dimension_weights['price'] +
            frequency_analysis.score * self.dimension_weights['frequency'] +
            volume_analysis.score * self.dimension_weights['volume']
        )
        
        # 共振强度权重
        resonance_score = resonance_analysis.resonance_strength * 0.3
        
        # 综合评分
        overall_score = dimension_score * 0.7 + resonance_score
        
        return min(1.0, max(0.0, overall_score))
    
    def _get_score_level(self, score: float) -> str:
        """获取评分等级
        
        Args:
            score: 评分
            
        Returns:
            str: 评分等级
        """
        if score >= 0.8:
            return '优秀'
        elif score >= 0.6:
            return '良好'
        elif score >= 0.4:
            return '一般'
        else:
            return '较差'
    
    def _extract_key_strengths(self, price_analysis: DimensionAnalysisDetail,
                             frequency_analysis: DimensionAnalysisDetail,
                             volume_analysis: DimensionAnalysisDetail) -> List[str]:
        """提取关键优势
        
        Args:
            price_analysis: 价格维度分析
            frequency_analysis: 频率维度分析
            volume_analysis: 成交量维度分析
            
        Returns:
            List[str]: 关键优势列表
        """
        strengths = []
        
        # 收集各维度的关键要点
        if price_analysis.is_valid:
            strengths.extend(price_analysis.key_points[:2])  # 取前2个要点
        
        if frequency_analysis.is_valid:
            strengths.extend(frequency_analysis.key_points[:2])
        
        if volume_analysis.is_valid:
            strengths.extend(volume_analysis.key_points[:2])
        
        return strengths[:5]  # 最多返回5个优势
    
    def _extract_main_concerns(self, price_analysis: DimensionAnalysisDetail,
                             frequency_analysis: DimensionAnalysisDetail,
                             volume_analysis: DimensionAnalysisDetail) -> List[str]:
        """提取主要关注点
        
        Args:
            price_analysis: 价格维度分析
            frequency_analysis: 频率维度分析
            volume_analysis: 成交量维度分析
            
        Returns:
            List[str]: 主要关注点列表
        """
        concerns = []
        
        # 收集各维度的风险因素
        concerns.extend(price_analysis.risk_factors[:2])
        concerns.extend(frequency_analysis.risk_factors[:2])
        concerns.extend(volume_analysis.risk_factors[:2])
        
        return concerns[:5]  # 最多返回5个关注点
    
    def _get_risk_description(self, risk_score: float) -> str:
        """获取风险描述
        
        Args:
            risk_score: 风险评分
            
        Returns:
            str: 风险描述
        """
        if risk_score < 0.3:
            return "风险较低，技术指标支持，适合稳健投资者"
        elif risk_score < 0.7:
            return "风险中等，需要密切关注市场变化"
        else:
            return "风险较高，建议谨慎操作或等待更好时机"
    
    def _get_risk_mitigation_suggestions(self, risk_level: str) -> List[str]:
        """获取风险缓解建议
        
        Args:
            risk_level: 风险等级
            
        Returns:
            List[str]: 风险缓解建议
        """
        if risk_level == 'LOW':
            return [
                "保持正常仓位管理",
                "设置合理止盈止损",
                "关注市场整体走势"
            ]
        elif risk_level == 'MEDIUM':
            return [
                "适当降低仓位",
                "加强风险监控",
                "设置较紧的止损",
                "分散投资降低风险"
            ]
        else:  # HIGH
            return [
                "严格控制仓位",
                "设置严格止损",
                "考虑暂缓入场",
                "等待更好的入场时机"
            ]
    
    def _generate_strategy_summary(self, strategy_assessment: Dict) -> str:
        """生成策略汇总
        
        Args:
            strategy_assessment: 策略评估数据
            
        Returns:
            str: 策略汇总
        """
        has_signal = strategy_assessment.get('has_buy_signal', False)
        resonance = strategy_assessment.get('three_dimension_resonance', False)
        overall_score = strategy_assessment.get('overall_score', 0)
        
        if has_signal and resonance and overall_score >= 0.7:
            return "PVFRS策略信号强烈，三维共振确认，建议关注"
        elif has_signal and overall_score >= 0.5:
            return "PVFRS策略信号一般，部分条件满足，可适度关注"
        else:
            return "PVFRS策略信号不足，建议继续观望"


class StockDetailManager:
    """股票详细信息管理器
    
    管理股票详细信息的获取、格式化和展示逻辑。
    """
    
    def __init__(self, frontend_interface: FrontendInterface):
        """初始化详细信息管理器
        
        Args:
            frontend_interface: 前端接口实例
        """
        self.frontend_interface = frontend_interface
        self.formatter = StockDetailFormatter()
        
        logger.info("股票详细信息管理器初始化完成")
    
    def get_formatted_stock_detail(self, symbol: str) -> Dict:
        """获取格式化的股票详细信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 格式化后的股票详细信息
        """
        try:
            # 获取原始详细信息
            stock_detail = self.frontend_interface.get_stock_detail(symbol)
            
            # 格式化详细信息
            formatted_detail = self.formatter.format_stock_detail(stock_detail)
            
            logger.info(f"成功获取股票 {symbol} 格式化详细信息")
            return formatted_detail
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 格式化详细信息失败: {str(e)}")
            return {
                'error': f"获取股票详细信息失败: {str(e)}",
                'basic_info': {
                    'symbol': symbol,
                    'analysis_timestamp': datetime.now().isoformat()
                }
            }


# 便捷函数
def create_stock_detail_manager(frontend_interface: FrontendInterface) -> StockDetailManager:
    """创建股票详细信息管理器
    
    Args:
        frontend_interface: 前端接口实例
        
    Returns:
        StockDetailManager: 详细信息管理器实例
    """
    return StockDetailManager(frontend_interface)