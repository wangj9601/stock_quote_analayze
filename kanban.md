# stock_quote_analayze
# 股票分析系统

## 📈 项目介绍

这是一个基于 FastAPI + SQLAlchemy + HTML/CSS/JavaScript 开发的股票分析系统，提供实时行情、历史行情、个股分析、自选股管理等功能。

## 🚀 快速启动

### 方式一：一键启动（推荐）
```bash
python start_system.py
```

### 方式二：分别启动
```bash
# 1. 启动后端API服务
python run.py

# 2. 启动前端服务
python start_frontend.py
```

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

## 🔧 常见问题解决

### 首页乱码问题
- 确保所有HTML文件都设置了`<meta charset="UTF-8">`
- Python文件建议使用UTF-8编码
- 如遇异常请清除浏览器缓存或强制刷新

### CORS跨域问题
- 前后端分离部署时，需在 FastAPI 中正确配置 CORS 中间件，允许前端域名访问。

### 数据库问题
- 默认使用 SQLite 数据库，首次启动会自动初始化。

## 🌐 访问地址
- **登录页面**: http://localhost:8000/login.html
- **首页**: http://localhost:8000/index.html
- **后端API**: http://localhost:5000
- **管理后台**: http://localhost:8001/

## 📋 主要功能

- ✅ 实时股票行情数据
- ✅ 历史行情查询（支持按股票代码、日期区间、分页、导出CSV）
- ✅ 市场指数监控
- ✅ 个股详细分析
- ✅ 自选股管理
- ✅ K线图表展示
- ✅ 用户登录注册
- ✅ 价格提醒功能
- ✅ 财经新闻资讯
- ✅ 管理后台界面

## 🛠 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite + akshare/tushare
- **前端**: 原生HTML5 + CSS3 + JavaScript
- **数据源**: akshare、tushare（真实股票数据）
- **样式**: 自定义CSS（股票交易风格）

## 📁 项目结构

```
stock_quote_analayze/
├── backend_api/         # 后端FastAPI应用
│   ├── main.py         # 主应用入口
│   ├── stock/          # 股票相关API（含历史行情）
│   └── database/       # 数据库相关
├── backend_core/       # 数据采集、模型等核心代码
├── frontend/           # 前端页面
│   ├── stock_history.html  # 历史行情页面
│   ├── css/            # 样式文件
│   └── js/             # JavaScript文件
├── admin/              # 管理后台
├── start_system.py     # 一键启动脚本
├── start_frontend.py   # 前端服务器
├── run.py              # 后端启动脚本
├── requirements.txt    # 依赖包列表
└── .gitignore          # Git忽略文件
```

## 📝 更新日志

### v1.2 (最新)
- ✨ 新增历史行情查询、导出、分页、日期筛选功能
- 🛠 后端切换为FastAPI+SQLAlchemy，接口更规范
- 🐞 修复跨域、编码等兼容性问题
- 💄 前端UI自适应优化，兼容PC/平板/手机

### v1.1
- 🔧 修复首页中文乱码问题
- 📝 重新格式化HTML代码结构
- ✨ 添加一键启动脚本
- 🚀 优化用户体验

### v1.0
- 🎉 初始版本发布
- 📈 基础股票分析功能
- 💻 前后端分离架构

## 📞 技术支持

如遇问题请检查：
1. Python版本（建议3.8+）
2. 依赖包是否正确安装
3. 数据库文件和权限
4. 网络连接是否正常
5. 浏览器是否支持现代标准

---

💡 **提示**: 首次使用建议运行`python start_system.py`一键启动所有服务。 
