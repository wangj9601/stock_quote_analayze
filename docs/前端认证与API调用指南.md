# 前端认证与 API 调用指南

## 概述

本指南说明前端在**登录状态**与**API 调用**下的认证使用方式：

1. **API 调用与登录失效**：调用后台接口时如何判断并处理登录失效（如 401），以及如何正确使用带认证的请求函数。
2. **按钮功能权限**：页面级认证已实现，但页面内按钮触发的功能需要单独做授权检查；如何为按钮功能添加认证。

---

## 认证体系概览

### 1. 页面级认证

- 页面加载时自动检查登录状态
- 未登录用户自动跳转到登录页
- Token 失效后自动清除本地存储并跳转登录页

### 2. 全局认证工具

- **authFetch(url, options)**：带 token 的 fetch，自动添加 `Authorization` 头并处理 401
- **CommonUtils.auth.checkLogin()**：检查登录状态
- **CommonUtils.auth.getUserInfo()**：获取用户信息
- **CommonUtils.auth.logout()**：登出

### 3. 按钮级认证

- 需要认证的按钮在执行前应做登录检查，或使用 `CommonUtils.requireAuth` / `requireAuthAsync` 包装。

---

## API 调用与登录失效

### 1. authFetch — 带认证的 API 调用

```javascript
const response = await authFetch(`${API_BASE_URL}/api/watchlist`);
```

**特点**：

- 自动添加 `Authorization: Bearer ${token}` 头
- 检测 401 后自动处理登录失效（清除本地存储、跳转登录页）
- 适合所有需要认证的接口

### 2. smartFetch — 按需认证

```javascript
const response = await smartFetch(`${API_BASE_URL}/api/market/indices`);
```

**特点**：

- 根据 URL 判断是否需要认证
- 需要认证的端点内部使用 `authFetch`，公开端点使用普通 `fetch`

### 3. 需要认证的 API 端点（示例）

以下路径会按需使用认证（如通过 `smartFetch` 或直接使用 `authFetch`）：

```javascript
const authRequiredEndpoints = [
    '/api/watchlist',      // 自选股相关
    '/api/auth/',          // 认证相关
    '/api/analysis/',     // 分析相关
    '/api/stock/history',  // 历史行情
    '/api/trading_notes',  // 交易备注
    '/api/user/',         // 用户相关
    '/api/admin/'         // 管理相关
];
```

### 4. 登录失效处理流程（401）

当接口返回 401 时，典型处理逻辑如下（`authFetch` 已内置类似逻辑）：

```javascript
if (response.status === 401) {
    console.log('Token已失效，清除本地存储并跳转到登录页');
    localStorage.removeItem('access_token');
    localStorage.removeItem('userInfo');
    localStorage.removeItem('token');

    if (!window.location.pathname.includes('login.html') &&
        !window.location.pathname.includes('test-login.html')) {
        CommonUtils.showToast('登录已过期，请重新登录', 'error');
        setTimeout(() => {
            window.location.href = 'login.html';
        }, 1000);
    }
}
```

- 显示 Toast：“登录已过期，请重新登录”
- 清除本地认证信息并跳转登录页

---

## 按钮功能认证

### 方法一：手动检查登录（适合复杂逻辑）

```javascript
async function exportHistory() {
    const userInfo = CommonUtils.auth.getUserInfo();
    if (!userInfo || !userInfo.id) {
        CommonUtils.showToast('请先登录后再导出数据', 'warning');
        return;
    }

    try {
        const response = await authFetch(url);
        if (!response.ok) {
            if (response.status === 401) {
                CommonUtils.showToast('登录已过期，请重新登录', 'error');
                CommonUtils.auth.logout();
                return;
            }
            throw new Error(`操作失败: ${response.status}`);
        }
        // 处理响应...
    } catch (error) {
        console.error('操作失败:', error);
        alert('操作失败: ' + error.message);
    }
}
```

### 方法二：使用认证装饰器（适合简单功能）

```javascript
// 同步函数
const protectedFunction = CommonUtils.requireAuth(function() {
    console.log('用户已认证，执行功能');
});

// 异步函数
const protectedAsyncFunction = CommonUtils.requireAuthAsync(async function() {
    const response = await authFetch(url);
    return response.json();
});
```

---

## 已接入认证的 API 与功能

### 按 API 分类

- **股票详情页**：股票分析、实时行情、财务数据等（`/api/analysis/stock/`、`/api/stock/realtime_quote_by_code`、`/api/stock/latest_financial`）
- **历史行情页**：历史行情、涨跌幅计算、交易备注（`/api/stock/history`、`/api/stock/history/calculate_*_day_change`、`/api/trading_notes/*`）
- **自选股 / 分组**：`/api/watchlist/*`、`/api/watchlist/groups/*`

### 按按钮功能分类

- **历史行情页**：导出历史数据、计算 5/10/60 天涨跌幅
- **行情中心 / 股票详情**：添加到自选股、从自选股删除

---

## 使用建议

### 1. 需要认证的 API 统一用 authFetch

```javascript
// 推荐
const response = await authFetch(`${API_BASE_URL}/api/watchlist`);

// 不推荐：普通 fetch 需自行处理 401
const response = await fetch(`${API_BASE_URL}/api/watchlist`);
```

### 2. 不确定是否需认证时用 smartFetch

```javascript
const response = await smartFetch(`${API_BASE_URL}/api/market/indices`);
```

### 3. 错误处理示例

```javascript
try {
    const response = await authFetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    // 处理数据...
} catch (error) {
    console.error('API调用失败:', error);
    // 错误处理...
}
```

---

## 测试方法

### 测试登录失效

在浏览器控制台执行：

```javascript
CommonUtils.testApiLoginExpiry();
```

### 模拟登录失效

```javascript
localStorage.removeItem('access_token');
localStorage.removeItem('userInfo');
localStorage.removeItem('token');

const response = await authFetch(`${API_BASE_URL}/api/watchlist`);
// 应触发 401 处理：提示并跳转登录页
```

---

## 最佳实践

1. **统一请求方式**：需要认证的接口一律使用 `authFetch`，避免与裸 `fetch` 混用。
2. **按钮前检查**：需要登录才能执行的功能，先检查 `CommonUtils.auth.getUserInfo()` 或使用 `requireAuth` / `requireAuthAsync`。
3. **错误与提示**：用 try-catch 处理异常，用 `CommonUtils.showToast()` 做用户提示；依赖 `authFetch` 自动处理 401，无需在业务里重复写 401 逻辑。
4. **安全**：敏感操作和敏感 API 都必须带认证，不暴露未授权能力。

---

## 注意事项

1. **不要混用**：同一项目中需认证的请求应用 `authFetch`（或通过 `smartFetch` 间接使用），避免部分用 `fetch` 导致 401 未统一处理。
2. **始终检查响应**：使用 `response.ok` 或 `response.status` 做成功/失败分支。
3. **体验**：登录失效时提示清晰（如“登录已过期，请重新登录”）并跳转登录页。
4. **按钮权限**：所有依赖登录的按钮功能都应做认证检查或包装，并使用 `authFetch` 发请求。
