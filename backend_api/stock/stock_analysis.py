import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import os
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from database import get_db
from models import (
    HistoricalQuotes, StockRealtimeQuote, HistoricalQuotesHK, StockRealtimeQuoteHK, 
    StockBasicInfoHK, StockBasicInfo, RSIIndicators, MACDIndicators, KDJIndicators, BOLLIndicators
)
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """计算MACD指标"""
        if len(prices) < slow:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        prices_array = np.array(prices)
        ema_fast = TechnicalIndicators._calculate_ema(prices_array, fast)
        ema_slow = TechnicalIndicators._calculate_ema(prices_array, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": round(macd_line[-1], 4),
            "signal": round(signal_line[-1], 4),
            "histogram": round(histogram[-1], 4)
        }
    
    @staticmethod
    def calculate_kdj(highs: List[float], lows: List[float], closes: List[float], period: int = 9) -> Dict[str, float]:
        """计算KDJ指标"""
        if len(closes) < period:
            return {"k": 50.0, "d": 50.0, "j": 50.0}
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        # 计算RSV
        highest_high = pd.Series(highs_array).rolling(window=period).max()
        lowest_low = pd.Series(lows_array).rolling(window=period).min()
        rsv = 100 * (closes_array - lowest_low) / (highest_high - lowest_low)
        
        # 计算K、D、J值
        k = 50.0
        d = 50.0
        
        for i in range(len(rsv)):
            if not np.isnan(rsv[i]):
                k = (2/3) * k + (1/3) * rsv[i]
                d = (2/3) * d + (1/3) * k
                j = 3 * k - 2 * d
        
        return {
            "k": round(k, 2),
            "d": round(d, 2),
            "j": round(j, 2)
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """计算布林带"""
        if len(prices) < period:
            return {"upper": 0.0, "middle": 0.0, "lower": 0.0}
        
        prices_array = np.array(prices)
        middle = np.mean(prices_array[-period:])
        std = np.std(prices_array[-period:])
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return {
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2)
        }
    
    @staticmethod
    def _calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema

class PricePrediction:
    """价格预测类"""
    
    @staticmethod
    def predict_price(historical_data: List[Dict], days: int = 30) -> Dict:
        """基于历史数据预测价格"""
        if len(historical_data) < 20:
            return {
                "target_price": 0.0,
                "change_percent": 0.0,
                "prediction_range": {"min": 0.0, "max": 0.0},
                "confidence": 0.0
            }
        
        # 提取收盘价
        closes = [float(data['close']) for data in historical_data]
        
        # 计算技术指标
        rsi = TechnicalIndicators.calculate_rsi(closes)
        macd = TechnicalIndicators.calculate_macd(closes)
        
        # 简单的线性回归预测
        x = np.arange(len(closes))
        y = np.array(closes)
        
        # 计算趋势
        slope, intercept = np.polyfit(x, y, 1)
        
        # 预测目标价格
        target_price = slope * (len(closes) + days) + intercept
        current_price = closes[-1]
        change_percent = ((target_price - current_price) / current_price) * 100
        
        # 计算预测区间（基于历史波动率）
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * np.sqrt(days)
        
        prediction_range = {
            "min": round(target_price * (1 - volatility), 2),
            "max": round(target_price * (1 + volatility), 2)
        }
        
        # 计算置信度（基于技术指标的一致性）
        confidence = PricePrediction._calculate_confidence(rsi, macd, slope)
        
        return {
            "target_price": round(target_price, 2),
            "change_percent": round(change_percent, 2),
            "prediction_range": prediction_range,
            "confidence": round(confidence, 1)
        }
    
    @staticmethod
    def _calculate_confidence(rsi: float, macd: Dict, slope: float) -> float:
        """计算预测置信度"""
        confidence = 50.0  # 基础置信度
        
        # RSI调整
        if 30 <= rsi <= 70:
            confidence += 10
        elif rsi < 30 or rsi > 70:
            confidence -= 5
        
        # MACD调整
        if macd["macd"] > 0 and macd["histogram"] > 0:
            confidence += 15
        elif macd["macd"] < 0 and macd["histogram"] < 0:
            confidence -= 10
        
        # 趋势调整
        if slope > 0:
            confidence += 10
        else:
            confidence -= 10
        
        return max(0, min(100, confidence))

class TradingRecommendation:
    """交易建议类"""
    
    @staticmethod
    def generate_recommendation(historical_data: List[Dict], current_price: float, price_prediction: Dict = None) -> Dict:
        """生成交易建议
        
        Args:
            historical_data: 历史数据
            current_price: 当前价格
            price_prediction: 价格预测结果（可选），包含target_price和change_percent
        """
        if len(historical_data) < 20:
            return {
                "action": "hold",
                "reasons": ["数据不足，无法给出建议"],
                "risk_level": "high",
                "strength": 0
            }
        
        # 提取数据
        closes = [float(data['close']) for data in historical_data]
        volumes = [float(data.get('volume', 0)) for data in historical_data]
        highs = [float(data['high']) for data in historical_data]
        lows = [float(data['low']) for data in historical_data]
        
        # 计算技术指标
        rsi = TechnicalIndicators.calculate_rsi(closes)
        macd = TechnicalIndicators.calculate_macd(closes)
        kdj = TechnicalIndicators.calculate_kdj(highs, lows, closes)
        bb = TechnicalIndicators.calculate_bollinger_bands(closes)
        
        # 分析信号
        signals = TradingRecommendation._analyze_signals(rsi, macd, kdj, bb, current_price, volumes)
        
        # 生成建议（考虑价格预测）
        recommendation = TradingRecommendation._generate_action(signals, price_prediction)
        
        return recommendation
    
    @staticmethod
    def _analyze_signals(rsi: float, macd: Dict, kdj: Dict, bb: Dict, current_price: float, volumes: List[float]) -> Dict:
        """分析技术信号"""
        signals = {
            "bullish": 0,
            "bearish": 0,
            "neutral": 0,
            "reasons": []
        }
        
        # RSI分析
        if rsi < 30:
            signals["bullish"] += 1
            signals["reasons"].append("RSI超卖，存在反弹机会")
        elif rsi > 70:
            signals["bearish"] += 1
            signals["reasons"].append("RSI超买，存在回调风险")
        else:
            signals["neutral"] += 1
        
        # MACD分析
        if macd["macd"] > 0 and macd["histogram"] > 0:
            signals["bullish"] += 1
            signals["reasons"].append("MACD金叉，趋势向上")
        elif macd["macd"] < 0 and macd["histogram"] < 0:
            signals["bearish"] += 1
            signals["reasons"].append("MACD死叉，趋势向下")
        else:
            signals["neutral"] += 1
        
        # KDJ分析
        if kdj["j"] < 20:
            signals["bullish"] += 1
            signals["reasons"].append("KDJ超卖，反弹信号")
        elif kdj["j"] > 80:
            signals["bearish"] += 1
            signals["reasons"].append("KDJ超买，回调信号")
        else:
            signals["neutral"] += 1
        
        # 布林带分析
        if current_price < bb["lower"]:
            signals["bullish"] += 1
            signals["reasons"].append("价格触及布林带下轨，反弹概率大")
        elif current_price > bb["upper"]:
            signals["bearish"] += 1
            signals["reasons"].append("价格触及布林带上轨，回调概率大")
        else:
            signals["neutral"] += 1
        
        # 成交量分析
        if len(volumes) >= 5:
            recent_volume_avg = np.mean(volumes[-5:])
            if recent_volume_avg > np.mean(volumes[-20:]):
                signals["bullish"] += 1
                signals["reasons"].append("成交量放大，支撑上涨")
        
        return signals
    
    @staticmethod
    def _generate_action(signals: Dict, price_prediction: Dict = None) -> Dict:
        """根据信号生成交易建议，考虑价格预测
        
        Args:
            signals: 技术指标信号
            price_prediction: 价格预测结果（可选）
        """
        bullish_count = signals["bullish"]
        bearish_count = signals["bearish"]
        
        # 如果有价格预测，根据预测结果调整建议
        prediction_adjustment = 0
        prediction_warning = None
        
        if price_prediction:
            change_percent = price_prediction.get('change_percent', 0)
            confidence = price_prediction.get('confidence', 0)
            
            # 如果预测跌幅超过15%，强烈看空
            if change_percent < -15:
                prediction_adjustment = -3
                prediction_warning = f"价格预测显示未来30天可能下跌{abs(change_percent):.1f}%，建议谨慎"
            # 如果预测跌幅超过10%，看空
            elif change_percent < -10:
                prediction_adjustment = -2
                prediction_warning = f"价格预测显示未来30天可能下跌{abs(change_percent):.1f}%，建议谨慎"
            # 如果预测跌幅超过5%，轻微看空
            elif change_percent < -5:
                prediction_adjustment = -1
                prediction_warning = f"价格预测显示未来30天可能下跌{abs(change_percent):.1f}%"
            # 如果预测涨幅超过15%，强烈看多
            elif change_percent > 15:
                prediction_adjustment = 3
            # 如果预测涨幅超过10%，看多
            elif change_percent > 10:
                prediction_adjustment = 2
            # 如果预测涨幅超过5%，轻微看多
            elif change_percent > 5:
                prediction_adjustment = 1
        
        # 调整看多/看空计数
        adjusted_bullish = bullish_count + prediction_adjustment
        adjusted_bearish = bearish_count - prediction_adjustment
        
        # 根据调整后的信号生成建议
        if adjusted_bullish > adjusted_bearish and adjusted_bullish >= 3:
            action = "buy"
            strength = min(100, adjusted_bullish * 25)
        elif adjusted_bearish > adjusted_bullish and adjusted_bearish >= 3:
            action = "sell"
            strength = min(100, adjusted_bearish * 25)
        else:
            action = "hold"
            strength = 50
        
        # 如果价格预测大幅下跌，但技术指标建议买入，强制改为持有或卖出
        if price_prediction and price_prediction.get('change_percent', 0) < -15:
            if action == "buy":
                action = "hold"
                strength = max(30, strength - 30)
                if prediction_warning:
                    signals["reasons"].insert(0, prediction_warning)
            elif action == "hold":
                signals["reasons"].insert(0, prediction_warning if prediction_warning else "价格预测显示大幅下跌风险")
        
        # 如果有价格预测警告，添加到理由中
        if prediction_warning and prediction_warning not in signals["reasons"]:
            signals["reasons"].append(prediction_warning)
        
        # 确定风险等级
        if strength >= 80:
            risk_level = "low"
        elif strength >= 60:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return {
            "action": action,
            "reasons": signals["reasons"],
            "risk_level": risk_level,
            "strength": strength
        }

class KeyLevels:
    """关键价位分析类（成交量加权 KDE，与 RPE 比价效应结构位同一思路）。"""

    # 与 RPE 默认 lookback / kde_base_factor 对齐
    KDE_LOOKBACK_DAYS = 250
    KDE_BASE_FACTOR = 1.0
    MAX_LEVELS = 2

    @staticmethod
    def calculate_key_levels(
        historical_data: List[Dict],
        current_price: float,
        *,
        kde_base_factor: Optional[float] = None,
        max_levels: int = 2,
    ) -> Dict:
        """
        用收盘价 + 成交量做 gaussian_kde，密度峰作为支撑/阻力。
        口径对齐 backend_core.strategies.rpe.kde_levels.extract_kde_levels：
        - 带宽 bw = max(0.01, base_factor * sigma/mu)
        - 现价下方峰 -> 支撑（由近到远）
        - 现价上方峰 -> 阻力（由近到远）
        展示侧各取最多 max_levels 个（默认 2）；按当前价（可实时）重新划分峰。
        """
        empty = {
            "resistance_levels": [],
            "support_levels": [],
            "current_price": current_price,
            "method": "kde_volume_weighted",
            "kde_bw": None,
            "kde_ok": False,
            "kde_reason": "insufficient_samples",
        }
        if not historical_data or len(historical_data) < 20:
            return empty
        try:
            price = float(current_price)
        except (TypeError, ValueError):
            return empty
        if price <= 0:
            return empty

        closes: List[float] = []
        volumes: List[float] = []
        for row in historical_data:
            try:
                closes.append(float(row["close"]))
                volumes.append(float(row.get("volume", 0) or 0))
            except (TypeError, ValueError, KeyError):
                continue

        from backend_core.strategies.rpe.kde_levels import extract_kde_levels

        factor = KeyLevels.KDE_BASE_FACTOR if kde_base_factor is None else float(kde_base_factor)
        kde = extract_kde_levels(closes, volumes, base_factor=factor)
        peaks = [float(p) for p in (kde.get("all_peaks") or []) if p is not None]

        # 按页面当前价划分（与实时价对齐）；阻力严格 > 现价，支撑严格 < 现价
        supports = sorted([p for p in peaks if 0 < p < price], reverse=True)
        resistances = sorted([p for p in peaks if p > price])

        n = max(1, int(max_levels or KeyLevels.MAX_LEVELS))
        return {
            "resistance_levels": [round(x, 2) for x in resistances[:n]],
            "support_levels": [round(x, 2) for x in supports[:n]],
            "current_price": price,
            "method": "kde_volume_weighted",
            "kde_bw": kde.get("bw"),
            "kde_ok": bool(kde.get("ok")),
            "kde_reason": kde.get("reason") or ("ok" if kde.get("ok") else "no_peaks"),
        }


class StockAnalysisService:
    """股票分析服务类"""
    
    def __init__(self):
        self.db = next(get_db())
    
    def _is_hk_stock(self, stock_code: str) -> bool:
        """判断是否为港股"""
        try:
            stock_code = str(stock_code).strip()
            # 先查询港股表
            hk_stock = self.db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == stock_code).first()
            if hk_stock:
                return True
            # 再查询A股表
            a_stock = self.db.query(StockBasicInfo).filter(StockBasicInfo.code == stock_code).first()
            if a_stock:
                return False
            # 如果两个表都没有，根据代码长度判断（港股5位，A股6位）
            return len(stock_code) == 5
        except Exception as e:
            logger.warning(f"判断股票类型失败: {str(e)}")
            # 默认根据代码长度判断
            return len(stock_code) == 5

    def _get_gemini_analysis(self, stock_code: str, historical_data: List[Dict], technical_indicators: Dict) -> str:
        """调用 Gemini 获取 AI 深度分析结果（带超时保护）"""
        
        def _call_gemini():
            """内部函数，用于在线程中执行 Gemini 调用"""
            try:
                try:
                    import google.generativeai as genai
                except ImportError:
                    logger.warning("google-generativeai 未安装，无法调用 Gemini（请 pip install google-generativeai 或保持仅用本地技术指标）")
                    return "AI 深度分析未启用：服务器未安装 google-generativeai 包。"

                # 设置你的代理端口（请根据你代理软件的实际端口修改，常见为 7890 或 1080）
                os.environ['HTTP_PROXY'] = 'http://127.0.0.1:9910'
                os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:9910'

                # 1. 配置 API 密钥
                API_KEY = "AIzaSyBH1CWisGCsTgWiPsCvjbwV60wq8I-DKgQ"
                genai.configure(api_key=API_KEY)
                
                # 使用标准的 1.5-flash 模型
                model = genai.GenerativeModel('gemini-3-flash-preview')

                # 准备上下文
                recent_data = historical_data[-10:] # 最近10个交易日数据
                
                prompt = f"""
                你是一位专业的资深股票分析师。请根据以下提供的股票数据和技术指标，为股票代码 {stock_code} 提供一份简洁而深刻的市场见解。
                
                最近价格数据:
                {recent_data}
                
                主要技术指标:
                {technical_indicators}
                
                请从以下三个维度进行分析:
                1. 趋势判断: 当前处于什么趋势？转折信号是否出现？
                2. 风险提示: 当前最核心的操作风险是什么？
                3. 具体建议: 给投资者的核心操作准则（不超过3条）。
                
                输出要求: 直接给出重点，格式清晰，不要使用模板式的开场白，保持专业且易于理解。
                """

                # 调用模型生成内容
                response = model.generate_content(prompt)
                
                if response and hasattr(response, 'text'):
                    return response.text
                return "AI 分析未能生成有效内容"
                
            except Exception as e:
                logger.error(f"Gemini 分析异常: {str(e)}")
                raise  # 重新抛出异常以便外层捕获
        
        # 使用线程池执行器添加超时保护
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_call_gemini)
                # 设置10秒超时
                result = future.result(timeout=10)
                return result
        except FutureTimeoutError:
            logger.warning(f"Gemini API 调用超时（10秒），跳过AI分析")
            return "AI 分析服务超时，请稍后重试"
        except Exception as e:
            logger.error(f"Gemini 分析异常: {str(e)}")
            return f"AI 分析服务暂不可用: {str(e)}"
    
    def get_stock_analysis(self, stock_code: str) -> Dict:
        """获取股票智能分析结果"""
        try:
            # 获取历史数据（关键价位 KDE 与 RPE 对齐，默认约 250 根）
            historical_data = self._get_historical_data(
                stock_code, days=KeyLevels.KDE_LOOKBACK_DAYS
            )
            if not historical_data:
                logger.warning(f"股票 {stock_code} 无法获取历史数据，返回空分析结果")
                return {
                    "success": False,
                    "error": "无法获取历史数据",
                    "data": {
                        "technical_indicators": {},
                        "price_prediction": {
                            "target_price": 0.0,
                            "change_percent": 0.0,
                            "prediction_range": {"min": 0.0, "max": 0.0},
                            "confidence": 0.0
                        },
                        "trading_recommendation": {
                            "action": "hold",
                            "reasons": ["数据不足，无法给出建议"],
                            "risk_level": "high",
                            "strength": 0
                        },
                        "key_levels": {
                            "resistance_levels": [],
                            "support_levels": [],
                            "current_price": 0.0
                        },
                        "current_price": 0.0,
                        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            
            # 获取当前价格
            current_price = self._get_current_price(stock_code)
            if not current_price:
                current_price = float(historical_data[-1]['close'])
            
            # 计算技术指标
            technical_indicators = self._calculate_technical_indicators(stock_code, historical_data)
            
            # 价格预测
            price_prediction = PricePrediction.predict_price(historical_data)
            
            # 交易建议（传入价格预测结果）
            trading_recommendation = TradingRecommendation.generate_recommendation(
                historical_data, 
                current_price, 
                price_prediction=price_prediction
            )
            
            # 关键价位
            key_levels = KeyLevels.calculate_key_levels(historical_data, current_price)
            
            # AI 深度分析 (Gemini) - 已屏蔽，避免配额超限
            # try:
            #     ai_insight = self._get_gemini_analysis(stock_code, historical_data, technical_indicators)
            # except Exception as e:
            #     logger.warning(f"AI分析失败，使用默认值: {str(e)}")
            #     ai_insight = "AI 分析服务暂不可用"
            ai_insight = ""  # 暂时屏蔽 Gemini 分析，避免配额超限
            
            return {
                "success": True,
                "data": {
                    "technical_indicators": technical_indicators,
                    "price_prediction": price_prediction,
                    "trading_recommendation": trading_recommendation,
                    "key_levels": key_levels,
                    "current_price": current_price,
                    "ai_insight": ai_insight,
                    "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
            return {"error": f"分析失败: {str(e)}"}
    
    def _get_historical_data(self, stock_code: str, days: int = 60) -> List[Dict]:
        """获取历史数据（支持A股和港股）"""
        try:
            is_hk = self._is_hk_stock(stock_code)
            
            if is_hk:
                # 港股：从historical_quotes_hk表查询
                query = text("""
                    SELECT code, name, date, open, high, low, close, volume, amount, 
                           change_percent, change_amount, turnover_rate
                    FROM historical_quotes_hk 
                    WHERE code = :code 
                    ORDER BY date DESC 
                    LIMIT :days
                """)
            else:
                # A股：从historical_quotes表查询
                query = text("""
                    SELECT code, name, date, open, high, low, close, volume, amount, 
                           change_percent, change, turnover_rate
                    FROM historical_quotes 
                    WHERE code = :code 
                    ORDER BY date DESC 
                    LIMIT :days
                """)
            
            result = self.db.execute(query, {"code": stock_code, "days": days})
            rows = result.fetchall()
            
            # 转换为字典列表
            data = []
            for row in rows:
                try:
                    # 处理日期格式
                    date_val = row[2]
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime("%Y-%m-%d")
                    elif isinstance(date_val, str):
                        date_str = date_val
                    else:
                        date_str = str(date_val)
                    
                    data.append({
                        "code": row[0],
                        "name": row[1],
                        "date": date_str,
                        "open": float(row[3]) if row[3] is not None else 0.0,
                        "high": float(row[4]) if row[4] is not None else 0.0,
                        "low": float(row[5]) if row[5] is not None else 0.0,
                        "close": float(row[6]) if row[6] is not None else 0.0,
                        "volume": float(row[7]) if row[7] is not None else 0.0,
                        "amount": float(row[8]) if row[8] is not None else 0.0,
                        "change_percent": float(row[9]) if row[9] is not None else 0.0,
                        "change": float(row[10]) if row[10] is not None else 0.0,  # 港股用change_amount，A股用change
                        "turnover_rate": float(row[11]) if row[11] is not None else 0.0
                    })
                except Exception as e:
                    logger.warning(f"处理历史数据行时出错: {e}, row: {row}")
                    continue
            
            # 如果数据库没有数据，尝试从akshare获取（仅对港股）
            if not data and is_hk:
                logger.info(f"数据库没有股票 {stock_code} 的历史数据，尝试从akshare获取")
                try:
                    import akshare as ak
                    from datetime import datetime, timedelta
                    
                    # 计算日期范围（最近days天）
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=days * 2)  # 多取一些，因为要排除非交易日
                    
                    end_date_str = end_date.strftime("%Y%m%d")
                    start_date_str = start_date.strftime("%Y%m%d")
                    
                    df = ak.stock_hk_hist(symbol=stock_code, period='daily', start_date=start_date_str, end_date=end_date_str, adjust='')
                    
                    if df is not None and not df.empty:
                        # 转换DataFrame为字典列表
                        for _, row_df in df.iterrows():
                            try:
                                date_val = row_df.get('日期', '')
                                if isinstance(date_val, pd.Timestamp):
                                    date_str = date_val.strftime("%Y-%m-%d")
                                else:
                                    date_str = str(date_val)
                                    if len(date_str) == 8 and date_str.isdigit():
                                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                                
                                data.append({
                                    "code": stock_code,
                                    "name": "",  # akshare接口可能没有名称
                                    "date": date_str,
                                    "open": float(row_df.get('开盘', 0)) if pd.notna(row_df.get('开盘')) else 0.0,
                                    "high": float(row_df.get('最高', 0)) if pd.notna(row_df.get('最高')) else 0.0,
                                    "low": float(row_df.get('最低', 0)) if pd.notna(row_df.get('最低')) else 0.0,
                                    "close": float(row_df.get('收盘', 0)) if pd.notna(row_df.get('收盘')) else 0.0,
                                    "volume": float(row_df.get('成交量', 0)) if pd.notna(row_df.get('成交量')) else 0.0,
                                    "amount": float(row_df.get('成交额', 0)) if pd.notna(row_df.get('成交额')) else 0.0,
                                    "change_percent": float(row_df.get('涨跌幅', 0)) if pd.notna(row_df.get('涨跌幅')) else 0.0,
                                    "change": float(row_df.get('涨跌额', 0)) if pd.notna(row_df.get('涨跌额')) else 0.0,
                                    "turnover_rate": float(row_df.get('换手率', 0)) if pd.notna(row_df.get('换手率')) else 0.0
                                })
                            except Exception as e:
                                logger.warning(f"处理akshare历史数据行时出错: {e}")
                                continue
                        
                        # 限制返回数量
                        data = data[:days]
                        logger.info(f"从akshare获取到 {len(data)} 条历史数据")
                except Exception as e:
                    logger.warning(f"从akshare获取历史数据失败: {e}")
            
            # 按日期正序排列
            if data:
                return list(reversed(data))
            else:
                return []
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_current_price(self, stock_code: str) -> Optional[float]:
        """获取当前价格（支持A股和港股）"""
        try:
            is_hk = self._is_hk_stock(stock_code)
            
            if is_hk:
                # 港股：从stock_realtime_quote_hk表获取
                latest_date_result = pd.read_sql_query("""
                    SELECT MAX(trade_date) as latest_date 
                    FROM stock_realtime_quote_hk 
                    WHERE change_percent IS NOT NULL
                """, self.db.bind)
                
                stock = None
                if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
                    latest_trade_date = latest_date_result.iloc[0]['latest_date']
                    if isinstance(latest_trade_date, str):
                        latest_trade_date = latest_trade_date[:10]
                    else:
                        latest_trade_date = str(latest_trade_date)[:10]
                    
                    stock = self.db.query(StockRealtimeQuoteHK).filter(
                        StockRealtimeQuoteHK.code == stock_code,
                        StockRealtimeQuoteHK.trade_date == latest_trade_date
                    ).first()
                
                if stock:
                    return float(stock.current_price) if stock.current_price else None
            else:
                # A股：优先从实时行情API获取最新价格
                import akshare as ak
                
                try:
                    df_bid_ask = ak.stock_bid_ask_em(symbol=stock_code)
                    if not df_bid_ask.empty:
                        bid_ask_dict = dict(zip(df_bid_ask['item'], df_bid_ask['value']))
                        current_price = bid_ask_dict.get("最新")
                        if current_price:
                            return float(current_price)
                except Exception as e:
                    logger.warning(f"从实时API获取价格失败: {str(e)}")
                
                # 如果实时API失败，从数据库获取
                latest_date_result = pd.read_sql_query("""
                    SELECT MAX(trade_date) as latest_date 
                    FROM stock_realtime_quote 
                    WHERE change_percent IS NOT NULL AND change_percent != 0
                """, self.db.bind)
                
                stock = None
                if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
                    latest_trade_date = latest_date_result.iloc[0]['latest_date']
                    stock = self.db.query(StockRealtimeQuote).filter(
                        StockRealtimeQuote.code == stock_code,
                        StockRealtimeQuote.trade_date == latest_trade_date
                    ).first()
                
                if stock:
                    return float(stock.current_price) if stock.current_price else None
            
            return None
        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return None
    
    def _calculate_technical_indicators(self, stock_code: str, historical_data: List[Dict]) -> Dict:
        """获取或计算技术指标"""
        if len(historical_data) < 20:
            return {}
        
        is_hk = self._is_hk_stock(stock_code)
        market_type = 'HK' if is_hk else 'CN'
        
        # 提取历史价格数据用于计算（备用）
        closes = [data['close'] for data in historical_data]
        highs = [data['high'] for data in historical_data]
        lows = [data['low'] for data in historical_data]
        last_close = historical_data[-1]['close']
        
        # 初始化指标数据
        rsi_val = None
        macd_val = None
        macd_hist = None
        kdj_j = None
        bb_upper = None
        bb_middle = None
        bb_lower = None
        
        # 1. 尝试从数据库获取最新RSI
        try:
            rsi_db = self.db.query(RSIIndicators).filter(
                RSIIndicators.code == stock_code,
                RSIIndicators.market_type == market_type
            ).order_by(desc(RSIIndicators.date)).first()
            if rsi_db:
                rsi_val = rsi_db.rsi6 # 通常这里显示短周期的，或者您可以根据需要选择rsi12, rsi24
        except Exception as e:
            logger.warning(f"从数据库获取RSI失败: {e}")
            
        if rsi_val is None:
            rsi_val = TechnicalIndicators.calculate_rsi(closes)
            
        # 2. 尝试从数据库获取最新MACD
        try:
            macd_db = self.db.query(MACDIndicators).filter(
                MACDIndicators.code == stock_code,
                MACDIndicators.market_type == market_type if is_hk else True # A股可能没存market_type或者存的不同，模型定义注释是'A股'
            ).order_by(desc(MACDIndicators.date)).first()
            # 兼容性处理：如果上面的查询没结果，尝试不带market_type
            if not macd_db and not is_hk:
                 macd_db = self.db.query(MACDIndicators).filter(
                    MACDIndicators.code == stock_code
                ).order_by(desc(MACDIndicators.date)).first()
                 
            if macd_db:
                macd_val = macd_db.macd
                macd_hist = macd_db.macd # 这里通常指的是柱状图值，在模型里macd字段存的就是DIF-DEA
        except Exception as e:
            logger.warning(f"从数据库获取MACD失败: {e}")
            
        if macd_val is None:
            calc_macd = TechnicalIndicators.calculate_macd(closes)
            macd_val = calc_macd["macd"]
            macd_hist = calc_macd["histogram"]
            
        # 3. 尝试从数据库获取最新KDJ
        try:
            kdj_db = self.db.query(KDJIndicators).filter(
                KDJIndicators.code == stock_code,
                KDJIndicators.market_type == market_type
            ).order_by(desc(KDJIndicators.date)).first()
            if kdj_db:
                kdj_j = kdj_db.j
        except Exception as e:
            logger.warning(f"从数据库获取KDJ失败: {e}")
            
        if kdj_j is None:
            calc_kdj = TechnicalIndicators.calculate_kdj(highs, lows, closes)
            kdj_j = calc_kdj["j"]
            
        # 4. 尝试从数据库获取最新BOLL
        try:
            bb_db = self.db.query(BOLLIndicators).filter(
                BOLLIndicators.code == stock_code,
                BOLLIndicators.market_type == market_type
            ).order_by(desc(BOLLIndicators.date)).first()
            if bb_db:
                bb_upper = bb_db.upper
                bb_middle = bb_db.mid
                bb_lower = bb_db.lower
        except Exception as e:
            logger.warning(f"从数据库获取BOLL失败: {e}")
            
        if bb_upper is None:
            calc_bb = TechnicalIndicators.calculate_bollinger_bands(closes)
            bb_upper = calc_bb["upper"]
            bb_middle = calc_bb["middle"]
            bb_lower = calc_bb["lower"]
            
        # 判断信号 (信号逻辑保持基于计算结果，但数据源优先选数据库)
        rsi_signal = "超卖" if rsi_val < 30 else "超买" if rsi_val > 70 else "中性"
        macd_signal = "看多" if macd_val > 0 else "看空" if macd_val < 0 else "中性"
        kdj_signal = "超卖" if kdj_j < 20 else "超买" if kdj_j > 80 else "中性"
        
        # 改进 BOLL 信号逻辑
        if last_close > bb_upper:
            bb_signal = "超买"
            bb_desc = "突破上轨"
        elif last_close < bb_lower:
            bb_signal = "超卖"
            bb_desc = "跌破下轨"
        elif last_close > bb_middle:
            bb_signal = "看多"
            bb_desc = "中轨上方"
        elif last_close < bb_middle:
            bb_signal = "看空"
            bb_desc = "中轨下方"
        else:
            bb_signal = "中性"
            bb_desc = "中轨"
        
        return {
            "rsi": {
                "value": round(rsi_val, 2),
                "signal": rsi_signal
            },
            "macd": {
                "value": round(macd_val, 3),
                "signal": macd_signal
            },
            "kdj": {
                "value": round(kdj_j, 2),
                "signal": kdj_signal
            },
            "bollinger_bands": {
                "upper": bb_upper,
                "middle": bb_middle,
                "lower": bb_lower,
                "signal": bb_signal,
                "desc": bb_desc
            }
        } 