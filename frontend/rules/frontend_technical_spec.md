# 股票分析系统前端技术规范

## 目录
1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [开发规范](#开发规范)
5. [JavaScript规范](#javascript规范)
6. [HTML规范](#html规范)
7. [CSS规范](#css规范)
8. [性能优化](#性能优化)
9. [测试规范](#测试规范)
10. [部署规范](#部署规范)

## 项目概述

股票分析系统前端是系统的用户界面层，采用传统的多页面应用（MPA）架构，使用原生HTML、JavaScript和CSS构建，提供股票数据的展示、分析和交互功能。项目采用模块化的开发方式，确保代码的可维护性和可扩展性。

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
frontend/
├── js/                # JavaScript文件目录
│   ├── common.js     # 公共函数和工具
│   ├── login.js      # 登录相关功能
│   ├── home.js       # 首页相关功能
│   ├── stock.js      # 股票相关功能
│   ├── markets.js    # 市场相关功能
│   ├── analysis.js   # 分析相关功能
│   ├── news.js       # 新闻相关功能
│   ├── profile.js    # 用户资料相关功能
│   └── watchlist.js  # 自选股相关功能
├── css/              # CSS样式文件目录
│   ├── common.css    # 公共样式
│   └── *.css         # 各页面样式
├── index.html        # 首页
├── login.html        # 登录页
├── stock.html        # 股票详情页
├── markets.html      # 市场行情页
├── analysis.html     # 股票分析页
├── news.html         # 新闻资讯页
├── profile.html      # 用户资料页
├── watchlist.html    # 自选股页面
└── rules/            # 技术规范文档
```

## 开发规范

### 1. 文件命名规范
- **HTML文件**: 小写字母，中划线分隔
  ```
  stock-detail.html
  market-index.html
  ```
- **JavaScript文件**: 小写字母，中划线分隔
  ```
  stock-detail.js
  market-index.js
  ```
- **CSS文件**: 小写字母，中划线分隔
  ```
  stock-detail.css
  market-index.css
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
  const stockList = [];
  let currentPrice = 0;
  ```
- **函数名**: 小驼峰命名
  ```javascript
  function getStockData() {}
  function updateUserProfile() {}
  ```
- **常量**: 大写字母，下划线分隔
  ```javascript
  const API_BASE_URL = 'http://localhost:5000';
  const MAX_RETRY_COUNT = 3;
  ```
- **类名**: 大驼峰命名
  ```javascript
  class StockChart {}
  class UserManager {}
  ```

### 3. 注释规范
- 文件头部添加功能说明
- 函数必须包含参数和返回值说明
- 复杂逻辑必须添加注释
```javascript
/**
 * 获取股票数据
 * @param {string} code - 股票代码
 * @param {string} period - 时间周期
 * @returns {Promise<Object>} 股票数据
 */
async function getStockData(code, period) {
  // 实现代码
}
```

### 4. 模块化规范
- 使用ES6模块化
- 按功能划分模块
- 避免全局变量污染
```javascript
// 模块导出
export function getStockData() {}
export class StockChart {}

// 模块导入
import { getStockData } from './stock-api.js';
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
    <title>股票分析系统</title>
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
            <li><a href="/">首页</a></li>
        </ul>
    </nav>
</header>
<main>
    <article>
        <!-- 主要内容 -->
    </article>
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
    --text-color: #333;
    --border-color: #ddd;
}
```

### 2. 命名规范
- 使用BEM命名方法
- 类名使用小写字母和中划线
```css
.stock-list {}
.stock-list__item {}
.stock-list__item--active {}
```

### 3. 响应式设计
- 使用媒体查询
- 移动优先设计
- 弹性布局
```css
@media screen and (max-width: 768px) {
    .container {
        padding: 10px;
    }
}
```

## 性能优化

### 1. 加载优化
- 资源压缩
- 图片优化
- 按需加载
- 缓存策略

### 2. 渲染优化
- 避免重排重绘
- 使用CSS动画
- 延迟加载
- 虚拟滚动

### 3. 代码优化
- 代码压缩
- 去除注释
- 合并文件
- 按需加载

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

## 更新日志

### v1.0.0 (2024-01-20)
- 初始版本发布
- 实现基础功能
- 完成技术规范文档

## 维护说明

本文档由前端开发团队维护，如有问题或建议，请提交Issue或联系开发团队。

## 参考资源

- [MDN Web文档](https://developer.mozilla.org/)
- [JavaScript标准参考教程](https://javascript.ruanyifeng.com/)
- [CSS参考手册](https://www.w3school.com.cn/css/)
- [HTML5参考手册](https://www.w3school.com.cn/html5/) 
- [ECharts文档](https://echarts.apache.org/) 