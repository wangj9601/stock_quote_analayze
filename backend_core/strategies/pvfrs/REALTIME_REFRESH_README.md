# PVFRS策略实时数据刷新机制

## 概述

实时数据刷新机制是PVFRS策略系统的重要组成部分，负责确保选股结果能够及时响应数据变化，为前端用户提供最新的股票分析信息。

## 功能特性

### 核心功能

1. **定时刷新机制**
   - 可配置的刷新间隔（默认5分钟）
   - 支持交易时间限制
   - 自动循环执行

2. **数据变化监听**
   - 支持外部数据变化通知
   - 防抖机制避免频繁刷新
   - 批量处理多个股票变化

3. **手动刷新触发**
   - 支持即时手动刷新
   - 可指定特定股票刷新
   - 立即执行无延迟

4. **事件订阅系统**
   - 支持事件监听和回调
   - 完整的事件生命周期管理
   - 多订阅者支持

5. **服务生命周期管理**
   - 启动、停止、暂停、恢复
   - 优雅的资源清理
   - 错误恢复机制

### 高级特性

1. **性能监控**
   - 刷新次数统计
   - 成功/失败率跟踪
   - 平均耗时计算
   - 错误信息记录

2. **并发控制**
   - 可配置的最大并发数
   - 线程池管理
   - 防止资源过度消耗

3. **智能缓存**
   - 结果变化检测
   - 避免无效刷新
   - 内存使用优化

4. **配置管理**
   - 运行时配置更新
   - 参数验证
   - 默认值支持

## 架构设计

### 核心组件

```
RealtimeRefreshManager
├── 配置管理 (RefreshConfig)
├── 状态管理 (RefreshStatus)
├── 指标统计 (RefreshMetrics)
├── 事件系统 (RefreshEvent)
├── 线程管理 (ThreadPoolExecutor)
└── 前端接口集成 (FrontendInterface)
```

### 数据流

```
数据变化通知 → 防抖处理 → 刷新执行 → 结果检查 → 事件发送 → 订阅者通知
     ↑              ↓
定时触发 ←→ 手动触发 → 统计更新 → 缓存更新 → 状态更新
```

## 使用方法

### 基本使用

```python
from backend_core.strategies.pvfrs.realtime_refresh import (
    RealtimeRefreshManager,
    RefreshConfig,
    create_realtime_refresh_manager
)
from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface

# 创建前端接口
frontend_interface = FrontendInterface()

# 创建刷新配置
config = RefreshConfig(
    enabled=True,
    scheduled_interval_seconds=300,  # 5分钟
    data_change_debounce_seconds=30,  # 30秒防抖
    market_hours_only=True
)

# 创建刷新管理器
refresh_manager = create_realtime_refresh_manager(frontend_interface, config)

# 启动服务
refresh_manager.start()

# 手动触发刷新
refresh_manager.trigger_manual_refresh(['000001', '000002'])

# 通知数据变化
refresh_manager.notify_data_change(['000001'], 'price_update')

# 停止服务
refresh_manager.stop()
```

### 事件订阅

```python
def event_handler(event):
    print(f"收到刷新事件: {event.trigger_type.value}")
    print(f"影响股票: {event.affected_symbols}")
    print(f"事件数据: {event.event_data}")

# 订阅事件
refresh_manager.subscribe_to_events(event_handler)

# 取消订阅
refresh_manager.unsubscribe_from_events(event_handler)
```

### 状态监控

```python
# 获取服务状态
status = refresh_manager.get_status()
print(f"服务状态: {status['service_status']}")
print(f"总刷新次数: {status['metrics']['total_refreshes']}")
print(f"成功率: {status['metrics']['successful_refreshes'] / status['metrics']['total_refreshes'] * 100:.1f}%")

# 获取最近事件
recent_events = refresh_manager.get_recent_events(10)
for event in recent_events:
    print(f"事件: {event['trigger_type']} - {event['timestamp']}")
```

### 配置管理

```python
# 更新配置
new_config = RefreshConfig(
    enabled=True,
    scheduled_interval_seconds=600,  # 改为10分钟
    data_change_debounce_seconds=60   # 改为1分钟防抖
)

refresh_manager.update_config(new_config)

# 暂停和恢复
refresh_manager.pause()   # 暂停定时刷新
refresh_manager.resume()  # 恢复定时刷新
```

## 配置选项

### RefreshConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | True | 是否启用实时刷新 |
| `scheduled_interval_seconds` | int | 300 | 定时刷新间隔（秒） |
| `data_change_debounce_seconds` | int | 30 | 数据变化防抖时间（秒） |
| `max_concurrent_refreshes` | int | 3 | 最大并发刷新数量 |
| `market_hours_only` | bool | True | 是否仅在交易时间刷新 |
| `market_start_hour` | int | 9 | 市场开始时间（小时） |
| `market_end_hour` | int | 15 | 市场结束时间（小时） |

### 刷新触发类型

- `SCHEDULED`: 定时刷新
- `DATA_CHANGE`: 数据变化触发
- `MANUAL`: 手动触发
- `MARKET_EVENT`: 市场事件触发

### 服务状态

- `IDLE`: 空闲状态
- `RUNNING`: 运行中
- `PAUSED`: 已暂停
- `ERROR`: 错误状态
- `STOPPED`: 已停止

## 性能考虑

### 优化建议

1. **合理设置刷新间隔**
   - 根据数据更新频率调整
   - 避免过于频繁的刷新
   - 考虑系统负载

2. **使用防抖机制**
   - 避免短时间内重复刷新
   - 批量处理数据变化
   - 减少不必要的计算

3. **监控性能指标**
   - 定期检查刷新耗时
   - 关注成功率变化
   - 及时处理错误

4. **资源管理**
   - 适当设置并发限制
   - 及时清理无用缓存
   - 正确关闭服务

### 内存使用

- 事件队列限制为100个事件
- 自动清理过期缓存
- 线程池自动管理

### 错误处理

- 自动重试机制
- 错误统计和记录
- 优雅降级处理

## 测试

### 单元测试

```bash
python -m pytest test/test_realtime_refresh_final.py -v
```

### 集成测试

```bash
python -m pytest test/test_realtime_refresh_integration.py -v
```

### 演示程序

```bash
python backend_core/strategies/pvfrs/demo_realtime_refresh.py
```

## 故障排除

### 常见问题

1. **刷新不工作**
   - 检查服务是否启动
   - 验证配置是否正确
   - 查看错误日志

2. **性能问题**
   - 检查刷新间隔设置
   - 监控并发数量
   - 优化前端接口性能

3. **内存泄漏**
   - 确保正确停止服务
   - 检查事件订阅清理
   - 监控缓存大小

### 调试技巧

1. **启用详细日志**
   ```python
   import logging
   logging.getLogger('backend_core.strategies.pvfrs.realtime_refresh').setLevel(logging.DEBUG)
   ```

2. **监控事件流**
   ```python
   def debug_handler(event):
       print(f"DEBUG: {event.trigger_type.value} - {event.event_data}")
   
   refresh_manager.subscribe_to_events(debug_handler)
   ```

3. **检查状态信息**
   ```python
   status = refresh_manager.get_status()
   print(json.dumps(status, indent=2, ensure_ascii=False))
   ```

## 扩展开发

### 自定义触发器

可以通过继承 `RealtimeRefreshManager` 来添加自定义触发逻辑：

```python
class CustomRefreshManager(RealtimeRefreshManager):
    def trigger_custom_refresh(self, custom_data):
        event = RefreshEvent(
            event_id=str(uuid.uuid4()),
            trigger_type=RefreshTriggerType.MARKET_EVENT,
            timestamp=datetime.now().isoformat(),
            affected_symbols=[],
            event_data={'custom_data': custom_data}
        )
        self._execute_refresh(event)
```

### 自定义事件处理

```python
class EventProcessor:
    def __init__(self, refresh_manager):
        self.refresh_manager = refresh_manager
        self.refresh_manager.subscribe_to_events(self.handle_event)
    
    def handle_event(self, event):
        if event.trigger_type == RefreshTriggerType.DATA_CHANGE:
            # 自定义数据变化处理逻辑
            self.process_data_change(event)
        elif event.trigger_type == RefreshTriggerType.MANUAL:
            # 自定义手动刷新处理逻辑
            self.process_manual_refresh(event)
```

## 版本历史

- **v1.0.0**: 初始版本，基本刷新功能
- **v1.1.0**: 添加事件订阅系统
- **v1.2.0**: 增加性能监控和配置管理
- **v1.3.0**: 优化并发控制和错误处理

## 相关文档

- [PVFRS策略系统总体设计](./design.md)
- [前端接口文档](./frontend_interface.py)
- [配置管理文档](./config.py)
- [测试指南](../../test/README.md)