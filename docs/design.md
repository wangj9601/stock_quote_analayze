# 股票分析系统设计文档

## 1. 项目概述

### 1.1 项目简介
股票分析系统是一个基于Web的股票数据分析和投资决策辅助平台，为个人投资者提供实时行情、历史数据、技术分析、智能预测等功能。系统采用前后端分离架构，支持多数据源集成，提供专业级的股票分析工具。

### 1.2 系统定位
- **目标用户**: 个人投资者、股票分析师
- **应用场景**: 股票市场分析、投资决策辅助、技术指标计算
- **核心价值**: 提供专业、准确、实时的股票数据分析服务

### 1.3 技术特点
- 前后端分离架构
- 多数据源集成（akshare、tushare）
- 实时数据采集和更新
- 智能分析算法
- 响应式Web界面
- PostgreSQL数据库支持

## 2. 系统架构

### 2.1 整体架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端层        │    │   后端API层     │    │   数据采集层    │
│                 │    │                 │    │                 │
│ • HTML/CSS/JS   │◄──►│ • FastAPI       │◄──►│ • akshare       │
│ • ECharts       │    │ • SQLAlchemy    │    │ • tushare       │
│ • 响应式设计    │    │ • JWT认证       │    │ • 定时任务      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   数据存储层    │
                       │                 │
                       │ • PostgreSQL    │
                       │ • Redis缓存     │
                       │ • 文件存储      │
                       └─────────────────┘
```

### 2.2 技术栈
- **前端**: HTML5 + CSS3 + JavaScript + ECharts
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **数据源**: akshare + tushare
- **部署**: Docker + Nginx
- **监控**: 日志系统 + 性能监控

## 3. 功能模块设计

### 3.1 用户管理模块
#### 3.1.1 功能描述
- 用户注册、登录、注销
- 用户信息管理
- 权限控制
- 会话管理

#### 3.1.2 数据模型
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password_hash = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime)
```

#### 3.1.3 API接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户注销
- `GET /api/auth/status` - 获取用户状态

### 3.2 行情数据模块
#### 3.2.1 功能描述
- 实时行情数据展示
- 历史行情数据查询
- 分时图、K线图展示
- 数据导出功能

#### 3.2.2 数据模型
```python
class StockRealtimeQuote(Base):
    __tablename__ = "stock_realtime_quote"
    code = Column(String, primary_key=True)
    name = Column(String)
    current_price = Column(Float)
    change_percent = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pre_close = Column(Float)
    update_time = Column(DateTime)

class HistoricalQuotes(Base):
    __tablename__ = 'historical_quotes'
    code = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    change_percent = Column(Float)
```

#### 3.2.3 API接口
- `GET /api/stock/realtime_quote_by_code` - 获取实时行情
- `GET /api/stock/kline_hist` - 获取K线历史数据
- `GET /api/stock/minute_data_by_code` - 获取分时数据
- `GET /api/stock/history` - 获取历史行情数据
- `GET /api/stock/history/export` - 导出历史数据

### 3.3 自选股管理模块
#### 3.3.1 功能描述
- 添加/删除自选股
- 自选股分组管理
- 自选股实时监控
- 价格提醒功能

#### 3.3.2 数据模型
```python
class Watchlist(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stock_code = Column(String)
    stock_name = Column(String)
    group_name = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.now)

class WatchlistGroup(Base):
    __tablename__ = "watchlist_groups"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    group_name = Column(String)
    created_at = Column(DateTime, default=datetime.now)
```

#### 3.3.3 API接口
- `GET /api/watchlist` - 获取自选股列表
- `POST /api/watchlist` - 添加自选股
- `DELETE /api/watchlist/delete_by_code` - 删除自选股
- `GET /api/watchlist/groups` - 获取分组列表
- `POST /api/watchlist/groups` - 创建分组

### 3.4 智能分析模块
#### 3.4.1 功能描述
- 技术指标计算（RSI、MACD、KDJ、布林带）
- 价格预测算法
- 交易建议生成
- 关键价位分析

#### 3.4.2 核心算法
```python
class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """计算RSI指标"""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

class PricePrediction:
    @staticmethod
    def predict_price(historical_data: List[Dict], days: int = 30) -> Dict:
        """基于线性回归的价格预测"""
        closes = [data['close'] for data in historical_data]
        x = np.arange(len(closes))
        y = np.array(closes)
        slope, intercept = np.polyfit(x, y, 1)
        target_price = slope * (len(closes) + days) + intercept
        return {"target_price": target_price, "confidence": 75.0}
```

#### 3.4.3 API接口
- `GET /analysis/stock/{stock_code}` - 获取完整分析
- `GET /analysis/technical/{stock_code}` - 获取技术指标
- `GET /analysis/prediction/{stock_code}` - 获取价格预测
- `GET /analysis/recommendation/{stock_code}` - 获取交易建议

### 3.5 数据采集模块
#### 3.5.1 功能描述
- 实时数据采集
- 历史数据采集
- 定时任务调度
- 数据质量监控

#### 3.5.2 采集策略
```python
class DataCollector:
    def collect_realtime_data(self):
        """实时数据采集"""
        # 使用akshare获取实时行情
        stock_data = ak.stock_zh_a_spot_em()
        # 数据清洗和存储
        self.save_to_database(stock_data)
    
    def collect_historical_data(self, stock_code: str):
        """历史数据采集"""
        # 获取历史K线数据
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily")
        # 数据转换和存储
        self.save_historical_data(hist_data)
```

#### 3.5.3 定时任务
- 实时数据：每5分钟采集一次
- 历史数据：每日采集一次
- 新闻公告：每日采集一次
- 财务数据：每季度采集一次

### 3.6 管理后台模块
#### 3.6.1 功能描述
- 用户管理
- 数据管理
- 系统监控
- 日志查看

#### 3.6.2 管理功能
- 用户账户管理
- 数据采集配置
- 系统性能监控
- 操作日志审计

## 4. 数据库设计

### 4.1 数据库架构
- **主数据库**: PostgreSQL
- **缓存数据库**: Redis
- **文件存储**: 本地文件系统

### 4.2 核心表结构
```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 实时行情表
CREATE TABLE stock_realtime_quote (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    current_price DECIMAL(10,2),
    change_percent DECIMAL(8,2),
    volume BIGINT,
    amount DECIMAL(15,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    open DECIMAL(10,2),
    pre_close DECIMAL(10,2),
    update_time TIMESTAMP
);

-- 历史行情表
CREATE TABLE historical_quotes (
    code VARCHAR(20),
    date DATE,
    open DECIMAL(10,2),
    close DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    volume BIGINT,
    amount DECIMAL(15,2),
    change_percent DECIMAL(8,2),
    PRIMARY KEY (code, date)
);
```

### 4.3 索引设计
```sql
-- 用户表索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- 行情表索引
CREATE INDEX idx_realtime_code ON stock_realtime_quote(code);
CREATE INDEX idx_realtime_update_time ON stock_realtime_quote(update_time);

-- 历史表索引
CREATE INDEX idx_historical_code_date ON historical_quotes(code, date);
CREATE INDEX idx_historical_date ON historical_quotes(date);
```

## 5. API设计

### 5.1 RESTful API规范
- 使用HTTP动词（GET、POST、PUT、DELETE）
- 统一的响应格式
- 标准的状态码
- 版本控制

### 5.2 响应格式
```json
{
    "success": true,
    "data": {
        // 具体数据
    },
    "message": "操作成功",
    "timestamp": "2025-01-20T10:30:00Z"
}
```

### 5.3 错误处理
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "details": {
            "field": "stock_code",
            "issue": "股票代码不能为空"
        }
    },
    "timestamp": "2025-01-20T10:30:00Z"
}
```

### 5.4 认证机制
- JWT Token认证
- Token过期时间：24小时
- 刷新Token机制
- 权限分级控制

## 6. 前端设计

### 6.1 页面结构
```
frontend/
├── index.html          # 首页
├── login.html          # 登录页
├── stock.html          # 股票详情页
├── watchlist.html      # 自选股页
├── markets.html        # 行情页
├── news.html           # 新闻页
├── profile.html        # 个人中心
├── css/                # 样式文件
├── js/                 # JavaScript文件
└── components/         # 组件文件
```

### 6.2 组件设计
- **Header组件**: 导航栏、搜索框、用户信息
- **Chart组件**: ECharts图表封装
- **Table组件**: 数据表格组件
- **Modal组件**: 弹窗组件
- **Loading组件**: 加载状态组件

### 6.3 响应式设计
- 移动端适配
- 平板端适配
- 桌面端优化
- 触摸操作支持

## 7. 部署架构

### 7.1 部署环境
- **操作系统**: Linux (Ubuntu 20.04+)
- **Web服务器**: Nginx
- **应用服务器**: uvicorn
- **数据库**: PostgreSQL 13+
- **缓存**: Redis 6+

### 7.2 部署流程
```bash
# 1. 环境准备
sudo apt update
sudo apt install python3 python3-pip postgresql redis-server nginx

# 2. 应用部署
git clone <repository>
cd stock_quote_analyze
pip install -r requirements.txt

# 3. 数据库初始化
python migrate_db.py

# 4. 服务启动
python start_system.py
```

### 7.3 监控和日志
- 应用日志：`app.log`
- 访问日志：Nginx access.log
- 错误日志：Nginx error.log
- 性能监控：Prometheus + Grafana

## 8. 安全设计

### 8.1 数据安全
- 密码加密存储（bcrypt）
- 敏感数据传输加密（HTTPS）
- 数据库连接加密
- 文件上传安全检查

### 8.2 访问控制
- JWT Token认证
- 角色权限控制
- API访问频率限制
- IP白名单控制

### 8.3 数据保护
- 用户数据隐私保护
- 数据备份策略
- 数据恢复机制
- 审计日志记录

## 9. 性能优化

### 9.1 数据库优化
- 索引优化
- 查询优化
- 连接池配置
- 读写分离

### 9.2 缓存策略
- Redis缓存热点数据
- 浏览器缓存静态资源
- CDN加速
- 数据库查询缓存

### 9.3 前端优化
- 代码压缩
- 图片优化
- 懒加载
- 预加载

## 10. 扩展性设计

### 10.1 水平扩展
- 负载均衡
- 微服务架构
- 容器化部署
- 自动扩缩容

### 10.2 功能扩展
- 插件系统
- API版本控制
- 第三方集成
- 移动端支持

### 10.3 数据扩展
- 多数据源支持
- 实时数据流
- 大数据分析
- 机器学习集成

## 11. 测试策略

### 11.1 单元测试
- 后端API测试
- 数据模型测试
- 业务逻辑测试
- 工具函数测试

### 11.2 集成测试
- API接口测试
- 数据库集成测试
- 第三方服务测试
- 端到端测试

### 11.3 性能测试
- 负载测试
- 压力测试
- 并发测试
- 稳定性测试

## 12. 维护和支持

### 12.1 运维监控
- 系统监控
- 应用监控
- 数据库监控
- 网络监控

### 12.2 故障处理
- 故障检测
- 自动恢复
- 人工干预
- 故障报告

### 12.3 版本管理
- 代码版本控制
- 数据库版本管理
- 配置文件管理
- 部署版本控制

## 13. 项目计划

### 13.1 开发阶段
1. **需求分析** (1周)
2. **系统设计** (2周)
3. **数据库设计** (1周)
4. **后端开发** (4周)
5. **前端开发** (3周)
6. **集成测试** (2周)
7. **部署上线** (1周)

### 13.2 里程碑
- **M1**: 基础框架搭建
- **M2**: 核心功能完成
- **M3**: 智能分析功能
- **M4**: 系统集成测试
- **M5**: 生产环境部署

## 14. 风险评估

### 14.1 技术风险
- 数据源稳定性
- 第三方API限制
- 性能瓶颈
- 安全漏洞

### 14.2 业务风险
- 需求变更
- 用户接受度
- 市场竞争
- 法规变化

### 14.3 缓解措施
- 多数据源备份
- 性能监控预警
- 安全审计
- 用户反馈收集

---

**文档版本**: V1.0  
**最后更新**: 2025-01-20  
**维护人员**: 开发团队
