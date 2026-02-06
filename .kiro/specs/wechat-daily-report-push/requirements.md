# 需求文档 - 每日报告推送

## 简介

每日报告推送功能允许系统每日自动向用户通过微信或邮件推送其关注股票的历史行情数据报告。该功能利用现有的微信服务和CSV报告生成器,为用户提供定时、自动化、多渠道的股票数据推送服务。

## 术语表

- **System**: 每日报告推送系统
- **User**: 使用系统的投资者用户
- **WeChatService**: 微信服务模块,负责微信消息发送(支持个人微信和企业微信)
- **EmailService**: 邮件服务模块,负责邮件发送
- **CSVReportGenerator**: CSV报告生成器,负责生成股票报告
- **PushScheduler**: 推送调度器,负责定时任务管理
- **PushRecord**: 推送记录,记录每次推送的状态和结果
- **UserPushConfig**: 用户推送配置,存储用户的推送偏好设置
- **Watchlist**: 自选股列表,用户关注的股票集合
- **HistoricalQuote**: 历史行情数据,包含A股和港股的历史价格数据
- **WeChatOpenID**: 微信用户的唯一标识符,用于个人微信推送
- **PushChannel**: 推送渠道,包括微信(个人/企业)和邮件

## 需求

### 需求 1: 用户推送渠道配置

**用户故事:** 作为用户,我希望能够配置我的推送接收方式,以便通过我偏好的渠道接收股票报告。

#### 验收标准

1. THE System SHALL 在User模型中添加wechat_openid字段用于存储微信用户唯一标识
2. THE System SHALL 在User模型中添加wechat_type字段用于标识微信类型(个人微信或企业微信)
3. THE System SHALL 在User模型中添加email字段用于存储用户邮箱地址
4. WHEN 用户提供有效的微信OpenID, THE System SHALL 保存该ID到用户记录中
5. WHEN 用户提供有效的邮箱地址, THE System SHALL 验证邮箱格式并保存到用户记录中
6. THE System SHALL 支持用户同时配置多个推送渠道(微信和邮件)
7. THE System SHALL 支持用户解绑推送渠道(将对应字段设置为空)

### 需求 2: 用户推送配置管理

**用户故事:** 作为用户,我希望能够配置推送偏好,以便按照我的需求接收报告。

#### 验收标准

1. THE System SHALL 为每个用户创建推送配置记录(UserPushConfig)
2. THE System SHALL 支持用户启用或禁用推送功能
3. THE System SHALL 允许用户配置推送时间(支持多个时间点,如09:30和15:30)
4. THE System SHALL 允许用户选择报告类型(汇总报告或详细报告)
5. THE System SHALL 允许用户选择推送渠道(微信、邮件或两者都选)
6. WHEN 用户未配置推送时间, THE System SHALL 使用默认时间(09:30和15:30)
7. WHEN 用户未配置推送渠道, THE System SHALL 使用所有已绑定的渠道
8. THE System SHALL 支持用户配置推送的股票范围(全部自选股或指定股票)

### 需求 3: CSV报告生成

**用户故事:** 作为用户,我希望系统能够生成我关注股票的历史行情报告,以便我分析股票表现。

#### 验收标准

1. WHEN 生成报告时, THE System SHALL 从Watchlist获取用户的自选股列表
2. WHEN 生成报告时, THE System SHALL 从historical_quotes和historical_quotes_hk表获取历史行情数据
3. THE System SHALL 使用CSVReportGenerator生成CSV格式的报告文件
4. WHERE 用户选择汇总报告, THE System SHALL 生成包含所有股票关键指标的汇总表
5. WHERE 用户选择详细报告, THE System SHALL 生成包含每只股票完整历史数据的详细表
6. THE System SHALL 在报告中包含股票代码、名称、日期、开盘价、收盘价、最高价、最低价、成交量等字段
7. WHEN 用户的自选股列表为空, THE System SHALL 生成空报告并记录警告信息

### 需求 4: 定时推送调度

**用户故事:** 作为系统管理员,我希望系统能够按照配置的时间自动执行推送任务,以便用户及时收到报告。

#### 验收标准

1. THE System SHALL 实现定时任务调度器(PushScheduler)
2. THE System SHALL 在配置的时间点自动触发推送任务
3. WHEN 推送时间到达, THE System SHALL 查询所有启用推送的用户配置
4. WHEN 推送时间到达, THE System SHALL 为每个启用推送的用户生成报告并发送
5. THE System SHALL 支持配置多个推送时间点(如09:30和15:30)
6. WHEN 系统重启, THE System SHALL 自动恢复定时任务调度
7. THE System SHALL 确保同一用户在同一时间点不会重复推送

### 需求 5: 多渠道消息推送

**用户故事:** 作为用户,我希望通过微信或邮件接收报告,以便我能够方便地查看股票数据。

#### 验收标准

1. THE System SHALL 根据用户配置的推送渠道选择相应的服务发送报告
2. WHERE 用户选择微信推送, THE System SHALL 使用WeChatService发送消息
3. WHERE 用户选择邮件推送, THE System SHALL 使用EmailService发送邮件
4. WHERE 用户选择多个渠道, THE System SHALL 向所有渠道发送报告
5. WHEN 通过微信发送报告时, THE System SHALL 先发送文本消息说明报告内容,然后发送CSV文件
6. WHEN 通过邮件发送报告时, THE System SHALL 在邮件正文中说明报告内容,并将CSV文件作为附件
7. WHEN 用户未绑定任何推送渠道, THE System SHALL 跳过该用户并记录警告
8. IF 某个渠道推送失败, THEN THE System SHALL 记录错误但继续尝试其他渠道
9. THE System SHALL 在消息中包含报告日期、股票数量、报告类型等信息
10. WHERE 使用个人微信, THE System SHALL 通过微信公众号或服务号发送消息
11. WHERE 使用企业微信, THE System SHALL 通过企业微信API发送消息
12. WHERE 使用邮件, THE System SHALL 支持HTML格式的邮件正文

### 需求 6: 推送记录管理

**用户故事:** 作为用户,我希望能够查看推送历史记录,以便了解报告推送情况。

#### 验收标准

1. THE System SHALL 为每次推送创建推送记录(PushRecord)
2. THE System SHALL 在推送记录中保存用户ID、推送时间、报告类型、推送状态、错误信息等字段
3. THE System SHALL 支持推送状态包括:待推送、推送中、推送成功、推送失败
4. WHEN 推送成功, THE System SHALL 更新推送记录状态为成功并记录完成时间
5. WHEN 推送失败, THE System SHALL 更新推送记录状态为失败并记录错误原因
6. THE System SHALL 支持用户查询自己的推送历史记录
7. THE System SHALL 支持按日期范围、推送状态筛选推送记录

### 需求 7: 推送重试机制

**用户故事:** 作为系统管理员,我希望系统能够自动重试失败的推送,以便提高推送成功率。

#### 验收标准

1. WHEN 推送失败, THE System SHALL 自动进行重试
2. THE System SHALL 支持配置最大重试次数(默认3次)
3. THE System SHALL 在每次重试之间等待递增的时间间隔(如1分钟、5分钟、15分钟)
4. WHEN 达到最大重试次数仍失败, THE System SHALL 标记推送为最终失败状态
5. THE System SHALL 在推送记录中记录重试次数和每次重试的结果
6. THE System SHALL 支持手动触发失败推送的重新发送

### 需求 8: 数据完整性和错误处理

**用户故事:** 作为系统管理员,我希望系统能够妥善处理各种异常情况,以便保证服务稳定性。

#### 验收标准

1. WHEN 数据库连接失败, THE System SHALL 记录错误并在恢复后继续执行
2. WHEN 历史行情数据缺失, THE System SHALL 在报告中标注数据缺失并继续生成其他股票的数据
3. WHEN CSV生成失败, THE System SHALL 记录错误并跳过该用户的推送
4. WHEN 微信服务不可用, THE System SHALL 将该渠道推送标记为失败并尝试其他渠道
5. WHEN 邮件服务不可用, THE System SHALL 将该渠道推送标记为失败并尝试其他渠道
6. THE System SHALL 确保推送任务执行过程中的异常不会影响其他用户的推送
7. THE System SHALL 记录所有错误和警告信息到日志系统
8. WHEN 邮箱地址格式无效, THE System SHALL 拒绝发送并记录错误

### 需求 9: 性能和并发处理

**用户故事:** 作为系统管理员,我希望系统能够高效处理大量用户的推送请求,以便支持业务扩展。

#### 验收标准

1. THE System SHALL 支持并发处理多个用户的推送任务
2. THE System SHALL 使用任务队列管理推送任务,避免系统过载
3. WHEN 推送用户数量超过阈值, THE System SHALL 分批处理推送任务
4. THE System SHALL 在推送过程中限制对数据库的并发查询数量
5. THE System SHALL 确保单个用户的报告生成时间不超过30秒
6. THE System SHALL 确保单次推送任务的总执行时间不超过10分钟

### 需求 10: 配置和管理接口

**用户故事:** 作为系统管理员,我希望能够管理推送系统的配置,以便灵活调整系统行为。

#### 验收标准

1. THE System SHALL 提供API接口用于查询和更新用户推送配置
2. THE System SHALL 提供API接口用于查询推送记录
3. THE System SHALL 提供API接口用于手动触发推送任务
4. THE System SHALL 提供API接口用于查询推送系统状态(如待推送用户数、最近推送时间等)
5. THE System SHALL 支持管理员查看所有用户的推送配置和记录
6. THE System SHALL 支持管理员暂停或恢复全局推送功能
