# 股票分析系统核心模块技术规范

## 目录
1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [目录结构](#目录结构)
4. [开发规范](#开发规范)
5. [数据采集规范](#数据采集规范)
6. [数据库规范](#数据库规范)
7. [测试规范](#测试规范)
8. [部署规范](#部署规范)
9. [更新日志](#更新日志)
10. [参考文档](#参考文档)

## 项目概述

backend_core 负责股票分析系统的数据采集、数据处理、数据存储、模型算法等核心功能。包括对接 akshare、tushare 等第三方数据源，定时采集行情、财务、指数等数据，进行清洗、转换、入库，并为后端API提供高质量数据支撑。

## 技术栈
- **语言**: Python 3.8+
- **数据采集**: akshare、tushare
- **数据处理**: pandas、numpy
- **数据库**: SQLite3（通过SQLAlchemy或原生SQL）
- **调度**: APScheduler、crontab
- **日志**: logging
- **测试**: pytest、unittest、mock

## 目录结构

```
backend_core/
├── data_collectors/         # 数据采集器（akshare、tushare等）
│   ├── akshare/
│   │   ├── historical.py
│   │   └── ...
│   ├── tushare/
│   │   ├── historical.py
│   │   └── ...
├── database/                # 数据库相关
│   └── stock_analysis.db
├── models/                  # 数据模型与结构
├── rules/                   # 技术规范与规则
├── logs/                    # 日志文件
├── config/                  # 配置文件
├── test/                    # 单元测试
└── ...
```

## 开发规范
- 遵循PEP8编码规范，4空格缩进，UTF-8编码。
- 所有函数、类、模块需有文档字符串说明。
- 复杂逻辑需有详细注释。
- 统一异常处理，关键操作加日志记录。
- 采集、清洗、入库、调度等功能模块化，便于维护和扩展。
- 日志建议按天分文件，重要异常需报警。

## 数据采集规范
- 采集接口需支持增量与全量采集。
- 采集前需校验数据源可用性，采集后需校验数据完整性。
- 采集数据需统一清洗、去重、标准化字段名与格式。
- 支持多数据源（akshare、tushare），可配置优先级与容灾。
- 采集结果以DataFrame为主，入库前转换为dict或SQL批量写入。
- 采集调度可用APScheduler、crontab等，支持定时与手动触发。
- 采集日志需详细记录采集时间、数据量、异常等。

## 数据库规范
- 表结构需有主键，重要字段加索引。
- 时间字段统一为TEXT(YYYYMMDD)或TIMESTAMP。
- 支持批量写入与事务，保证数据一致性。
- 采集表如 historical_quotes 字段需与API一致（code, date, open, close, high, low, volume, ...）。
- 数据库连接需支持多线程/多进程安全。

## 测试规范
- 单元测试用pytest，覆盖率>80%。
- 采集、清洗、入库等核心流程需有mock测试。
- 测试用例需覆盖异常、边界、数据完整性等。
- 测试数据与生产数据隔离，测试后自动清理。

## 部署规范
- 依赖通过 requirements.txt 管理。
- 首次部署需初始化数据库结构。
- 定时任务建议用APScheduler或系统crontab。
- 日志、数据、配置等目录需有写权限。
- 重要采集任务建议加监控与报警。

## 更新日志

### v1.2.0 (2025-06)
- 完善akshare/tushare采集器，支持历史行情、财务、指数等多源采集
- 采集、清洗、入库流程标准化
- 增加批量入库与事务支持
- 完善单元测试与mock
- 文档与规范同步更新

## 参考文档
- [akshare官方文档](https://akshare.readthedocs.io/zh_CN/latest/)
- [tushare官方文档](https://tushare.pro/document/2)
- [pandas官方文档](https://pandas.pydata.org/pandas-docs/stable/)
- [SQLAlchemy官方文档](https://docs.sqlalchemy.org/)
- [pytest官方文档](https://docs.pytest.org/) 