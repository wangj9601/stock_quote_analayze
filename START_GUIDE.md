# 🚀 股票分析软件启动指南

## 📋 系统要求

- **Python 3.7+** (推荐3.8或更高版本)
- **现代浏览器** (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- **网络连接** (用于获取数据)

## ⚡ 快速启动 (推荐)

### 方法一：一键启动脚本

```bash
# 1. 启动后端服务 (在新的终端窗口)
cd backend-api
python start.py

# 2. 启动前端服务 (在另一个终端窗口)
cd ..
python start_frontend.py
```

启动成功后：
- 后端API: `http://localhost:5000`
- 前端应用: `http://localhost:8080`
- 会自动打开浏览器到登录页面

### 方法二：分步启动

#### 第一步：启动后端服务

```bash
# 进入后端目录
cd backend-api

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

#### 第二步：启动前端服务

```bash
# 回到项目根目录
cd ..

# 启动HTTP服务器
python -m http.server 8080

# 或使用Node.js (如果已安装)
npx http-server -p 8080
```

#### 第三步：访问应用

打开浏览器，访问: `http://localhost:8080/frontend/login.html`

## 🎯 功能演示

### 1. 用户注册/登录
- 访问登录页面
- 注册新账户或使用测试账户
- 登录成功后进入主界面

### 2. 浏览股票行情
- 查看市场指数
- 浏览股票列表
- 查看涨跌幅排行

### 3. 管理自选股
- 搜索并添加股票到自选股
- 查看自选股列表
- 删除不需要的股票

### 4. 查看个股详情
- 点击任意股票进入详情页
- 查看实时行情数据
- 查看基本面信息

### 5. 智能分析
- 查看系统推荐
- 获取买卖建议
- 查看预测分析

### 6. 财经资讯
- 浏览最新财经新闻
- 查看市场快讯

## 🛠️ 故障排除

### 问题1：后端启动失败

**错误信息**: `ModuleNotFoundError: No module named 'flask'`

**解决方案**:
```bash
pip install flask flask-cors werkzeug
```

**错误信息**: `Address already in use`

**解决方案**:
```bash
# 查找占用端口的进程
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # macOS/Linux

# 或更改端口
python app.py --port 5001
```

### 问题2：前端无法连接后端

**现象**: 页面显示但数据加载失败

**解决方案**:
1. 确认后端服务已启动
2. 检查浏览器控制台错误
3. 验证API地址配置：
   ```javascript
   // 在 frontend/js/common.js 中检查
   const API_BASE_URL = 'http://localhost:5000';
   ```

### 问题3：跨域错误 (CORS)

**错误信息**: `Access to fetch at 'http://localhost:5000' from origin 'http://localhost:8080' has been blocked by CORS policy`

**解决方案**: 后端已配置CORS，如仍有问题，检查Flask-CORS安装：
```bash
pip install flask-cors
```

### 问题4：数据库错误

**错误信息**: `no such table: users`

**解决方案**: 删除数据库文件重新初始化：
```bash
rm backend-api/database/stock_analysis.db
python backend-api/start.py
```

## 📱 浏览器兼容性

### 推荐浏览器
- **Chrome 90+** ✅ 完全支持
- **Firefox 88+** ✅ 完全支持  
- **Safari 14+** ✅ 完全支持
- **Edge 90+** ✅ 完全支持

### 不支持的浏览器
- Internet Explorer (所有版本) ❌
- Chrome < 70 ❌
- Firefox < 65 ❌

## 🔧 高级配置

### 修改端口配置

**后端端口** (默认5000):
```python
# 在 backend-api/app.py 最后一行修改
app.run(debug=True, host='0.0.0.0', port=5001)
```

**前端端口** (默认8080):
```bash
python -m http.server 8081
```

**更新API地址**:
```javascript
// 在 frontend/js/common.js 中修改
const API_BASE_URL = 'http://localhost:5001';
```

### 数据库配置

**查看数据库内容**:
```bash
cd backend-api/database
sqlite3 stock_analysis.db
.tables
SELECT * FROM users;
.quit
```

**重置数据库**:
```bash
rm backend-api/database/stock_analysis.db
python backend-api/app.py  # 会自动重新创建
```

## 📊 测试数据

系统内置模拟数据，包括：
- 主要股票指数 (上证、深证、创业板)
- 热门股票 (茅台、五粮液、平安银行等)
- 行业板块数据
- 财经新闻
- 智能分析建议

## 🚀 性能优化

### 前端优化
- 启用浏览器缓存
- 使用CDN加载静态资源
- 图片懒加载

### 后端优化
- 数据库索引优化
- Redis缓存
- 负载均衡

## 📞 技术支持

### 常见问题
1. 数据更新频率？ - 演示版本使用模拟数据，30秒刷新一次
2. 支持实时数据吗？ - 当前为延时数据，可扩展WebSocket实时推送
3. 能否部署到服务器？ - 支持，参考部署文档

### 获得帮助
- 查看项目README.md
- 检查浏览器开发者工具
- 查看终端错误信息

## 🎉 开始使用

1. **启动服务** - 按照上述步骤启动前后端服务
2. **注册账户** - 在登录页面注册新用户
3. **探索功能** - 从首页开始探索各个功能模块
4. **添加自选股** - 搜索并添加感兴趣的股票
5. **查看分析** - 体验智能分析和预测功能

---

🎯 **提示**: 第一次启动可能需要几秒钟初始化数据库，请耐心等待。

✨ **体验建议**: 建议使用Chrome或Firefox浏览器获得最佳体验。 