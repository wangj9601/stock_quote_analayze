# 股票分析系统管理后台技术规范

## 目录
1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [开发规范](#开发规范)
5. [JavaScript规范](#javascript规范)
6. [HTML规范](#html规范)
7. [CSS规范](#css规范)
8. [功能规范](#功能规范)
9. [安全规范](#安全规范)
10. [测试规范](#测试规范)
11. [部署规范](#部署规范)

## 项目概述

股票分析系统管理后台是系统的管理控制层，采用传统的多页面应用（MPA）架构，使用原生HTML、JavaScript和CSS构建，提供完整的系统管理功能，包括用户管理、数据管理、系统配置等。管理后台采用严格的权限控制，确保系统安全性和可维护性。

## 技术栈

### 核心技术
- **前端语言**: HTML5 + JavaScript (ES6+) + CSS3
- **HTTP客户端**: Fetch API
- **图表库**: ECharts
- **UI组件**: 自定义组件
- **数据存储**: LocalStorage/SessionStorage

### 开发工具
- **编辑器**: VSCode
- **版本控制**: Git
- **浏览器工具**: Chrome DevTools
- **文档工具**: Markdown

## 项目结构

```
admin/
├── js/                # JavaScript文件目录
│   ├── admin.js      # 主要管理功能
│   └── admin_fixed.js # 修复版本管理功能
├── css/              # CSS样式文件目录
│   ├── common.css    # 公共样式
│   └── admin.css     # 管理后台样式
├── index.html        # 管理后台主页
└── rules/            # 技术规范文档
```

## 开发规范

### 1. 文件命名规范
- **HTML文件**: 小写字母，中划线分隔
  ```
  admin-dashboard.html
  user-management.html
  ```
- **JavaScript文件**: 小写字母，中划线分隔
  ```
  admin-dashboard.js
  user-management.js
  ```
- **CSS文件**: 小写字母，中划线分隔
  ```
  admin-dashboard.css
  user-management.css
  ```

### 2. 目录组织规范
- 按功能模块组织文件
- 公共资源集中管理
- 保持目录结构清晰
- 避免过深的目录嵌套

## JavaScript规范

### 1. 代码风格
- 使用2个空格缩进
- 使用单引号
- 行末使用分号
- 使用UTF-8编码
- 每行代码不超过120字符

### 2. 命名规范
- **变量名**: 小驼峰命名
  ```javascript
  const userList = [];
  let currentUser = null;
  ```
- **函数名**: 小驼峰命名
  ```javascript
  function getUserList() {}
  function updateUserStatus() {}
  ```
- **常量**: 大写字母，下划线分隔
  ```javascript
  const API_BASE_URL = 'http://localhost:5000';
  const ADMIN_ROLE = 'admin';
  ```
- **类名**: 大驼峰命名
  ```javascript
  class UserManager {}
  class SystemConfig {}
  ```

### 3. 注释规范
- 文件头部添加功能说明
- 函数必须包含参数和返回值说明
- 复杂逻辑必须添加注释
```javascript
/**
 * 获取用户列表
 * @param {Object} params - 查询参数
 * @param {number} params.page - 页码
 * @param {number} params.pageSize - 每页数量
 * @returns {Promise<Object>} 用户列表和分页信息
 */
async function getUserList(params) {
  // 实现代码
}
```

### 4. 模块化规范
- 使用ES6模块化
- 按功能划分模块
- 避免全局变量污染
```javascript
// 模块导出
export function getUserList() {}
export class UserManager {}

// 模块导入
import { getUserList } from './user-api.js';
```

## HTML规范

### 1. 文档结构
- 使用HTML5文档类型
- 包含必要的meta标签
- 合理的语义化标签使用
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票分析系统管理后台</title>
</head>
<body>
    <!-- 页面内容 -->
</body>
</html>
```

### 2. 标签使用
- 使用语义化标签
- 保持标签嵌套合理
- 属性使用双引号
```html
<header>
    <nav>
        <ul>
            <li><a href="/admin">管理首页</a></li>
        </ul>
    </nav>
</header>
<main>
    <section>
        <!-- 主要内容 -->
    </section>
</main>
<footer>
    <!-- 页脚内容 -->
</footer>
```

## CSS规范

### 1. 样式组织
- 使用外部样式表
- 按功能模块组织样式
- 使用CSS变量管理主题
```css
:root {
    --primary-color: #1890ff;
    --danger-color: #ff4d4f;
    --success-color: #52c41a;
    --text-color: #333;
    --border-color: #ddd;
}
```

### 2. 命名规范
- 使用BEM命名方法
- 类名使用小写字母和中划线
```css
.admin-header {}
.admin-header__nav {}
.admin-header__nav-item--active {}
```

### 3. 响应式设计
- 使用媒体查询
- 移动优先设计
- 弹性布局
```css
@media screen and (max-width: 768px) {
    .admin-container {
        padding: 10px;
    }
}
```

## 功能规范

### 1. 用户管理
- 用户列表展示
- 用户信息编辑
- 用户状态管理
- 用户权限分配
- 用户操作日志

### 2. 股票管理
- 股票数据管理
- 股票分类管理
- 股票数据导入导出
- 股票数据更新
- 股票数据统计

### 3. 系统管理
- 系统配置管理
- 角色权限管理
- 操作日志管理
- 系统监控
- 数据备份恢复

### 4. 权限控制
```javascript
// 权限检查
function checkPermission(permission) {
    const userRole = localStorage.getItem('userRole');
    return userRole === 'admin' || userRole === permission;
}

// 权限使用
if (checkPermission('admin')) {
    // 执行管理操作
}
```

## 安全规范

### 1. 认证安全
- 登录认证
- Token管理
- 密码加密
- 会话管理
- 登录限制

### 2. 权限安全
- 角色权限
- 操作权限
- 数据权限
- 接口权限
- 按钮权限

### 3. 数据安全
- 数据加密
- 数据备份
- 数据恢复
- 敏感信息保护
- 操作日志

## 测试规范

### 1. 测试要求
- 功能测试
- 兼容性测试
- 性能测试
- 安全测试

### 2. 浏览器兼容
- Chrome (最新版)
- Firefox (最新版)
- Edge (最新版)
- Safari (最新版)

## 部署规范

### 1. 文件组织
- 静态资源压缩
- 文件版本控制
- 目录结构清晰
- 备份策略

### 2. 部署步骤
1. 代码检查
2. 资源压缩
3. 文件上传
4. 功能验证

### 3. 监控要求
- 错误监控
- 性能监控
- 用户行为监控
- 接口监控
- 安全监控

## 更新日志

### v1.0.0 (2024-01-20)
- 初始版本发布
- 实现基础功能
- 完成技术规范文档

## 维护说明

本文档由管理后台开发团队维护，如有问题或建议，请提交Issue或联系开发团队。

## 参考资源

- [MDN Web文档](https://developer.mozilla.org/)
- [JavaScript标准参考教程](https://javascript.ruanyifeng.com/)
- [CSS参考手册](https://www.w3school.com.cn/css/)
- [HTML5参考手册](https://www.w3school.com.cn/html5/)
- [ECharts文档](https://echarts.apache.org/) 