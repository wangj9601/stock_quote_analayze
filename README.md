# stock_quote_analayze
# 股票分析系统

## 📈 项目介绍

这是一个基于Flask + HTML/CSS/JavaScript开发的股票分析系统原型，提供实时行情数据、个股分析、自选股管理等功能。

## 🚀 快速启动

### 方式一：一键启动（推荐）
```bash
python start_system.py
```

### 方式二：分别启动
```bash
# 1. 启动后端API服务
cd backend-api
python app.py

# 2. 启动前端服务
python start_frontend.py
```

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

## 🔧 常见问题解决

### 首页乱码问题
如果遇到首页显示乱码，已在最新版本中修复：

1. **HTML文件编码**：确保所有HTML文件都设置了`<meta charset="UTF-8">`
2. **文件格式化**：重新格式化了压缩的HTML代码，提高可读性
3. **字符实体**：正确处理了HTML字符实体（如`&gt;`）
4. **表情符号**：修复了表情符号显示问题

### 浏览器缓存问题
如果页面显示异常，请：
1. 按`Ctrl+F5`强制刷新页面
2. 清除浏览器缓存
3. 使用隐私模式/无痕模式打开

### 编码设置检查确保以下文件编码设置正确：- 所有HTML文件：`<meta charset="UTF-8">`- Python文件：`# -*- coding: utf-8 -*-`- 系统区域设置：使用UTF-8编码## 🌐 访问地址- **登录页面**: http://localhost:8000/login.html (系统入口)- **首页**: http://localhost:8000/index.html (登录后访问)- **后端API**: http://localhost:5000- **管理后台**: http://localhost:8000/admin## 📋 主要功能

- ✅ 实时股票行情数据
- ✅ 市场指数监控
- ✅ 个股详细分析
- ✅ 自选股管理
- ✅ K线图表展示
- ✅ 用户登录注册
- ✅ 价格提醒功能
- ✅ 财经新闻资讯
- ✅ 管理后台界面

## 🛠 技术栈

- **后端**: Flask + SQLite + akshare
- **前端**: HTML5 + CSS3 + JavaScript
- **数据源**: akshare (真实股票数据)
- **样式**: 自定义CSS（股票交易风格）

## 📁 项目结构

```
cursor/
├── backend-api/       # 后端Flask应用
│   ├── app.py        # 主应用文件
│   └── database/     # SQLite数据库
├── frontend/          # 前端页面
│   ├── index.html    # 首页（已修复乱码）
│   ├── css/          # 样式文件
│   └── js/           # JavaScript文件
├── admin/            # 管理后台
├── start_system.py   # 一键启动脚本
├── start_frontend.py # 前端服务器
└── requirements.txt  # 依赖包列表
```

## 📝 更新日志

### v1.1 (最新)
- 🔧 修复首页中文乱码问题
- 📝 重新格式化HTML代码结构
- ✨ 添加一键启动脚本
- 🚀 优化用户体验

### v1.0
- 🎉 初始版本发布
- 📈 基础股票分析功能
- 💻 前后端分离架构

## 📞 技术支持

如果遇到任何问题，请检查：
1. Python版本（建议3.8+）
2. 依赖包是否正确安装
3. 网络连接是否正常
4. 浏览器是否支持现代标准

---

💡 **提示**: 首次使用建议运行`python start_system.py`一键启动所有服务。 
