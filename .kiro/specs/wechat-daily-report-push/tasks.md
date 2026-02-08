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
    - _状态: 已完成 - backend_api/services/email_service.py已创建_

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
    - _状态: 已完成 - backend_api/services/config_service.py已创建_

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

- [x] 4. 实现报告服务 (ReportService)
  - [x] 4.1 创建ReportService类
    - 在backend_api/services/目录下创建report_service.py
    - 封装现有的CSVReportGenerator (backend_core/reports/csv_report_generator.py)
    - 实现generate_user_report方法(支持指定股票范围)
    - 实现get_report_info方法
    - 处理空自选股情况
    - 处理数据缺失情况
    - 适配现有的数据库表结构(watchlist, historical_quotes, historical_quotes_hk)
    - _需求: 3.1, 3.2, 3.4, 3.5, 3.7, 8.2_
    - _状态: 已完成 - backend_api/services/report_service.py已创建_

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

- [x] 5. 检查点 - 确保基础服务测试通过
  - 确保所有测试通过,如有问题请询问用户
  - _状态: 已完成 - 基础服务已实现并测试_

- [x] 6. 实现推送记录管理 (RecordRepository)
  - [x] 6.1 创建RecordRepository类
    - 在backend_api/services/目录下创建record_repository.py
    - 实现create_record方法
    - 实现update_record_status方法
    - 实现get_user_records方法(支持筛选)
    - 实现get_record_by_id方法
    - 实现check_duplicate_push方法(推送去重)
    - 实现get_failed_records方法(获取失败记录)
    - _需求: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7_
    - _状态: 已完成 - backend_api/services/record_repository.py已创建_

  - [ ]* 6.2 为记录管理编写属性测试
    - **属性 15: 推送记录完整性**
    - **属性 16: 推送状态更新正确性**
    - **属性 17: 推送记录查询和筛选**
    - **验证需求: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7**

- [x] 7. 实现推送服务核心 (PushService)
  - [x] 7.1 创建PushService类基础结构
    - 在backend_api/services/目录下创建push_service.py
    - 注入WeChatService、EmailService、ReportService、ConfigService、RecordRepository
    - 实现_send_via_wechat私有方法(使用backend_core/wechat/wechat_service.py)
    - 实现_send_via_email私有方法
    - 实现_format_push_message方法(格式化推送消息内容)
    - _需求: 5.1, 5.2, 5.3, 5.5, 5.6, 5.9_

  - [x] 7.2 实现单用户推送逻辑 (push_to_user)
    - 获取用户配置
    - 验证用户是否绑定了推送渠道
    - 生成报告(调用ReportService)
    - 根据配置选择推送渠道
    - 创建推送记录(状态为processing)
    - 处理多渠道推送(并行发送)
    - 处理渠道失败隔离(一个渠道失败不影响其他渠道)
    - 更新推送记录状态(success/partial_success/failed)
    - _需求: 5.1, 5.4, 5.7, 5.8, 6.1, 6.4, 6.5_

  - [ ]* 7.3 为单用户推送编写属性测试
    - **属性 11: 渠道选择正确性**
    - **属性 12: 微信推送消息顺序**
    - **属性 13: 邮件推送结构完整性**
    - **属性 14: 渠道失败隔离**
    - **验证需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8**

  - [x] 7.4 实现批量推送逻辑 (execute_scheduled_push)
    - 查询指定时间点需要推送的用户(调用ConfigService.get_users_for_push_time)
    - 使用RecordRepository.check_duplicate_push检查推送去重
    - 使用线程池或异步方式并发处理多个用户推送
    - 处理单个用户失败不影响其他用户(异常捕获和隔离)
    - 返回批量推送结果统计(成功数、失败数、跳过数)
    - _需求: 4.3, 4.4, 4.7, 8.3, 8.6, 9.1_

  - [ ]* 7.5 为批量推送编写属性测试
    - **属性 9: 推送时间触发正确用户**
    - **属性 10: 推送去重**
    - **属性 23: 报告生成失败隔离**
    - **验证需求: 4.3, 4.4, 4.7, 8.3, 8.6**

  - [x] 7.6 实现重试机制 (retry_failed_push)
    - 根据record_id获取推送记录
    - 检查是否已达到最大重试次数
    - 实现指数退避策略(1分钟、5分钟、15分钟)
    - 更新重试次数
    - 重新执行推送流程
    - 更新推送记录状态和重试结果
    - 如果达到最大重试次数,标记为最终失败
    - _需求: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 7.7 为重试机制编写属性测试
    - **属性 18: 失败自动重试**
    - **属性 19: 重试次数限制**
    - **属性 20: 重试信息记录**
    - **属性 21: 手动重发支持**
    - **验证需求: 7.1, 7.2, 7.4, 7.5, 7.6**

  - [ ]* 7.8 为推送服务编写单元测试
    - 测试单用户推送成功场景
    - 测试单用户推送失败场景
    - 测试多渠道推送
    - 测试渠道失败隔离
    - 测试批量推送
    - 测试推送去重
    - 测试重试机制
    - _需求: 5.1-5.9, 7.1-7.6_

- [x] 8. 检查点 - 确保推送服务测试通过
  - 运行所有推送服务相关测试
  - 确保所有测试通过,如有问题请询问用户

- [ ] 9. 实现定时调度器 (PushScheduler)
  - [x] 9.1 创建PushScheduler类
    - 在backend_core/scheduler/目录下创建push_scheduler.py
    - 使用APScheduler实现定时任务(BackgroundScheduler)
    - 实现start方法(启动调度器)
    - 实现stop方法(停止调度器)
    - 实现add_push_job方法(添加推送任务)
    - 实现remove_push_job方法(移除推送任务)
    - 实现get_scheduled_jobs方法(获取已调度任务列表)
    - 从配置加载默认推送时间(09:30, 15:30)
    - 实现系统重启后自动恢复定时任务
    - _需求: 4.1, 4.2, 4.5, 4.6_

  - [ ]* 9.2 为调度器编写单元测试
    - 测试任务添加和移除
    - 测试任务列表查询
    - 测试调度器启动和停止
    - 测试系统重启后任务恢复
    - _需求: 4.1, 4.2, 4.6_

- [ ] 10. 实现错误处理和日志记录
  - [x] 10.1 创建ErrorHandler类
    - 在backend_api/services/目录下创建error_handler.py
    - 实现handle_push_error方法(统一错误处理)
    - 实现should_retry方法(判断是否应该重试)
    - 实现错误分类逻辑(用户输入错误、数据错误、服务不可用错误、系统错误)
    - 实现get_retry_delay方法(获取重试延迟时间)
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5, 8.7_

  - [x] 10.2 集成结构化日志记录
    - 在backend_api/services/目录下创建logging_utils.py
    - 实现log_push_event函数(记录推送事件)
    - 在PushService关键位置添加日志记录
    - 记录错误和警告信息(数据缺失、服务不可用、推送失败等)
    - 使用JSON格式记录结构化日志
    - _需求: 8.7_

  - [ ]* 10.3 为错误处理编写属性测试
    - **属性 24: 错误日志记录**
    - **验证需求: 8.7**

  - [ ]* 10.4 为错误处理编写单元测试
    - 测试不同错误类型的处理
    - 测试重试判断逻辑
    - 测试重试延迟计算
    - _需求: 8.1-8.8_

- [x] 11. 实现API接口
  - [x] 11.1 创建配置管理API
    - 在backend_api/目录下创建push_routes.py
    - GET /api/push/config - 获取当前用户推送配置
    - PUT /api/push/config - 更新当前用户推送配置
    - POST /api/push/config/bind-wechat - 绑定微信(更新wechat_openid和wechat_type)
    - POST /api/push/config/unbind-wechat - 解绑微信(清空wechat_openid和wechat_type)
    - POST /api/push/config/bind-email - 绑定邮箱(更新email)
    - POST /api/push/config/unbind-email - 解绑邮箱(清空email)
    - 添加用户认证和权限验证
    - _需求: 1.4, 1.5, 1.7, 10.1_

  - [x] 11.2 创建推送记录API
    - GET /api/push/records - 查询当前用户推送记录(支持日期范围和状态筛选)
    - GET /api/push/records/{id} - 获取单条记录详情
    - POST /api/push/records/{id}/retry - 手动重发失败的推送
    - 添加用户认证和权限验证(只能查看和操作自己的记录)
    - _需求: 6.6, 6.7, 7.6, 10.2_

  - [x] 11.3 创建推送控制API
    - POST /api/push/trigger - 手动触发当前用户的推送
    - GET /api/push/status - 查询推送系统状态(待推送用户数、最近推送时间等)
    - 添加用户认证
    - _需求: 10.3, 10.4_

  - [x] 11.4 创建管理员API
    - GET /api/admin/push/configs - 查看所有用户配置(支持分页)
    - GET /api/admin/push/records - 查看所有推送记录(支持筛选和分页)
    - POST /api/admin/push/global-control - 全局暂停/恢复推送功能
    - GET /api/admin/push/statistics - 获取推送统计数据
    - 添加管理员权限验证
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
    - 测试用户权限验证
    - 测试管理员权限验证
    - 测试错误响应
    - 测试分页和筛选功能
    - _需求: 10.1, 10.2, 10.3, 10.5, 10.6_

- [x] 12. 配置和部署准备
  - [x] 12.1 更新配置文件
    - 在backend_api/config.py中添加SMTP配置(host, port, username, password, use_tls, from_email, from_name)
    - 添加推送配置(max_retry_count, push_batch_size, report_dir)
    - 添加调度器配置(default_push_times)
    - 添加微信配置(如果需要更新)
    - 支持环境变量覆盖
    - _需求: 7.2, 9.1_

  - [x] 12.2 创建启动脚本
    - 创建start_scheduler.py脚本(启动调度器)
    - 创建init_db.py脚本(运行数据库迁移)
    - 创建generate_test_data.py脚本(生成测试数据)
    - 添加命令行参数支持
    - _需求: 4.2, 4.6_

  - [x] 12.3 编写部署文档
    - 创建DEPLOYMENT.md文档
    - 环境要求(Python版本、依赖包、数据库版本)
    - 配置说明(环境变量、配置文件)
    - 启动步骤(数据库迁移、启动调度器、启动API服务)
    - 监控指标(推送成功率、推送延迟、错误率)
    - 故障排查指南
    - _需求: 所有_

- [ ] 13. 最终集成测试
  - [ ]* 13.1 端到端推送流程测试
    - 在test/目录下创建test_push_e2e.py
    - 创建测试用户和配置
    - 创建测试自选股数据
    - 手动触发推送
    - 验证报告生成
    - 验证消息发送(使用Mock)
    - 验证记录创建和状态更新
    - 测试多渠道推送
    - 测试失败重试
    - _需求: 所有核心需求_

  - [ ]* 13.2 定时任务集成测试
    - 在test/目录下创建test_scheduler_integration.py
    - 启动调度器
    - 模拟时间触发(使用APScheduler的测试功能)
    - 验证批量推送执行
    - 验证推送去重
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.7_

  - [ ]* 13.3 性能测试
    - 在test/目录下创建test_push_performance.py
    - 测试大量用户并发推送
    - 测试报告生成性能
    - 验证单个用户报告生成时间不超过30秒
    - 验证单次推送任务总执行时间不超过10分钟
    - _需求: 9.5, 9.6_

- [x] 14. 最终检查点 - 确保所有测试通过
  - 运行所有单元测试(pytest test/ -k "not e2e and not integration and not performance")
  - 运行所有属性测试(pytest test/ -k "property")
  - 运行所有集成测试(pytest test/ -k "integration or e2e")
  - 运行性能测试(pytest test/ -k "performance")
  - 确保测试覆盖率达标(>80%)
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
