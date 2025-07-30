# 依赖管理指南

## 概述

本项目提供了多个requirements文件来满足不同环境的需求：

- `requirements.txt` - 完整依赖（包含开发工具）
- `requirements-prod.txt` - 生产环境依赖（仅运行时必需）
- `requirements-dev.txt` - 开发环境依赖（开发工具和测试框架）

## 文件说明

### 1. requirements.txt
**用途**: 完整项目依赖，包含所有运行时和开发工具依赖
**适用场景**: 
- 开发环境完整安装
- 需要所有功能的用户
- 项目初始设置

**包含内容**:
- Web框架 (FastAPI, Uvicorn)
- 数据库驱动 (PostgreSQL, SQLite)
- 数据处理 (Pandas, NumPy, AKShare)
- 开发工具 (Black, Isort, Flake8, Pytest)
- 日志和监控工具
- 配置管理工具

### 2. requirements-prod.txt
**用途**: 生产环境最小化依赖，仅包含运行时必需的包
**适用场景**:
- 生产环境部署
- Docker容器构建
- 服务器部署
- 性能优化场景

**包含内容**:
- Web框架 (FastAPI, Uvicorn)
- 数据库驱动 (PostgreSQL)
- 数据处理 (Pandas, NumPy, AKShare)
- 核心工具 (Pydantic, Requests, Aiohttp)
- 日志和监控工具
- 不包含开发工具和测试框架

### 3. requirements-dev.txt
**用途**: 开发环境额外依赖，包含开发工具和测试框架
**适用场景**:
- 开发环境设置
- 代码质量检查
- 测试执行
- 调试和性能分析

**包含内容**:
- 代码格式化工具 (Black, Isort)
- 代码质量检查 (Flake8, MyPy)
- 测试框架 (Pytest, Pytest-cov)
- 调试工具 (IPython, IPdb)
- 文档工具 (Sphinx)
- 性能分析工具

## 安装指南

### 生产环境安装
```bash
# 方法1: 使用生产环境依赖文件
pip install -r requirements-prod.txt

# 方法2: 使用部署脚本（推荐）
python deploy.py --env production
```

### 开发环境安装
```bash
# 方法1: 分步安装
pip install -r requirements-prod.txt
pip install -r requirements-dev.txt

# 方法2: 使用完整依赖文件
pip install -r requirements.txt

# 方法3: 使用部署脚本
python deploy.py --env development
```

### 完整环境安装
```bash
# 安装所有依赖
pip install -r requirements.txt

# 或者使用部署脚本
python deploy.py --env development --install-all
```

## 部署配置

### deploy_config.json 配置
```json
{
  "environment": "production",  // "production" 或 "development"
  "install_submodules": true,   // 是否安装子模块依赖
  "debug": false,
  "log_level": "INFO"
}
```

### 环境变量配置
```bash
# 设置环境类型
export DEPLOY_ENV=production

# 设置是否安装子模块
export INSTALL_SUBMODULES=true
```

## 依赖检查

### 快速检查
```bash
# 运行快速依赖检查
python quick_dependency_check.py
```

### 完整检查
```bash
# 运行完整依赖分析
python check_dependencies.py
```

### 生成报告
```bash
# 生成依赖报告
python check_dependencies.py
# 报告将保存到 dependency_report.txt
```

## 版本管理

### 版本冲突解决
如果遇到版本冲突，可以：

1. **调整版本范围**:
   ```txt
   # 从精确版本改为范围版本
   pydantic>=2.6.1,<3.0.0
   ```

2. **使用兼容版本**:
   ```bash
   pip install --upgrade pydantic
   ```

3. **创建虚拟环境**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

### 依赖更新
```bash
# 更新所有依赖
pip install --upgrade -r requirements.txt

# 更新特定依赖
pip install --upgrade fastapi uvicorn

# 生成新的requirements文件
pip freeze > requirements-new.txt
```

## 常见问题

### 1. 版本冲突
**问题**: `pydantic==2.6.1` 与已安装的 `pydantic==2.11.7` 冲突
**解决**: 使用版本范围 `pydantic>=2.6.1,<3.0.0`

### 2. 缺失依赖
**问题**: 运行时提示 `ModuleNotFoundError`
**解决**: 运行 `pip install -r requirements-prod.txt`

### 3. 开发工具缺失
**问题**: 无法运行测试或代码格式化
**解决**: 安装开发依赖 `pip install -r requirements-dev.txt`

### 4. PostgreSQL连接问题
**问题**: 无法连接到PostgreSQL数据库
**解决**: 确保安装了 `psycopg2-binary` 并检查数据库配置

## 最佳实践

### 1. 环境隔离
- 为每个项目创建独立的虚拟环境
- 使用 `requirements-prod.txt` 进行生产部署
- 使用 `requirements-dev.txt` 进行开发

### 2. 版本锁定
- 生产环境使用精确版本号
- 开发环境可以使用版本范围
- 定期更新依赖版本

### 3. 依赖管理
- 定期运行依赖检查
- 及时更新安全补丁
- 移除未使用的依赖

### 4. 部署优化
- 使用多阶段Docker构建
- 分离生产环境和开发环境依赖
- 使用缓存加速依赖安装

## 工具推荐

### 1. pip-tools
```bash
# 安装pip-tools
pip install pip-tools

# 编译依赖
pip-compile requirements.in

# 同步依赖
pip-sync requirements.txt
```

### 2. Poetry
```bash
# 安装Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 初始化项目
poetry init

# 安装依赖
poetry install
```

### 3. Pipenv
```bash
# 安装Pipenv
pip install pipenv

# 安装依赖
pipenv install

# 激活环境
pipenv shell
```

## 总结

通过合理使用不同的requirements文件，可以：

1. **优化部署大小**: 生产环境只安装必需依赖
2. **提高开发效率**: 开发环境包含所有工具
3. **确保兼容性**: 版本范围避免冲突
4. **简化维护**: 清晰的依赖分类和管理

建议根据实际需求选择合适的安装方式，并定期检查和更新依赖。 