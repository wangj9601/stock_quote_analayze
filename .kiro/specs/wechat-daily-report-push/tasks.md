# 实现计划: 每日报告推送

## 概述

本实现计划将每日报告推送功能分解为一系列增量式的编码任务。每个任务都基于前面的任务构建,最终形成一个完整的、可工作的推送系统。实现将使用Python语言,基于现有的PostgreSQL数据库、WeChatService和CSVReportGenerator。

## 任务列表

- [x] 1. 数据库模型扩展和迁移
  - 扩展User模型,添加wechat_openid和wechat_type字段
  - 创建UserPushConfig模型
  - 创建PushRecord模型
  - 编写数据库迁移脚本
  - 创建必要的索引
  - _需求: 1.1, 1.2, 2.1, 6.1_
  - _状态: 已完成 - backend_api/models.py中已实现所有模型,migrations/add_wechat_push_tables.py已创建_

- [ ]* 1.1 为数据模型编写属性测试
  - **属性 1: 用户渠道绑定持久化**
  - **属性 4: 用户配置自动创建**
  - **验证需求: 1.4, 1.5, 2.1**

- [x] 2. 实现邮件服务 (EmailService)
  - [x] 2.1 创建EmailService类和SMTPConfig配置类
    - 在backend_api/services/目录下创建email_service.py
    - 实现send_report_email方法
    - 实现validate_email方法
    - 支持HTML格式邮件正文
    - 支持CSV文件附件
    - 在backend_api/config.py中添加SMTP配置
    - _需求: 5.3, 5.6, 5.12_

  - [ ]* 2.2 为邮件服务编写属性测试
    - **属性 13: 邮件推送结构完整性**
    - **属性 25: 邮箱格式验证**
    - **验证需求: 5.6, 5.12, 8.8**

  - [ ]* 2.3 为邮件服务编写单元测试
    - 测试有效邮箱发送
    - 测试无效邮箱拒绝
    - 测试SMTP连接失败处理
    - 测试附件发送
    - _需求: 5.6, 8.8_

- [x] 3. 实现配置服务 (ConfigService)
  - [x] 3.1 创建ConfigService类
    - 在backend_api/services/目录下创建config_service.py
    - 实现get_user_config方法
    - 实现update_user_config方法
    - 实现create_default_config方法
    - 实现get_users_for_push_time方法
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.8, 4.3_

  - [ ]* 3.2 为配置服务编写属性测试
    - **属性 2: 多渠道配置支持**
    - **属性 3: 渠道解绑清除**
    - **属性 5: 配置更新持久化**
    - **验证需求: 1.6, 1.7, 2.2, 2.3, 2.4, 2.8**

  - [ ]* 3.3 为配置服务编写单元测试
    - 测试默认配置创建
    - 测试配置更新
    - 测试默认值应用
    - _需求: 2.1, 2.6, 2.7_

- [ ] 4. 实现报告服务 (ReportService)
  - [ ] 4.1 创建ReportService类
    - 在backend_api/services/目录下创建report_service.py
    - 封装现有的CSVReportGenerator (backend_core/reports/csv_report_generator.py)
    - 实现generate_user_report方法(支持指定股票范围)
    - 实现get_report_info方法
    - 处理空自选股情况
    - 处理数据缺失情况
    - 适配现有的数据库表结构(watchlist, historical_quotes, historical_quotes_hk)
    - _需求: 3.1, 3.2, 3.4, 3.5, 3.7, 8.2_

  - [ ]* 4.2 为报告服务编写属性测试
    - **属性 6: 报告包含自选股数据**
    - **属性 7: 报告类型决定内容格式**
    - **属性 8: 报告必需字段完整性**
    - **属性 22: 数据缺失容错**
    - **验证需求: 3.1, 3.2, 3.4, 3.5, 3.6, 8.2**

  - [ ]* 4.3 为报告服务编写单元测试
    - 测试汇总报告生成
    - 测试详细报告生成
    - 测试空自选股处理
    - 测试数据缺失处理
    - _需求: 3.4, 3.5, 3.7, 8.2_

- [ ] 5. 检查点 - 确保基础服务测试通过
  - 确保所有测试通过,如有问题请询问用户

- [ ] 6. 实现推送记录管理 (RecordRepository)
  - [ ] 6.1 创建RecordRepository类
    - 在backend_api/services/目录下创建record_repository.py
    - 实现create_record方法
    - 实现update_record_status方法
    - 实现get_user_records方法(支持筛选)
    - 实现get_record_by_id方法
    - _需求: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 6.2 为记录管理编写属性测试
    - **属性 15: 推送记录完整性**
    - **属性 16: 推送状态更新正确性**
    - **属性 17: 推送记录查询和筛选**
    - **验证需求: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7**

- [ ] 7. 实现推送服务核心 (PushService)
  - [ ] 7.1 创建PushService类基础结构
    - 在backend_api/services/目录下创建push_service.py
    - 注入WeChatService、EmailService、ReportService、ConfigService、RecordRepository
    - 实现_send_via_wechat私有方法(使用backend_core/wechat/wechat_service.py)
    - 实现_send_via_email私有方法
    - _需求: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [ ] 7.2 实现单用户推送逻辑 (push_to_user)
    - 获取用户配置
    - 生成报告
    - 根据配置选择推送渠道
    - 创建推送记录
    - 处理多渠道推送
    - 处理渠道失败隔离
    - 更新推送记录状态
    - _需求: 5.1, 5.4, 5.7, 5.8, 6.1, 6.4, 6.5_

  - [ ]* 7.3 为单用户推送编写属性测试
    - **属性 11: 渠道选择正确性**
    - **属性 12: 微信推送消息顺序**
    - **属性 13: 邮件推送结构完整性**
    - **属性 14: 渠道失败隔离**
    - **验证需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8**

  - [ ] 7.4 实现批量推送逻辑 (execute_scheduled_push)
    - 查询指定时间点需要推送的用户
    - 并发处理多个用户推送
    - 实现推送去重逻辑
    - 处理单个用户失败不影响其他用户
    - _需求: 4.3, 4.4, 4.7, 8.3, 8.6_

  - [ ]* 7.5 为批量推送编写属性测试
    - **属性 9: 推送时间触发正确用户**
    - **属性 10: 推送去重**
    - **属性 23: 报告生成失败隔离**
    - **验证需求: 4.3, 4.4, 4.7, 8.3, 8.6**

  - [ ] 7.6 实现重试机制 (retry_failed_push)
    - 实现重试逻辑
    - 实现指数退避策略
    - 更新重试次数和结果
    - 处理达到最大重试次数
    - _需求: 7.1, 7.2, 7.4, 7.5, 7.6_

  - [ ]* 7.7 为重试机制编写属性测试
    - **属性 18: 失败自动重试**
    - **属性 19: 重试次数限制**
    - **属性 20: 重试信息记录**
    - **属性 21: 手动重发支持**
    - **验证需求: 7.1, 7.2, 7.4, 7.5, 7.6**

- [ ] 8. 检查点 - 确保推送服务测试通过
  - 确保所有测试通过,如有问题请询问用户

- [ ] 9. 实现定时调度器 (PushScheduler)
  - [ ] 9.1 创建PushScheduler类
    - 在backend_core/scheduler/目录下创建push_scheduler.py
    - 使用APScheduler实现定时任务
    - 实现start和stop方法
    - 实现add_push_job和remove_push_job方法
    - 实现get_scheduled_jobs方法
    - 从配置加载默认推送时间(09:30, 15:30)
    - _需求: 4.1, 4.2, 4.5_

  - [ ]* 9.2 为调度器编写单元测试
    - 测试任务添加和移除
    - 测试任务列表查询
    - 测试调度器启动和停止
    - _需求: 4.1, 4.2_

- [ ] 10. 实现错误处理和日志记录
  - [ ] 10.1 创建ErrorHandler类
    - 在backend_api/services/目录下创建error_handler.py
    - 实现handle_push_error方法
    - 实现should_retry方法
    - 实现错误分类逻辑
    - _需求: 8.1, 8.3, 8.4, 8.5, 8.7_

  - [ ] 10.2 集成结构化日志记录
    - 实现log_push_event函数
    - 在关键位置添加日志记录
    - 记录错误和警告信息
    - _需求: 8.7_

  - [ ]* 10.3 为错误处理编写属性测试
    - **属性 24: 错误日志记录**
    - **验证需求: 8.7**

- [ ] 11. 实现API接口
  - [ ] 11.1 创建配置管理API
    - 在backend_api/目录下创建push_routes.py
    - GET /api/push/config - 获取用户推送配置
    - PUT /api/push/config - 更新用户推送配置
    - POST /api/push/config/bind-wechat - 绑定微信
    - POST /api/push/config/unbind-wechat - 解绑微信
    - _需求: 1.4, 1.7, 10.1_

  - [ ] 11.2 创建推送记录API
    - GET /api/push/records - 查询推送记录(支持筛选)
    - GET /api/push/records/{id} - 获取单条记录详情
    - POST /api/push/records/{id}/retry - 手动重发
    - _需求: 6.6, 6.7, 7.6, 10.2_

  - [ ] 11.3 创建推送控制API
    - POST /api/push/trigger - 手动触发推送
    - GET /api/push/status - 查询推送系统状态
    - _需求: 10.3, 10.4_

  - [ ] 11.4 创建管理员API
    - GET /api/admin/push/configs - 查看所有用户配置
    - GET /api/admin/push/records - 查看所有推送记录
    - POST /api/admin/push/global-control - 全局暂停/恢复
    - _需求: 10.5, 10.6_

  - [ ]* 11.5 为API接口编写属性测试
    - **属性 26: API配置管理**
    - **属性 27: API推送记录查询**
    - **属性 28: API手动推送触发**
    - **属性 29: 管理员全局查看权限**
    - **属性 30: 全局推送开关**
    - **验证需求: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

  - [ ]* 11.6 为API接口编写集成测试
    - 测试完整的API调用链
    - 测试权限验证
    - 测试错误响应
    - _需求: 10.1, 10.2, 10.3, 10.5, 10.6_

- [ ] 12. 配置和部署准备
  - [ ] 12.1 更新配置文件
    - 在backend_api/config.py中添加SMTP配置
    - 添加推送配置(重试次数、批量大小等)
    - 添加微信配置(如果需要)
    - 支持环境变量覆盖
    - _需求: 7.2_

  - [ ] 12.2 创建启动脚本
    - 创建启动调度器的脚本
    - 创建数据库初始化脚本(运行migrations/add_wechat_push_tables.py)
    - 创建测试数据生成脚本
    - _需求: 4.2, 4.6_

  - [ ] 12.3 编写部署文档
    - 环境要求
    - 配置说明
    - 启动步骤
    - 监控指标
    - _需求: 所有_

- [ ] 13. 最终集成测试
  - [ ]* 13.1 端到端推送流程测试
    - 创建测试用户和配置
    - 触发推送
    - 验证报告生成
    - 验证消息发送
    - 验证记录创建
    - _需求: 所有核心需求_

  - [ ]* 13.2 定时任务集成测试
    - 启动调度器
    - 模拟时间触发
    - 验证批量推送执行
    - _需求: 4.1, 4.2, 4.3, 4.4_

- [ ] 14. 最终检查点 - 确保所有测试通过
  - 运行所有单元测试
  - 运行所有属性测试
  - 运行所有集成测试
  - 确保测试覆盖率达标
  - 如有问题请询问用户


## 注意事项

- 标记为`*`的任务是可选的测试任务,可以跳过以加快MVP开发
- 每个任务都引用了具体的需求编号,便于追溯
- 检查点任务确保增量验证,及早发现问题
- 属性测试使用Hypothesis框架,每个测试运行最少100次迭代
- 所有测试文件放在`.\test`目录下
- 实现使用Python语言,基于现有的PostgreSQL数据库和服务

## 实现路径说明

基于现有代码库结构,各组件的实现位置:

- **数据模型**: backend_api/models.py (已完成)
- **迁移脚本**: migrations/add_wechat_push_tables.py (已完成)
- **服务层**: backend_api/services/ (EmailService, ConfigService, ReportService, RecordRepository, PushService, ErrorHandler)
- **调度器**: backend_core/scheduler/ (PushScheduler)
- **API路由**: backend_api/push_routes.py
- **配置**: backend_api/config.py (需要添加SMTP和推送相关配置)
- **测试**: test/ (所有测试文件)

## 现有资源

- ✅ CSVReportGenerator: backend_core/reports/csv_report_generator.py
- ✅ WeChatService: backend_core/wechat/wechat_service.py
- ✅ 数据库连接: backend_core/database/db.py
- ✅ 用户认证: backend_api/auth.py, backend_api/auth_routes.py

## 技术栈

- **语言**: Python 3.8+
- **数据库**: PostgreSQL
- **ORM**: SQLAlchemy
- **定时任务**: APScheduler
- **异步任务**: 可选使用Celery进行并发处理
- **测试框架**: pytest
- **属性测试**: Hypothesis
- **Mock框架**: unittest.mock
- **邮件**: smtplib + email
- **Web框架**: FastAPI (用于API接口)
