import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db
from ..models import HistoricalQuotes, StockRealtimeQuote

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
    def generate_recommendation(historical_data: List[Dict], current_price: float) -> Dict:
        """生成交易建议"""
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
        
        # 生成建议
        recommendation = TradingRecommendation._generate_action(signals)
        
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
    def _generate_action(signals: Dict) -> Dict:
        """根据信号生成交易建议"""
        bullish_count = signals["bullish"]
        bearish_count = signals["bearish"]
        
        if bullish_count > bearish_count and bullish_count >= 3:
            action = "buy"
            strength = min(100, bullish_count * 25)
        elif bearish_count > bullish_count and bearish_count >= 3:
            action = "sell"
            strength = min(100, bearish_count * 25)
        else:
            action = "hold"
            strength = 50
        
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
    """关键价位分析类"""
    
    @staticmethod
    def calculate_key_levels(historical_data: List[Dict], current_price: float) -> Dict:
        """计算关键支撑阻力位"""
        if len(historical_data) < 20:
            return {
                "resistance_levels": [],
                "support_levels": [],
                "current_price": current_price
            }
        
        # 提取数据
        highs = [float(data['high']) for data in historical_data]
        lows = [float(data['low']) for data in historical_data]
        closes = [float(data['close']) for data in historical_data]
        volumes = [float(data.get('volume', 0)) for data in historical_data]
        
        # 计算支撑位（基于近期低点和重要价位）
        support_levels = KeyLevels._find_support_levels(lows, closes, volumes, current_price)
        
        # 计算阻力位（基于近期高点和重要价位）
        resistance_levels = KeyLevels._find_resistance_levels(highs, closes, volumes, current_price)
        
        return {
            "resistance_levels": resistance_levels,
            "support_levels": support_levels,
            "current_price": current_price
        }
    
    @staticmethod
    def _find_support_levels(lows: List[float], closes: List[float], volumes: List[float], current_price: float) -> List[float]:
        """寻找支撑位"""
        support_levels = []
        
        # 1. 寻找近期重要低点（最近30天）
        recent_lows = lows[-30:] if len(lows) >= 30 else lows
        recent_closes = closes[-30:] if len(closes) >= 30 else closes
        recent_volumes = volumes[-30:] if len(volumes) >= 30 else volumes
        
        # 找出局部最低点
        for i in range(1, len(recent_lows) - 1):
            if (recent_lows[i] < recent_lows[i-1] and 
                recent_lows[i] < recent_lows[i+1] and
                recent_lows[i] < current_price):
                support_levels.append(recent_lows[i])
        
        # 2. 添加心理支撑位（整数价位）
        for i in range(int(current_price), int(current_price) - 5, -1):
            if i > 0 and i < current_price:
                support_levels.append(float(i))
        
        # 3. 添加技术支撑位（移动平均线附近）
        if len(closes) >= 20:
            ma20 = sum(closes[-20:]) / 20
            if ma20 < current_price:
                support_levels.append(round(ma20, 2))
        
        # 去重并排序
        support_levels = list(set(support_levels))
        support_levels = [round(level, 2) for level in support_levels if level < current_price]
        support_levels.sort(reverse=True)
        
        return support_levels[:3]
    
    @staticmethod
    def _find_resistance_levels(highs: List[float], closes: List[float], volumes: List[float], current_price: float) -> List[float]:
        """寻找阻力位"""
        resistance_levels = []
        
        # 1. 寻找近期重要高点（最近30天）
        recent_highs = highs[-30:] if len(highs) >= 30 else highs
        recent_closes = closes[-30:] if len(closes) >= 30 else closes
        recent_volumes = volumes[-30:] if len(volumes) >= 30 else volumes
        
        # 找出局部最高点
        for i in range(1, len(recent_highs) - 1):
            if (recent_highs[i] > recent_highs[i-1] and 
                recent_highs[i] > recent_highs[i+1] and
                recent_highs[i] > current_price):
                resistance_levels.append(recent_highs[i])
        
        # 2. 添加心理阻力位（整数价位）
        for i in range(int(current_price) + 1, int(current_price) + 6):
            if i > current_price:
                resistance_levels.append(float(i))
        
        # 3. 添加技术阻力位（移动平均线附近）
        if len(closes) >= 20:
            ma20 = sum(closes[-20:]) / 20
            if ma20 > current_price:
                resistance_levels.append(round(ma20, 2))
        
        # 4. 添加布林带上轨作为阻力位
        if len(closes) >= 20:
            prices = closes[-20:]
            middle = sum(prices) / 20
            variance = sum((p - middle) ** 2 for p in prices) / 20
            std = variance ** 0.5
            upper_band = middle + (2 * std)
            if upper_band > current_price:
                resistance_levels.append(round(upper_band, 2))
        
        # 去重并排序
        resistance_levels = list(set(resistance_levels))
        resistance_levels = [round(level, 2) for level in resistance_levels if level > current_price]
        resistance_levels.sort()
        
        return resistance_levels[:3]

class StockAnalysisService:
    """股票分析服务类"""
    
    def __init__(self):
        self.db = next(get_db())
    
    def get_stock_analysis(self, stock_code: str) -> Dict:
        """获取股票智能分析结果"""
        try:
            # 获取历史数据
            historical_data = self._get_historical_data(stock_code)
            if not historical_data:
                return {"error": "无法获取历史数据"}
            
            # 获取当前价格
            current_price = self._get_current_price(stock_code)
            if not current_price:
                current_price = float(historical_data[-1]['close'])
            
            # 计算技术指标
            technical_indicators = self._calculate_technical_indicators(historical_data)
            
            # 价格预测
            price_prediction = PricePrediction.predict_price(historical_data)
            
            # 交易建议
            trading_recommendation = TradingRecommendation.generate_recommendation(historical_data, current_price)
            
            # 关键价位
            key_levels = KeyLevels.calculate_key_levels(historical_data, current_price)
            
            return {
                "success": True,
                "data": {
                    "technical_indicators": technical_indicators,
                    "price_prediction": price_prediction,
                    "trading_recommendation": trading_recommendation,
                    "key_levels": key_levels,
                    "current_price": current_price,
                    "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
            return {"error": f"分析失败: {str(e)}"}
    
    def _get_historical_data(self, stock_code: str, days: int = 60) -> List[Dict]:
        """获取历史数据"""
        try:
            # 查询最近60天的历史数据
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
                data.append({
                    "code": row[0],
                    "name": row[1],
                    "date": row[2].strftime("%Y-%m-%d") if hasattr(row[2], 'strftime') else str(row[2]),
                    "open": float(row[3]) if row[3] else 0.0,
                    "high": float(row[4]) if row[4] else 0.0,
                    "low": float(row[5]) if row[5] else 0.0,
                    "close": float(row[6]) if row[6] else 0.0,
                    "volume": float(row[7]) if row[7] else 0.0,
                    "amount": float(row[8]) if row[8] else 0.0,
                    "change_percent": float(row[9]) if row[9] else 0.0,
                    "change": float(row[10]) if row[10] else 0.0,
                    "turnover_rate": float(row[11]) if row[11] else 0.0
                })
            
            # 按日期正序排列
            return list(reversed(data))
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {str(e)}")
            return []
    
    def _get_current_price(self, stock_code: str) -> Optional[float]:
        """获取当前价格"""
        try:
            stock = self.db.query(StockRealtimeQuote).filter(StockRealtimeQuote.code == stock_code).first()
            if stock:
                return float(stock.latest_price) if stock.latest_price else None
            return None
        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return None
    
    def _calculate_technical_indicators(self, historical_data: List[Dict]) -> Dict:
        """计算技术指标"""
        if len(historical_data) < 20:
            return {}
        
        # 提取数据
        closes = [data['close'] for data in historical_data]
        highs = [data['high'] for data in historical_data]
        lows = [data['low'] for data in historical_data]
        
        # 计算各项指标
        rsi = TechnicalIndicators.calculate_rsi(closes)
        macd = TechnicalIndicators.calculate_macd(closes)
        kdj = TechnicalIndicators.calculate_kdj(highs, lows, closes)
        bb = TechnicalIndicators.calculate_bollinger_bands(closes)
        
        # 判断信号
        rsi_signal = "超卖" if rsi < 30 else "超买" if rsi > 70 else "中性"
        macd_signal = "看多" if macd["macd"] > 0 and macd["histogram"] > 0 else "看空" if macd["macd"] < 0 and macd["histogram"] < 0 else "中性"
        kdj_signal = "超卖" if kdj["j"] < 20 else "超买" if kdj["j"] > 80 else "中性"
        bb_signal = "看多" if historical_data[-1]['close'] < bb["lower"] else "看空" if historical_data[-1]['close'] > bb["upper"] else "中性"
        
        return {
            "rsi": {
                "value": rsi,
                "signal": rsi_signal
            },
            "macd": {
                "value": macd["macd"],
                "signal": macd_signal
            },
            "kdj": {
                "value": kdj["j"],
                "signal": kdj_signal
            },
            "bollinger_bands": {
                "upper": bb["upper"],
                "middle": bb["middle"],
                "lower": bb["lower"],
                "signal": bb_signal
            }
        } 