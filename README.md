[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/wangj9601/stock_quote_analayze)
# 股票分析系统管理后台 - 现代化版本

基于 Vue 3 + TypeScript + Vite + Element Plus 构建的现代化管理后台系统。

## 🚀 技术栈

- **前端框架**: Vue 3 (Composition API)
- **开发语言**: TypeScript
- **构建工具**: Vite
- **UI 组件库**: Element Plus
- **状态管理**: Pinia
- **路由管理**: Vue Router 4
- **样式框架**: Tailwind CSS
- **HTTP 客户端**: Axios
- **日期处理**: Day.js

## 📁 项目结构

```
admin-modern/
├── src/
│   ├── assets/          # 静态资源
│   │   └── styles/      # 样式文件
│   ├── components/      # 组件
│   │   ├── common/      # 通用组件
│   │   ├── logs/        # 日志相关组件
│   │   ├── users/       # 用户相关组件
│   │   └── quotes/      # 行情相关组件
│   ├── views/           # 页面组件
│   ├── stores/          # 状态管理
│   ├── services/        # API 服务
│   ├── types/           # TypeScript 类型定义
│   ├── utils/           # 工具函数
│   └── router/          # 路由配置
├── public/              # 公共资源
├── package.json         # 项目配置
├── vite.config.ts       # Vite 配置
├── tsconfig.json        # TypeScript 配置
├── tailwind.config.js   # Tailwind CSS 配置
└── README.md           # 项目说明
```

## 🛠️ 开发环境

### 环境要求

- Node.js >= 16.0.0
- npm >= 8.0.0

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## 🔧 功能特性

### ✅ 已完成功能

- **用户认证**: 登录/登出功能
- **系统日志**: 完整的日志查看、筛选、导出功能
- **仪表板**: 系统概览和快速操作
- **响应式设计**: 适配不同屏幕尺寸
- **现代化UI**: 基于 Element Plus 的美观界面

### 🚧 开发中功能

- 用户管理
- 行情数据管理
- 数据源配置
- 数据采集管理
- 系统监控
- 预测模型
- 内容管理
- 公告发布

## 🔌 API 接口

系统使用 RESTful API 与后端通信，主要接口包括：

- `POST /api/admin/auth/login` - 用户登录
- `GET /api/admin/logs/query/historical_collect` - 获取历史采集日志
- `GET /api/admin/operation-logs/query` - 获取操作日志
- `GET /api/admin/logs/stats` - 获取日志统计
- `GET /api/admin/logs/export` - 导出日志

## 🎨 设计规范

### 颜色系统

- **主色调**: 蓝色系 (#3B82F6)
- **成功色**: 绿色系 (#10B981)
- **警告色**: 黄色系 (#F59E0B)
- **错误色**: 红色系 (#EF4444)
- **信息色**: 灰色系 (#6B7280)

### 组件规范

- 使用 Element Plus 组件库
- 结合 Tailwind CSS 进行样式定制
- 遵循 Vue 3 Composition API 最佳实践
- 使用 TypeScript 进行类型安全开发

## 📝 开发规范

### 代码规范

- 使用 ESLint + Prettier 进行代码格式化
- 遵循 Vue 3 官方风格指南
- 使用 TypeScript 严格模式
- 组件命名采用 PascalCase
- 文件命名采用 kebab-case

### Git 提交规范

- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具的变动

## 🚀 部署

### 开发环境

1. 确保后端API服务运行在 `http://localhost:5000`
2. 复制 `env.example` 为 `.env` 并配置环境变量
3. 运行 `npm run dev` 启动开发服务器

### 生产环境

1. 运行 `npm run build` 构建生产版本
2. 将 `dist` 目录部署到 Web 服务器
3. 配置反向代理将 `/api` 请求转发到后端服务

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 项目 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 邮箱: your-email@example.com

---

**股票分析系统管理后台** - 让数据管理更简单、更高效！ 
