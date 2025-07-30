# 股票分析系统后端技术规范

## 目录
1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [开发规范](#开发规范)
5. [API规范](#api规范)
6. [数据库规范](#数据库规范)
7. [安全规范](#安全规范)
8. [测试规范](#测试规范)
9. [部署规范](#部署规范)

## 项目概述

股票分析系统后端是系统的核心服务层，负责提供数据服务、业务逻辑处理和系统管理功能。采用FastAPI框架构建，提供RESTful API接口，支持前端和管理端的各项功能需求。

## 技术栈

### 核心框架
- **Web框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据库**: PostgreSQL
- **API风格**: RESTful
- **认证方式**: JWT Token
- **跨域处理**: FastAPI CORS Middleware
- **数据采集**: AKShare、Tushare

### 开发工具
- **版本控制**: Git
- **代码规范**: PEP 8
- **测试框架**: pytest
- **文档工具**: Markdown

## 项目结构

```
backend_api/
├── main.py                # FastAPI主应用入口
├── stock/                 # 股票相关API（含历史行情）
├── database/              # 数据库相关
├── models.py              # ORM模型定义
├── test/                  # 测试目录
│   └── test_*.py
├── requirements.txt       # 依赖管理
└── rules/                 # 规范文档
```

## 开发规范

### 1. 代码风格
- 遵循PEP 8编码规范
- 使用4个空格缩进
- 行长度不超过120字符
- 使用UTF-8编码

### 2. 命名规范
- **文件名**: 小写字母，下划线分隔
- **函数名**: 小写字母，下划线分隔
- **类名**: 大驼峰命名
- **常量**: 大写字母，下划线分隔

### 3. 注释规范
- 所有函数必须包含文档字符串
- 复杂逻辑必须添加行内注释
- API接口必须说明参数和返回值

### 4. 错误处理
- 统一使用try-except进行异常捕获
- 所有异常必须记录日志
- API错误响应统一格式
  ```python
  try:
      # 业务逻辑
  except Exception as e:
      logger.error(f"操作失败: {str(e)}")
      raise HTTPException(status_code=500, detail=str(e))
  ```

## API规范

### 1. URL规范
- 使用名词复数形式
- 版本控制建议：/api/v1/（当前项目为 /api/stock/xxx）
- 资源层级不超过3层

### 2. 请求方法
- GET: 获取资源
- POST: 创建资源
- PUT/PATCH: 更新资源
- DELETE: 删除资源

### 3. 响应格式
```json
{
    "items": [...],
    "total": 100
}
```
或
```json
{
    "success": true/false,
    "message": "提示信息",
    "data": {...},
    "error": "错误信息"
}
```

### 4. 状态码使用
- 200: 成功
- 400: 请求参数错误
- 401: 未认证
- 403: 无权限
- 404: 资源不存在
- 500: 服务器错误

## 数据库规范

### 1. 表设计规范
- 所有表必须包含主键
- 使用外键保证数据完整性（如有必要）
- 关键字段必须建立索引
- 时间字段统一使用TEXT(YYYYMMDD)或TIMESTAMP

### 2. 表结构示例
```sql
CREATE TABLE historical_quotes (
    code TEXT,
    ts_code TEXT,
    name TEXT,
    market TEXT,
    date TEXT, -- 格式YYYYMMDD
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    change_percent REAL,
    collected_source TEXT,
    collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date)
);
```

### 3. SQL规范
- 使用参数化查询防止SQL注入
- 查询必须指定具体字段
- 大量数据操作使用事务
```python
result = db.execute(text('SELECT code, date FROM historical_quotes WHERE code = :code'), {"code": code})
```

## 安全规范

### 1. 认证安全
- 密码必须加密存储
- JWT Token有效期设置
- 敏感操作二次验证

### 2. 数据安全
- 输入数据验证
- SQL注入防护
- XSS防护

### 3. 接口安全
- 请求频率限制（如有必要）
- 参数验证
- 跨域控制（CORS）
- 日志记录

## 测试规范

### 1. 单元测试
- 测试覆盖率要求>80%
- 每个API接口必须有测试用例
- 测试数据使用测试数据库
- 测试完成后清理数据

### 2. 测试用例示例
```python
import pytest
from httpx import AsyncClient
from backend_api.main import app

@pytest.mark.asyncio
async def test_get_stock_history():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/history", params={
            "code": "002539",
            "page": 1,
            "size": 10
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
```

### 3. 测试运行
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest backend_api/test/test_stock_history_api.py
```

## 部署规范

### 1. 环境要求
- Python 3.8+
- 必要的系统依赖
- 数据库配置
- 网络端口配置

### 2. 部署步骤
1. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
2. 初始化数据库
   ```bash
   python run.py  # 首次启动会自动初始化
   ```
3. 启动服务
   ```bash
   python start_system.py
   ```

### 3. 监控要求
- 服务状态监控
- 性能监控
- 错误日志监控
- 数据库监控

### 4. 备份策略
- 数据库定期备份
- 配置文件备份
- 日志文件归档
- 备份文件验证

## 更新日志

### v1.2.0 (2025-06)
- 切换为FastAPI+SQLAlchemy
- 新增历史行情API、导出、分页、日期筛选
- 完善测试用例
- 文档与规范同步更新

## 维护说明

本文档由后端开发团队维护，如有问题或建议，请提交Issue或联系开发团队。

## 参考资源

- [FastAPI官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [PEP 8规范](https://www.python.org/dev/peps/pep-0008/)
- [RESTful API设计指南](https://restfulapi.net/)
- [pytest官方文档](https://docs.pytest.org/) 