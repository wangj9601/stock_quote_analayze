"""
PVFRS策略交易记录管理器
负责计算每笔交易的准确盈亏和维护完整的交易历史记录
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict
import json
import os

from .models import Trade, MarketData, Signal, CalculationException, ValidationException


class PnLCalculator:
    """盈亏计算器
    
    计算每笔交易的准确盈亏，包括手续费、滑点等成本
    """
    
    def __init__(self, commission_rate: float = 0.0003, slippage_rate: float = 0.001):
        """初始化盈亏计算器
        
        Args:
            commission_rate: 手续费率
            slippage_rate: 滑点率
        """
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
    
    def calculate_trade_pnl(self, trade: Trade) -> Tuple[float, float, Dict]:
        """计算交易盈亏
        
        Args:
            trade: 交易记录
            
        Returns:
            Tuple[float, float, Dict]: (绝对盈亏, 百分比盈亏, 详细计算结果)
            
        Raises:
            ValidationException: 交易数据无效时抛出
            CalculationException: 计算异常时抛出
        """
        try:
            # 验证交易数据
            if not self._validate_trade_data(trade):
                raise ValidationException(f"交易数据无效: {trade}")
            
            # 如果交易未完成，返回浮动盈亏（需要当前价格）
            if trade.exit_price is None:
                raise ValidationException("交易未完成，无法计算最终盈亏")
            
            # 计算买入成本
            buy_amount = trade.quantity * trade.entry_price
            buy_commission = buy_amount * self.commission_rate
            buy_slippage = trade.quantity * trade.entry_price * self.slippage_rate
            total_buy_cost = buy_amount + buy_commission + buy_slippage
            
            # 计算卖出收入
            sell_amount = trade.quantity * trade.exit_price
            sell_commission = sell_amount * self.commission_rate
            sell_slippage = trade.quantity * trade.exit_price * self.slippage_rate
            net_sell_proceeds = sell_amount - sell_commission - sell_slippage
            
            # 计算盈亏
            absolute_pnl = net_sell_proceeds - total_buy_cost
            percentage_pnl = absolute_pnl / total_buy_cost if total_buy_cost > 0 else 0.0
            
            # 详细计算结果
            calculation_details = {
                'buy_amount': buy_amount,
                'buy_commission': buy_commission,
                'buy_slippage': buy_slippage,
                'total_buy_cost': total_buy_cost,
                'sell_amount': sell_amount,
                'sell_commission': sell_commission,
                'sell_slippage': sell_slippage,
                'net_sell_proceeds': net_sell_proceeds,
                'absolute_pnl': absolute_pnl,
                'percentage_pnl': percentage_pnl,
                'total_commission': buy_commission + sell_commission,
                'total_slippage': buy_slippage + sell_slippage,
                'holding_days': self._calculate_holding_days(trade.entry_date, trade.exit_date)
            }
            
            return absolute_pnl, percentage_pnl, calculation_details
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"计算交易盈亏失败: {str(e)}")
    
    def calculate_floating_pnl(self, trade: Trade, current_price: float) -> Tuple[float, float, Dict]:
        """计算浮动盈亏
        
        Args:
            trade: 交易记录
            current_price: 当前价格
            
        Returns:
            Tuple[float, float, Dict]: (绝对浮动盈亏, 百分比浮动盈亏, 详细计算结果)
        """
        try:
            # 验证输入
            if current_price <= 0:
                raise ValidationException("当前价格必须大于0")
            
            if not self._validate_trade_data(trade, check_exit=False):
                raise ValidationException(f"交易数据无效: {trade}")
            
            # 计算买入成本
            buy_amount = trade.quantity * trade.entry_price
            buy_commission = buy_amount * self.commission_rate
            buy_slippage = trade.quantity * trade.entry_price * self.slippage_rate
            total_buy_cost = buy_amount + buy_commission + buy_slippage
            
            # 计算当前市值（假设现在卖出）
            current_amount = trade.quantity * current_price
            estimated_sell_commission = current_amount * self.commission_rate
            estimated_sell_slippage = trade.quantity * current_price * self.slippage_rate
            estimated_net_proceeds = current_amount - estimated_sell_commission - estimated_sell_slippage
            
            # 计算浮动盈亏
            floating_pnl = estimated_net_proceeds - total_buy_cost
            floating_pnl_pct = floating_pnl / total_buy_cost if total_buy_cost > 0 else 0.0
            
            # 详细计算结果
            calculation_details = {
                'current_price': current_price,
                'total_buy_cost': total_buy_cost,
                'current_market_value': current_amount,
                'estimated_net_proceeds': estimated_net_proceeds,
                'floating_pnl': floating_pnl,
                'floating_pnl_percentage': floating_pnl_pct,
                'unrealized_commission': estimated_sell_commission,
                'unrealized_slippage': estimated_sell_slippage
            }
            
            return floating_pnl, floating_pnl_pct, calculation_details
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"计算浮动盈亏失败: {str(e)}")
    
    def calculate_portfolio_pnl(self, trades: List[Trade], 
                               current_prices: Optional[Dict[str, float]] = None) -> Dict:
        """计算投资组合盈亏
        
        Args:
            trades: 交易记录列表
            current_prices: 当前价格字典（用于计算浮动盈亏）
            
        Returns:
            Dict: 投资组合盈亏统计
        """
        try:
            # 分类交易
            completed_trades = [t for t in trades if t.exit_price is not None]
            open_trades = [t for t in trades if t.exit_price is None]
            
            # 计算已完成交易的盈亏
            total_realized_pnl = 0.0
            total_realized_pnl_pct = 0.0
            realized_details = []
            
            for trade in completed_trades:
                pnl, pnl_pct, details = self.calculate_trade_pnl(trade)
                total_realized_pnl += pnl
                realized_details.append({
                    'symbol': trade.symbol,
                    'pnl': pnl,
                    'pnl_percentage': pnl_pct,
                    'details': details
                })
            
            # 计算平均已实现盈亏百分比
            if completed_trades:
                total_realized_pnl_pct = sum([d['pnl_percentage'] for d in realized_details]) / len(realized_details)
            
            # 计算未完成交易的浮动盈亏
            total_floating_pnl = 0.0
            total_floating_pnl_pct = 0.0
            floating_details = []
            
            if current_prices:
                for trade in open_trades:
                    if trade.symbol in current_prices:
                        current_price = current_prices[trade.symbol]
                        floating_pnl, floating_pnl_pct, details = self.calculate_floating_pnl(trade, current_price)
                        total_floating_pnl += floating_pnl
                        floating_details.append({
                            'symbol': trade.symbol,
                            'floating_pnl': floating_pnl,
                            'floating_pnl_percentage': floating_pnl_pct,
                            'details': details
                        })
                
                # 计算平均浮动盈亏百分比
                if floating_details:
                    total_floating_pnl_pct = sum([d['floating_pnl_percentage'] for d in floating_details]) / len(floating_details)
            
            # 总盈亏
            total_pnl = total_realized_pnl + total_floating_pnl
            
            return {
                'total_pnl': total_pnl,
                'realized_pnl': total_realized_pnl,
                'floating_pnl': total_floating_pnl,
                'realized_pnl_percentage': total_realized_pnl_pct,
                'floating_pnl_percentage': total_floating_pnl_pct,
                'completed_trades_count': len(completed_trades),
                'open_trades_count': len(open_trades),
                'realized_details': realized_details,
                'floating_details': floating_details,
                'summary': {
                    'winning_trades': len([d for d in realized_details if d['pnl'] > 0]),
                    'losing_trades': len([d for d in realized_details if d['pnl'] < 0]),
                    'win_rate': len([d for d in realized_details if d['pnl'] > 0]) / len(realized_details) if realized_details else 0.0,
                    'avg_win': sum([d['pnl'] for d in realized_details if d['pnl'] > 0]) / len([d for d in realized_details if d['pnl'] > 0]) if [d for d in realized_details if d['pnl'] > 0] else 0.0,
                    'avg_loss': sum([d['pnl'] for d in realized_details if d['pnl'] < 0]) / len([d for d in realized_details if d['pnl'] < 0]) if [d for d in realized_details if d['pnl'] < 0] else 0.0
                }
            }
            
        except Exception as e:
            raise CalculationException(f"计算投资组合盈亏失败: {str(e)}")
    
    def _validate_trade_data(self, trade: Trade, check_exit: bool = True) -> bool:
        """验证交易数据
        
        Args:
            trade: 交易记录
            check_exit: 是否检查退出数据
            
        Returns:
            bool: 数据是否有效
        """
        if not trade.symbol or not trade.entry_date:
            return False
        
        if trade.entry_price <= 0 or trade.quantity <= 0:
            return False
        
        if check_exit and trade.exit_price is not None and trade.exit_price <= 0:
            return False
        
        return True
    
    def _calculate_holding_days(self, entry_date: str, exit_date: Optional[str]) -> Optional[int]:
        """计算持有天数
        
        Args:
            entry_date: 入场日期
            exit_date: 出场日期
            
        Returns:
            Optional[int]: 持有天数
        """
        if not exit_date:
            return None
        
        try:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
            return (exit_dt - entry_dt).days
        except ValueError:
            return None


class TradeRecorder:
    """交易记录管理器
    
    维护完整的交易历史记录，提供交易查询和统计功能
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """初始化交易记录管理器
        
        Args:
            storage_path: 存储路径（可选）
        """
        self.storage_path = storage_path or "trade_records.json"
        self.pnl_calculator = PnLCalculator()
        
        # 内存中的交易记录
        self.trades: List[Trade] = []
        self.trade_index: Dict[str, List[int]] = {}  # 按股票代码索引
        
        # 加载历史记录
        self._load_records()
    
    def add_trade(self, trade: Trade) -> None:
        """添加交易记录
        
        Args:
            trade: 交易记录
            
        Raises:
            ValidationException: 交易数据无效时抛出
        """
        try:
            # 验证交易数据
            if not self._validate_trade(trade):
                raise ValidationException(f"交易数据无效: {trade}")
            
            # 如果是完成的交易，计算盈亏
            if trade.exit_price is not None:
                pnl, pnl_pct, _ = self.pnl_calculator.calculate_trade_pnl(trade)
                trade.pnl = pnl
                trade.pnl_percent = pnl_pct
            
            # 添加到记录
            trade_index = len(self.trades)
            self.trades.append(trade)
            
            # 更新索引
            if trade.symbol not in self.trade_index:
                self.trade_index[trade.symbol] = []
            self.trade_index[trade.symbol].append(trade_index)
            
            # 保存到文件
            self._save_records()
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"添加交易记录失败: {str(e)}")
    
    def update_trade(self, trade_index: int, updated_trade: Trade) -> None:
        """更新交易记录
        
        Args:
            trade_index: 交易索引
            updated_trade: 更新后的交易记录
            
        Raises:
            ValidationException: 交易数据无效时抛出
        """
        try:
            if trade_index < 0 or trade_index >= len(self.trades):
                raise ValidationException(f"交易索引无效: {trade_index}")
            
            # 验证更新的交易数据
            if not self._validate_trade(updated_trade):
                raise ValidationException(f"更新的交易数据无效: {updated_trade}")
            
            # 如果是完成的交易，重新计算盈亏
            if updated_trade.exit_price is not None:
                pnl, pnl_pct, _ = self.pnl_calculator.calculate_trade_pnl(updated_trade)
                updated_trade.pnl = pnl
                updated_trade.pnl_percent = pnl_pct
            
            # 更新记录
            old_symbol = self.trades[trade_index].symbol
            self.trades[trade_index] = updated_trade
            
            # 如果股票代码改变，更新索引
            if old_symbol != updated_trade.symbol:
                # 从旧索引中移除
                if old_symbol in self.trade_index:
                    self.trade_index[old_symbol].remove(trade_index)
                    if not self.trade_index[old_symbol]:
                        del self.trade_index[old_symbol]
                
                # 添加到新索引
                if updated_trade.symbol not in self.trade_index:
                    self.trade_index[updated_trade.symbol] = []
                self.trade_index[updated_trade.symbol].append(trade_index)
            
            # 保存到文件
            self._save_records()
            
        except (ValidationException, CalculationException):
            raise
        except Exception as e:
            raise CalculationException(f"更新交易记录失败: {str(e)}")
    
    def get_trades_by_symbol(self, symbol: str) -> List[Trade]:
        """获取指定股票的交易记录
        
        Args:
            symbol: 股票代码
            
        Returns:
            List[Trade]: 交易记录列表
        """
        if symbol not in self.trade_index:
            return []
        
        return [self.trades[i] for i in self.trade_index[symbol]]
    
    def get_trades_by_date_range(self, start_date: str, end_date: str) -> List[Trade]:
        """获取指定日期范围的交易记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[Trade]: 交易记录列表
        """
        filtered_trades = []
        
        for trade in self.trades:
            if start_date <= trade.entry_date <= end_date:
                filtered_trades.append(trade)
        
        return filtered_trades
    
    def get_open_positions(self) -> List[Trade]:
        """获取当前持仓
        
        Returns:
            List[Trade]: 未完成的交易记录列表
        """
        return [trade for trade in self.trades if trade.exit_price is None]
    
    def get_completed_trades(self) -> List[Trade]:
        """获取已完成的交易
        
        Returns:
            List[Trade]: 已完成的交易记录列表
        """
        return [trade for trade in self.trades if trade.exit_price is not None]
    
    def get_trade_statistics(self) -> Dict:
        """获取交易统计信息
        
        Returns:
            Dict: 交易统计信息
        """
        completed_trades = self.get_completed_trades()
        open_positions = self.get_open_positions()
        
        if not completed_trades:
            return {
                'total_trades': len(self.trades),
                'completed_trades': 0,
                'open_positions': len(open_positions),
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'avg_holding_days': 0.0
            }
        
        # 基础统计
        winning_trades = [t for t in completed_trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in completed_trades if t.pnl and t.pnl < 0]
        
        total_pnl = sum([t.pnl for t in completed_trades if t.pnl is not None])
        avg_pnl = total_pnl / len(completed_trades)
        
        # 计算平均持有期
        holding_days = []
        for trade in completed_trades:
            days = self.pnl_calculator._calculate_holding_days(trade.entry_date, trade.exit_date)
            if days is not None:
                holding_days.append(days)
        
        avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0.0
        
        return {
            'total_trades': len(self.trades),
            'completed_trades': len(completed_trades),
            'open_positions': len(open_positions),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(completed_trades),
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': sum([t.pnl for t in winning_trades]) / len(winning_trades) if winning_trades else 0.0,
            'avg_loss': sum([t.pnl for t in losing_trades]) / len(losing_trades) if losing_trades else 0.0,
            'largest_win': max([t.pnl for t in winning_trades], default=0.0),
            'largest_loss': min([t.pnl for t in losing_trades], default=0.0),
            'avg_holding_days': avg_holding_days,
            'symbols_traded': len(set([t.symbol for t in self.trades]))
        }
    
    def export_trades_to_dict(self) -> List[Dict]:
        """导出交易记录为字典列表
        
        Returns:
            List[Dict]: 交易记录字典列表
        """
        return [asdict(trade) for trade in self.trades]
    
    def import_trades_from_dict(self, trades_data: List[Dict]) -> None:
        """从字典列表导入交易记录
        
        Args:
            trades_data: 交易记录字典列表
            
        Raises:
            ValidationException: 数据格式无效时抛出
        """
        try:
            # 清空现有记录
            self.trades.clear()
            self.trade_index.clear()
            
            # 导入新记录
            for trade_dict in trades_data:
                trade = Trade(**trade_dict)
                self.add_trade(trade)
            
        except Exception as e:
            raise ValidationException(f"导入交易记录失败: {str(e)}")
    
    def _validate_trade(self, trade: Trade) -> bool:
        """验证交易记录
        
        Args:
            trade: 交易记录
            
        Returns:
            bool: 是否有效
        """
        return self.pnl_calculator._validate_trade_data(trade, check_exit=False)
    
    def _save_records(self) -> None:
        """保存记录到文件
        
        Raises:
            CalculationException: 保存失败时抛出
        """
        try:
            if not self.storage_path:
                return  # 不保存到文件
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # 导出数据
            data = {
                'trades': self.export_trades_to_dict(),
                'metadata': {
                    'total_trades': len(self.trades),
                    'last_updated': datetime.now().isoformat(),
                    'version': '1.0'
                }
            }
            
            # 保存到文件
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise CalculationException(f"保存交易记录失败: {str(e)}")
    
    def _load_records(self) -> None:
        """从文件加载记录
        
        Raises:
            CalculationException: 加载失败时抛出
        """
        try:
            if not self.storage_path or not os.path.exists(self.storage_path):
                return  # 文件不存在，跳过加载
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 导入交易记录
            if 'trades' in data:
                self.import_trades_from_dict(data['trades'])
                
        except Exception as e:
            # 加载失败不应该阻止程序运行，只记录错误
            print(f"加载交易记录失败: {str(e)}")
    
    def clear_all_records(self) -> None:
        """清空所有记录
        """
        self.trades.clear()
        self.trade_index.clear()
        
        # 删除文件
        if self.storage_path and os.path.exists(self.storage_path):
            try:
                os.remove(self.storage_path)
            except Exception:
                pass  # 忽略删除失败
    
    def get_recorder_status(self) -> Dict:
        """获取记录器状态
        
        Returns:
            Dict: 记录器状态信息
        """
        return {
            'total_trades': len(self.trades),
            'open_positions': len(self.get_open_positions()),
            'completed_trades': len(self.get_completed_trades()),
            'symbols_count': len(self.trade_index),
            'storage_path': self.storage_path,
            'has_storage_file': self.storage_path and os.path.exists(self.storage_path)
        }