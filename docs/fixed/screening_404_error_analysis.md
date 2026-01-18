# 选股API 404错误分析

## 错误信息
- **错误类型**: 404 Not Found
- **前端文件**: `frontend/js/screening.js:250`
- **函数**: `loadScreeningResults`
- **错误位置**: `screening.js:237:23`

## 问题分析

### 1. 前端请求的API端点

前端代码在 `screening.js:214` 请求：
```javascript
url = `${apiBaseUrl}/api/screening/one-yang-three-lines`;
```

### 2. 后端路由定义

后端路由定义在 `backend_api/stock/stock_screening_routes.py:503`：
```python
@router.get("/one-yang-three-lines")
async def get_one_yang_three_lines_strategy(...)
```

路由前缀：`/api/screening`（定义在第22行）

**完整路径应该是**: `/api/screening/one-yang-three-lines` ✅

### 3. 路由注册检查

在 `backend_api/main.py` 中，路由注册逻辑：

```python
# 第53-60行：尝试导入选股路由
try:
    from .stock.stock_screening_routes import router as stock_screening_router
    print("✅ stock_screening_routes 导入成功")
except Exception as e:
    print(f"❌ stock_screening_routes 导入失败: {e}")
    stock_screening_router = None

# 第170-181行：条件注册路由
if stock_screening_router:
    app.include_router(stock_screening_router)
else:
    print("⚠️ 选股路由未加载，跳过注册")
```

## 根本原因 ✅ **已确认**

### API基础URL配置错误 ⚠️ **问题所在**

**问题描述**：
在 `frontend/js/config.js` 中，`getApiBaseUrl()` 函数在开发环境下总是返回 `'http://localhost:5000'`，即使前端页面是通过IP地址访问的（如 `http://192.168.31.237:8000`）。

**具体表现**：
- 用户通过 `http://192.168.31.237:8000` 访问前端
- `Config.getApiBaseUrl()` 返回 `'http://localhost:5000'`
- 前端请求 `http://localhost:5000/api/screening/one-yang-three-lines`
- 如果后端运行在 `192.168.31.237:5000`，或用户不在服务器机器上，请求会失败（404或网络错误）

**后端路由状态**：✅ 正常
- 从后端启动日志确认：路由 `/api/screening/one-yang-three-lines` 已成功注册（日志第220行）
- 路由模块导入成功（日志第207行）
- 路由数量从108增加到117，说明路由已正确注册

**解决方案**：
已修复 `frontend/js/config.js` 中的 `getApiBaseUrl()` 函数，现在会：
- 如果通过IP地址访问（192.168.x.x, 10.x.x.x, 172.16-31.x.x），使用相同的IP地址
- 如果通过localhost访问，使用localhost

## 解决步骤

### 步骤1：检查后端启动日志

查看后端服务启动时的日志输出，确认：
- [ ] 是否有 `✅ stock_screening_routes 导入成功`
- [ ] 是否有 `[DEBUG] 选股路由注册完成`
- [ ] 是否有任何导入错误

### 步骤2：检查实际注册的路由

访问后端调试端点（如果可用）：
```
http://localhost:5000/debug/routes
```

或者检查后端日志中的路由列表。

### 步骤3：检查前端API配置

在浏览器控制台中检查：
```javascript
// 在screening.js中检查
console.log('API_BASE_URL:', ScreeningPage.API_BASE_URL);
```

### 步骤4：手动测试API端点

使用curl或Postman直接测试后端API：
```bash
curl http://localhost:5000/api/screening/one-yang-three-lines
```

如果返回404，说明路由确实没有注册。

## 修复方案 ✅ **已实施**

### 修复 `frontend/js/config.js`

**修改前**：
```javascript
getApiBaseUrl() {
    // ...
    case 'development':
    default:
        return 'http://localhost:5000';  // ❌ 总是返回localhost
}
```

**修改后**：
```javascript
getApiBaseUrl() {
    // ...
    case 'development':
    default:
        const hostname = window.location.hostname;
        const protocol = window.location.protocol;
        if (hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname.match(/^172\.(1[6-9]|2[0-9]|3[01])\./)) {
            // ✅ 如果是内网IP地址，使用相同的IP地址
            return `${protocol}//${hostname}:5000`;
        } else {
            // ✅ 否则使用localhost
            return 'http://localhost:5000';
        }
}
```

**修复效果**：
- 通过 `http://192.168.31.237:8000` 访问时，API请求会发送到 `http://192.168.31.237:5000`
- 通过 `http://localhost:8000` 访问时，API请求会发送到 `http://localhost:5000`

## 验证方法

修复后，应该能够：
1. 在前端页面加载选股结果，不再出现404错误
2. 在浏览器Network面板看到请求成功（200状态码）
3. 后端日志显示路由请求被正确处理

## 相关文件

- `frontend/js/screening.js` - 前端请求代码
- `backend_api/stock/stock_screening_routes.py` - 后端路由定义
- `backend_api/main.py` - 路由注册逻辑
