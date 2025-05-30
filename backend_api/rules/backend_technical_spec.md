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

股票分析系统后端是系统的核心服务层，负责提供数据服务、业务逻辑处理和系统管理功能。采用Flask框架构建，提供RESTful API接口，支持前端和管理端的各项功能需求。

## 技术栈

### 核心框架
- **Web框架**: Flask 2.x
- **数据库**: SQLite3
- **API风格**: RESTful
- **认证方式**: Session + Token
- **跨域处理**: Flask-CORS
- **数据采集**: AKShare

### 开发工具
- **版本控制**: Git
- **代码规范**: PEP 8
- **测试框架**: unittest
- **文档工具**: Markdown

## 项目结构

```
backend-api/
├── app_complete.py      # 主应用入口
├── database/           # 数据库文件目录
│   └── stock_analysis.db
├── test/              # 测试目录
│   ├── test_app_complete.py
│   └── test_*.py
├── requirements.txt    # 依赖管理
└── README.md          # 项目文档
```

## 开发规范

### 1. 代码风格
- 遵循PEP 8编码规范
- 使用4个空格缩进
- 行长度不超过120字符
- 使用UTF-8编码

### 2. 命名规范
- **文件名**: 小写字母，下划线分隔
  ```python
  app_complete.py
  test_app_complete.py
  ```
- **函数名**: 小写字母，下划线分隔
  ```python
  def get_market_indices():
  def init_db():
  ```
- **类名**: 大驼峰命名
  ```python
  class TestStockAnalysisSystem:
  ```
- **常量**: 大写字母，下划线分隔
  ```python
  MAX_RETRY_COUNT = 3
  DEFAULT_TIMEOUT = 30
  ```

### 3. 注释规范
- 所有函数必须包含文档字符串
  ```python
  def get_market_indices():
      """获取市场指数数据
    
      Returns:
          dict: 包含指数数据的字典
      """
  ```
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
      print(f"❌ 操作失败: {str(e)}")
      return jsonify({
          'success': False,
          'message': '操作失败',
          'error': str(e)
      }), 500
  ```

## API规范

### 1. URL规范
- 使用名词复数形式
- 版本控制：/api/v1/
- 资源层级不超过3层
  ```
  /api/users
  /api/users/{id}
  /api/users/{id}/status
  ```

### 2. 请求方法
- GET: 获取资源
- POST: 创建资源
- PUT: 更新资源
- DELETE: 删除资源

### 3. 响应格式
```json
{
    "success": true/false,
    "message": "提示信息",
    "data": {},
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
- 使用外键保证数据完整性
- 关键字段必须建立索引
- 时间字段统一使用TIMESTAMP

### 2. 表结构示例
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

### 3. SQL规范
- 使用参数化查询防止SQL注入
- 查询必须指定具体字段
- 大量数据操作使用事务
```python
cursor.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
```

## 安全规范

### 1. 认证安全
- 密码必须加密存储
- Session超时设置
- Token定期刷新
- 敏感操作二次验证

### 2. 数据安全
- 敏感数据加密
- 输入数据验证
- SQL注入防护
- XSS防护

### 3. 接口安全
- 请求频率限制
- 参数验证
- 跨域控制
- 日志记录

## 测试规范

### 1. 单元测试
- 测试覆盖率要求>80%
- 每个API接口必须有测试用例
- 测试数据使用测试数据库
- 测试完成后清理数据

### 2. 测试用例示例
```python
def test_user_login(self):
    """测试用户登录"""
    response = self.client.post('/api/auth/login',
        json=self.test_user,
        content_type='application/json'
    )
    self.assertEqual(response.status_code, 200)
    data = json.loads(response.data)
    self.assertTrue(data['success'])
```

### 3. 测试运行
```bash
# 运行所有测试
python -m unittest discover

# 运行特定测试
python -m unittest test_app_complete.py
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
   python -c "from app_complete import init_db; init_db()"
   ```
3. 启动服务
   ```bash
   python app_complete.py
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

### v1.0.0 (2024-01-20)
- 初始版本发布
- 实现基础功能
- 完成技术规范文档

## 维护说明

本文档由后端开发团队维护，如有问题或建议，请提交Issue或联系开发团队。

## 参考资源

- [Flask官方文档](https://flask.palletsprojects.com/)
- [SQLite文档](https://www.sqlite.org/docs.html)
- [PEP 8规范](https://www.python.org/dev/peps/pep-0008/)
- [RESTful API设计指南](https://restfulapi.net/) 