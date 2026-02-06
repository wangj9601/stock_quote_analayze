# 设计文档 - 每日报告推送

## 概述

每日报告推送系统是一个自动化的股票数据推送服务,支持通过微信(个人微信/企业微信)和邮件两种渠道向用户推送其关注股票的历史行情CSV报告。系统基于现有的企业微信服务(WeChatService)和CSV报告生成器(CSVReportGenerator),新增邮件服务、定时调度器、推送配置管理和推送记录追踪等功能。

### 设计目标

1. **多渠道支持**: 支持微信和邮件两种推送渠道,用户可自由选择
2. **灵活配置**: 用户可配置推送时间、报告类型、推送渠道等
3. **可靠性**: 支持推送失败重试,确保消息送达
4. **可追溯**: 完整记录推送历史,支持查询和重发
5. **高性能**: 支持并发处理大量用户的推送任务
6. **可扩展**: 架构清晰,易于添加新的推送渠道

## 架构设计

### 系统架构图

```mermaid
graph TB
    subgraph "定时调度层"
        Scheduler[PushScheduler<br/>定时调度器]
    end
    
    subgraph "业务逻辑层"
        PushService[PushService<br/>推送服务]
        ConfigService[ConfigService<br/>配置服务]
        ReportService[ReportService<br/>报告服务]
    end
    
    subgraph "推送渠道层"
        WeChatService[WeChatService<br/>微信服务]
        EmailService[EmailService<br/>邮件服务]
    end
    
    subgraph "数据访问层"
        UserRepo[UserRepository]
        ConfigRepo[ConfigRepository]
        RecordRepo[RecordRepository]
        WatchlistRepo[WatchlistRepository]
    end
    
    subgraph "数据库"
        DB[(PostgreSQL)]
    end
    
    subgraph "外部服务"
        WeChatAPI[微信API]
        SMTP[SMTP服务器]
    end
    
    Scheduler --> PushService
    PushService --> ConfigService
    PushService --> ReportService
    PushService --> WeChatService
    PushService --> EmailService
    
    ConfigService --> UserRepo
    ConfigService --> ConfigRepo
    PushService --> RecordRepo
    ReportService --> WatchlistRepo
    
    UserRepo --> DB
    ConfigRepo --> DB
    RecordRepo --> DB
    WatchlistRepo --> DB
    
    WeChatService --> WeChatAPI
    EmailService --> SMTP
```

### 核心组件

1. **PushScheduler**: 定时任务调度器,负责在配置的时间点触发推送任务
2. **PushService**: 推送服务核心,协调报告生成、渠道选择、消息发送
3. **ConfigService**: 配置管理服务,管理用户推送配置
4. **ReportService**: 报告生成服务,封装CSVReportGenerator
5. **WeChatService**: 微信推送服务(已存在)
6. **EmailService**: 邮件推送服务(新增)
7. **Repository层**: 数据访问层,封装数据库操作

## 组件和接口

### 1. 数据模型扩展

#### 1.1 User模型扩展

```python
class User(Base):
    __tablename__ = "users"
    
    # 现有字段
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    # 新增字段
    wechat_openid = Column(String(100), nullable=True, index=True)  # 微信OpenID
    wechat_type = Column(String(20), nullable=True)  # 'personal' 或 'enterprise'
    
    # 关系
    watchlists = relationship("Watchlist", back_populates="user")
    push_config = relationship("UserPushConfig", back_populates="user", uselist=False)
    push_records = relationship("PushRecord", back_populates="user")
```

#### 1.2 UserPushConfig模型

```python
class UserPushConfig(Base):
    """用户推送配置表"""
    __tablename__ = "user_push_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # 推送开关
    enabled = Column(Boolean, default=True, nullable=False)
    
    # 推送渠道配置 (JSON格式: ["wechat", "email"])
    channels = Column(JSON, default=["wechat"], nullable=False)
    
    # 推送时间配置 (JSON格式: ["09:30", "15:30"])
    push_times = Column(JSON, default=["09:30", "15:30"], nullable=False)
    
    # 报告类型: 'summary' 或 'detailed'
    report_type = Column(String(20), default="summary", nullable=False)
    
    # 股票范围配置 (JSON格式: null表示全部, 或["000001", "600000"])
    stock_codes = Column(JSON, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    user = relationship("User", back_populates="push_config")
```

#### 1.3 PushRecord模型

```python
class PushRecord(Base):
    """推送记录表"""
    __tablename__ = "push_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 推送信息
    push_date = Column(Date, nullable=False, index=True)
    push_time = Column(String(10), nullable=False)  # "09:30"
    report_type = Column(String(20), nullable=False)  # 'summary' 或 'detailed'
    
    # 推送渠道和状态 (JSON格式)
    # {"wechat": "success", "email": "failed"}
    channel_status = Column(JSON, nullable=False)
    
    # 整体状态: 'pending', 'processing', 'success', 'partial_success', 'failed'
    status = Column(String(20), default="pending", nullable=False, index=True)
    
    # 报告文件路径
    report_file_path = Column(String(500), nullable=True)
    
    # 错误信息 (JSON格式: {"wechat": "error msg", "email": null})
    error_messages = Column(JSON, nullable=True)
    
    # 重试信息
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    user = relationship("User", back_populates="push_records")
```

### 2. 邮件服务 (EmailService)

#### 2.1 接口定义

```python
class EmailService:
    """邮件推送服务"""
    
    def __init__(self, smtp_config: SMTPConfig):
        """
        初始化邮件服务
        
        Args:
            smtp_config: SMTP配置对象
        """
        pass
    
    def send_report_email(
        self, 
        to_email: str, 
        subject: str, 
        content: str, 
        attachment_path: str
    ) -> EmailSendResult:
        """
        发送报告邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件正文(HTML格式)
            attachment_path: CSV附件路径
            
        Returns:
            EmailSendResult: 发送结果
            
        Raises:
            EmailSendException: 发送失败时抛出
        """
        pass
    
    def validate_email(self, email: str) -> bool:
        """
        验证邮箱地址格式
        
        Args:
            email: 邮箱地址
            
        Returns:
            bool: 是否有效
        """
        pass
```

#### 2.2 配置模型

```python
class SMTPConfig:
    """SMTP配置"""
    host: str  # SMTP服务器地址
    port: int  # SMTP端口
    username: str  # 发件人账号
    password: str  # 发件人密码
    use_tls: bool  # 是否使用TLS
    from_email: str  # 发件人邮箱
    from_name: str  # 发件人名称
```

### 3. 推送服务 (PushService)

#### 3.1 接口定义

```python
class PushService:
    """推送服务核心"""
    
    def __init__(
        self,
        wechat_service: WeChatService,
        email_service: EmailService,
        report_service: ReportService,
        config_service: ConfigService,
        record_repository: RecordRepository
    ):
        """初始化推送服务"""
        pass
    
    def execute_scheduled_push(self, push_time: str) -> PushBatchResult:
        """
        执行定时推送任务
        
        Args:
            push_time: 推送时间点 (如 "09:30")
            
        Returns:
            PushBatchResult: 批量推送结果
        """
        pass
    
    def push_to_user(self, user_id: int, push_time: str) -> PushResult:
        """
        向单个用户推送报告
        
        Args:
            user_id: 用户ID
            push_time: 推送时间点
            
        Returns:
            PushResult: 推送结果
        """
        pass
    
    def retry_failed_push(self, record_id: int) -> PushResult:
        """
        重试失败的推送
        
        Args:
            record_id: 推送记录ID
            
        Returns:
            PushResult: 重试结果
        """
        pass
    
    def _send_via_wechat(
        self, 
        user: User, 
        report_path: str, 
        report_info: ReportInfo
    ) -> ChannelResult:
        """通过微信发送报告"""
        pass
    
    def _send_via_email(
        self, 
        user: User, 
        report_path: str, 
        report_info: ReportInfo
    ) -> ChannelResult:
        """通过邮件发送报告"""
        pass
```

### 4. 配置服务 (ConfigService)

```python
class ConfigService:
    """配置管理服务"""
    
    def get_user_config(self, user_id: int) -> UserPushConfig:
        """获取用户推送配置"""
        pass
    
    def update_user_config(
        self, 
        user_id: int, 
        config_update: ConfigUpdate
    ) -> UserPushConfig:
        """更新用户推送配置"""
        pass
    
    def get_users_for_push_time(self, push_time: str) -> List[User]:
        """获取指定时间点需要推送的用户列表"""
        pass
    
    def create_default_config(self, user_id: int) -> UserPushConfig:
        """为新用户创建默认配置"""
        pass
```

### 5. 报告服务 (ReportService)

```python
class ReportService:
    """报告生成服务"""
    
    def __init__(self, csv_generator: CSVReportGenerator):
        """初始化报告服务"""
        self.csv_generator = csv_generator
    
    def generate_user_report(
        self, 
        user_id: int, 
        report_type: str,
        stock_codes: Optional[List[str]] = None
    ) -> ReportResult:
        """
        生成用户报告
        
        Args:
            user_id: 用户ID
            report_type: 报告类型 ('summary' 或 'detailed')
            stock_codes: 指定股票代码列表,None表示全部自选股
            
        Returns:
            ReportResult: 报告生成结果
        """
        pass
    
    def get_report_info(self, report_path: str) -> ReportInfo:
        """获取报告信息(股票数量、日期等)"""
        pass
```

### 6. 定时调度器 (PushScheduler)

```python
class PushScheduler:
    """定时任务调度器"""
    
    def __init__(self, push_service: PushService):
        """初始化调度器"""
        self.push_service = push_service
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        """启动调度器"""
        pass
    
    def stop(self):
        """停止调度器"""
        pass
    
    def add_push_job(self, push_time: str):
        """
        添加推送任务
        
        Args:
            push_time: 推送时间 (如 "09:30")
        """
        pass
    
    def remove_push_job(self, push_time: str):
        """移除推送任务"""
        pass
    
    def get_scheduled_jobs(self) -> List[JobInfo]:
        """获取所有已调度的任务"""
        pass
```

## 数据模型

### ER图

```mermaid
erDiagram
    users ||--o| user_push_configs : has
    users ||--o{ push_records : has
    users ||--o{ watchlist : has
    
    users {
        int id PK
        string username
        string email
        string password_hash
        string wechat_openid
        string wechat_type
        datetime created_at
    }
    
    user_push_configs {
        int id PK
        int user_id FK
        boolean enabled
        json channels
        json push_times
        string report_type
        json stock_codes
        datetime created_at
        datetime updated_at
    }
    
    push_records {
        int id PK
        int user_id FK
        date push_date
        string push_time
        string report_type
        json channel_status
        string status
        string report_file_path
        json error_messages
        int retry_count
        datetime created_at
        datetime completed_at
    }
    
    watchlist {
        int id PK
        int user_id FK
        string stock_code
        string stock_name
        string group_name
        datetime created_at
    }
```

### 数据字典

#### user_push_configs表

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| channels | JSON | 推送渠道列表 | ["wechat", "email"] |
| push_times | JSON | 推送时间列表 | ["09:30", "15:30"] |
| report_type | String | 报告类型 | "summary" 或 "detailed" |
| stock_codes | JSON | 指定股票代码,null表示全部 | ["000001", "600000"] 或 null |

#### push_records表

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| channel_status | JSON | 各渠道推送状态 | {"wechat": "success", "email": "failed"} |
| status | String | 整体状态 | pending/processing/success/partial_success/failed |
| error_messages | JSON | 各渠道错误信息 | {"wechat": null, "email": "SMTP connection failed"} |

## 正确性属性

*属性是一个特征或行为,应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的正式陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

在编写正确性属性之前,我需要先进行验收标准的可测试性分析。


### 正确性属性

基于需求分析和prework,以下是系统的核心正确性属性:

**属性 1: 用户渠道绑定持久化**
*对于任何*有效的微信OpenID或邮箱地址,当用户绑定该渠道后,查询用户记录应该返回相同的绑定信息
**验证需求: 1.4, 1.5**

**属性 2: 多渠道配置支持**
*对于任何*渠道组合(微信、邮件或两者),用户配置后,系统应该正确保存并在推送时使用所有配置的渠道
**验证需求: 1.6, 2.5, 5.4**

**属性 3: 渠道解绑清除**
*对于任何*已绑定的渠道,当用户解绑后,对应的字段应该为空,且该渠道不应再用于推送
**验证需求: 1.7**

**属性 4: 用户配置自动创建**
*对于任何*新创建的用户,系统应该自动创建一个默认的推送配置记录
**验证需求: 2.1**

**属性 5: 配置更新持久化**
*对于任何*用户配置更新(启用/禁用、推送时间、报告类型、股票范围),更新后查询应该返回新的配置值
**验证需求: 2.2, 2.3, 2.4, 2.8, 4.5**

**属性 6: 报告包含自选股数据**
*对于任何*用户的自选股列表,生成的报告应该包含列表中所有股票的数据
**验证需求: 3.1, 3.2**

**属性 7: 报告类型决定内容格式**
*对于任何*用户,当选择汇总报告时,报告应包含关键指标汇总;当选择详细报告时,报告应包含完整历史数据
**验证需求: 3.4, 3.5**

**属性 8: 报告必需字段完整性**
*对于任何*生成的报告,应该包含股票代码、股票名称、交易日期、价格等必需字段
**验证需求: 3.6**

**属性 9: 推送时间触发正确用户**
*对于任何*推送时间点,系统应该查询并推送给所有在该时间点启用推送的用户,且不包含未启用的用户
**验证需求: 4.3, 4.4**

**属性 10: 推送去重**
*对于任何*用户和推送时间点,在同一天内多次触发推送时,用户应该只收到一次报告
**验证需求: 4.7**

**属性 11: 渠道选择正确性**
*对于任何*用户配置的推送渠道,系统应该调用对应的服务(WeChatService或EmailService),且不调用未配置的渠道服务
**验证需求: 5.1, 5.2, 5.3**

**属性 12: 微信推送消息顺序**
*对于任何*通过微信推送的报告,系统应该先发送文本说明消息,然后发送CSV文件,且文本消息包含报告日期、股票数量、报告类型
**验证需求: 5.5, 5.9**

**属性 13: 邮件推送结构完整性**
*对于任何*通过邮件推送的报告,邮件应该包含HTML格式的正文(含报告说明)和CSV附件
**验证需求: 5.6, 5.12**

**属性 14: 渠道失败隔离**
*对于任何*配置了多个渠道的用户,当其中一个渠道推送失败时,系统应该继续尝试其他渠道,且记录失败渠道的错误信息
**验证需求: 5.8, 8.4, 8.5**

**属性 15: 推送记录完整性**
*对于任何*推送操作,系统应该创建包含用户ID、推送时间、报告类型、各渠道状态、错误信息等完整字段的推送记录
**验证需求: 6.1, 6.2**

**属性 16: 推送状态更新正确性**
*对于任何*推送操作,当推送成功时,记录状态应为成功且包含完成时间;当推送失败时,记录状态应为失败且包含错误原因
**验证需求: 6.4, 6.5**

**属性 17: 推送记录查询和筛选**
*对于任何*用户的推送记录查询,应该只返回该用户的记录,且支持按日期范围和状态筛选
**验证需求: 6.6, 6.7**

**属性 18: 失败自动重试**
*对于任何*推送失败的记录,系统应该自动触发重试,直到成功或达到最大重试次数
**验证需求: 7.1, 7.2**

**属性 19: 重试次数限制**
*对于任何*推送失败的记录,当重试次数达到配置的最大值后,系统应该停止重试并标记为最终失败状态
**验证需求: 7.4**

**属性 20: 重试信息记录**
*对于任何*经过重试的推送,推送记录应该包含重试次数和每次重试的结果
**验证需求: 7.5**

**属性 21: 手动重发支持**
*对于任何*失败的推送记录,管理员或用户应该能够手动触发重新发送,且系统应该执行完整的推送流程
**验证需求: 7.6**

**属性 22: 数据缺失容错**
*对于任何*报告生成请求,当某些股票的历史数据缺失时,系统应该在报告中标注缺失,并继续生成其他股票的数据
**验证需求: 8.2**

**属性 23: 报告生成失败隔离**
*对于任何*批量推送任务,当某个用户的报告生成失败时,系统应该记录错误并跳过该用户,继续处理其他用户
**验证需求: 8.3, 8.6**

**属性 24: 错误日志记录**
*对于任何*错误或警告情况(无效邮箱、服务不可用、数据缺失等),系统应该记录详细的错误信息到日志系统
**验证需求: 8.7, 8.8**

**属性 25: 邮箱格式验证**
*对于任何*邮箱地址,系统应该验证其格式,拒绝发送到无效邮箱,并记录错误
**验证需求: 8.8**

**属性 26: API配置管理**
*对于任何*通过API进行的配置查询或更新操作,系统应该正确处理并返回更新后的配置
**验证需求: 10.1**

**属性 27: API推送记录查询**
*对于任何*通过API进行的推送记录查询,系统应该返回符合查询条件的记录列表
**验证需求: 10.2**

**属性 28: API手动推送触发**
*对于任何*通过API手动触发的推送请求,系统应该立即执行推送流程并返回执行结果
**验证需求: 10.3**

**属性 29: 管理员全局查看权限**
*对于任何*管理员用户,应该能够查看所有用户的推送配置和推送记录
**验证需求: 10.5**

**属性 30: 全局推送开关**
*对于任何*全局推送控制操作(暂停/恢复),系统应该立即生效,暂停时不执行任何推送,恢复后正常执行
**验证需求: 10.6**

## 错误处理

### 错误分类

1. **用户输入错误**
   - 无效的邮箱格式
   - 无效的微信OpenID
   - 无效的推送时间格式
   - 处理: 返回明确的错误信息,拒绝操作

2. **数据错误**
   - 用户没有自选股
   - 历史行情数据缺失
   - 处理: 生成空报告或部分报告,记录警告

3. **服务不可用错误**
   - 微信API不可用
   - SMTP服务器不可用
   - 数据库连接失败
   - 处理: 标记推送失败,触发重试机制

4. **系统错误**
   - CSV生成失败
   - 文件系统错误
   - 处理: 记录错误,跳过当前操作,继续处理其他任务

### 错误处理策略

```python
class ErrorHandler:
    """统一错误处理器"""
    
    def handle_push_error(
        self, 
        error: Exception, 
        context: PushContext
    ) -> ErrorHandlingResult:
        """
        处理推送错误
        
        策略:
        1. 记录详细错误信息到日志
        2. 更新推送记录状态
        3. 根据错误类型决定是否重试
        4. 通知相关人员(如果是严重错误)
        """
        pass
    
    def should_retry(self, error: Exception) -> bool:
        """判断错误是否应该重试"""
        # 网络错误、服务暂时不可用 -> 重试
        # 数据错误、配置错误 -> 不重试
        pass
```

### 重试策略

```python
class RetryStrategy:
    """重试策略"""
    
    def get_retry_delay(self, retry_count: int) -> int:
        """
        获取重试延迟时间(秒)
        
        指数退避策略:
        - 第1次重试: 1分钟
        - 第2次重试: 5分钟
        - 第3次重试: 15分钟
        """
        delays = [60, 300, 900]
        return delays[min(retry_count, len(delays) - 1)]
```

## 测试策略

### 测试方法

系统采用**双重测试方法**:

1. **单元测试**: 验证具体示例、边界情况和错误条件
2. **属性测试**: 验证跨所有输入的通用属性

两种测试方法是互补的,共同确保全面覆盖:
- 单元测试捕获具体的错误
- 属性测试验证通用的正确性

### 测试框架

- **单元测试框架**: pytest
- **属性测试框架**: Hypothesis (Python的属性测试库)
- **Mock框架**: unittest.mock
- **测试数据库**: PostgreSQL测试实例

### 属性测试配置

每个属性测试必须:
- 运行最少100次迭代(由于随机化)
- 使用注释标签引用设计文档中的属性
- 标签格式: `# Feature: wechat-daily-report-push, Property {number}: {property_text}`

### 测试覆盖范围

#### 单元测试重点

1. **配置管理**
   - 创建默认配置
   - 更新配置
   - 验证配置有效性

2. **报告生成**
   - 汇总报告格式
   - 详细报告格式
   - 空自选股处理
   - 数据缺失处理

3. **推送服务**
   - 单渠道推送
   - 多渠道推送
   - 推送失败处理
   - 重试机制

4. **API接口**
   - 配置CRUD操作
   - 推送记录查询
   - 手动触发推送
   - 权限验证

#### 属性测试重点

1. **配置持久化属性** (属性1, 2, 3, 4, 5)
   - 生成随机配置
   - 验证保存和查询的一致性

2. **报告生成属性** (属性6, 7, 8)
   - 生成随机自选股列表
   - 验证报告内容完整性

3. **推送执行属性** (属性9, 10, 11, 12, 13, 14)
   - 生成随机用户和配置
   - 验证推送行为正确性

4. **记录管理属性** (属性15, 16, 17)
   - 生成随机推送记录
   - 验证记录完整性和查询正确性

5. **重试机制属性** (属性18, 19, 20, 21)
   - 模拟随机失败场景
   - 验证重试行为

6. **错误处理属性** (属性22, 23, 24, 25)
   - 生成随机错误场景
   - 验证容错和日志记录

7. **API属性** (属性26, 27, 28, 29, 30)
   - 生成随机API请求
   - 验证响应正确性

### 测试示例

#### 单元测试示例

```python
def test_create_default_config():
    """测试创建默认配置"""
    user_id = 1
    config = config_service.create_default_config(user_id)
    
    assert config.user_id == user_id
    assert config.enabled == True
    assert config.channels == ["wechat"]
    assert config.push_times == ["09:30", "15:30"]
    assert config.report_type == "summary"
```

#### 属性测试示例

```python
from hypothesis import given, strategies as st

@given(
    wechat_openid=st.text(min_size=10, max_size=50),
    user_id=st.integers(min_value=1, max_value=10000)
)
def test_wechat_binding_persistence(wechat_openid, user_id):
    """
    Feature: wechat-daily-report-push, Property 1: 用户渠道绑定持久化
    
    对于任何有效的微信OpenID,绑定后查询应返回相同的信息
    """
    # 绑定微信
    user_service.bind_wechat(user_id, wechat_openid, "personal")
    
    # 查询用户
    user = user_service.get_user(user_id)
    
    # 验证
    assert user.wechat_openid == wechat_openid
    assert user.wechat_type == "personal"
```

### Mock策略

对于外部服务,使用Mock对象:

```python
@pytest.fixture
def mock_wechat_service():
    """Mock微信服务"""
    service = Mock(spec=WeChatService)
    service.send_text_message.return_value = True
    service.send_file_message.return_value = True
    return service

@pytest.fixture
def mock_email_service():
    """Mock邮件服务"""
    service = Mock(spec=EmailService)
    service.send_report_email.return_value = EmailSendResult(success=True)
    return service
```

### 集成测试

集成测试验证组件之间的交互:

1. **端到端推送流程**
   - 创建用户和配置
   - 触发推送
   - 验证报告生成
   - 验证消息发送
   - 验证记录创建

2. **定时任务集成**
   - 启动调度器
   - 等待触发时间
   - 验证推送执行

3. **API集成测试**
   - 测试完整的API调用链
   - 验证数据库状态变化

### 测试数据管理

```python
@pytest.fixture
def test_db():
    """测试数据库fixture"""
    # 创建测试数据库
    engine = create_engine("postgresql://test:test@localhost/test_db")
    Base.metadata.create_all(engine)
    
    yield engine
    
    # 清理测试数据
    Base.metadata.drop_all(engine)

@pytest.fixture
def sample_user(test_db):
    """创建示例用户"""
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash="hashed",
        wechat_openid="test_openid",
        wechat_type="personal"
    )
    test_db.add(user)
    test_db.commit()
    return user
```

## 实现注意事项

### 1. 并发控制

使用任务队列(如Celery)管理推送任务:

```python
from celery import Celery

app = Celery('push_tasks', broker='redis://localhost:6379/0')

@app.task
def push_to_user_task(user_id: int, push_time: str):
    """异步推送任务"""
    push_service.push_to_user(user_id, push_time)
```

### 2. 配置管理

使用环境变量和配置文件:

```python
class Config:
    # SMTP配置
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    
    # 推送配置
    MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "3"))
    PUSH_BATCH_SIZE = int(os.getenv("PUSH_BATCH_SIZE", "100"))
    
    # 微信配置
    WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID")
    WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID")
```

### 3. 日志记录

使用结构化日志:

```python
import logging
import json

logger = logging.getLogger(__name__)

def log_push_event(event_type: str, user_id: int, details: dict):
    """记录推送事件"""
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        **details
    }
    logger.info(json.dumps(log_data))
```

### 4. 监控和告警

关键指标监控:
- 推送成功率
- 推送延迟
- 重试次数
- 错误率

### 5. 数据库索引

确保关键字段有索引:
- `user_push_configs.user_id`
- `push_records.user_id`
- `push_records.push_date`
- `push_records.status`
- `users.wechat_openid`

### 6. 安全考虑

- 邮箱和微信OpenID的验证
- API接口的权限控制
- 敏感信息(SMTP密码)的加密存储
- 防止推送滥用(频率限制)
