# 生产环境与 HTTPS 部署配置指南

本文档整合生产环境部署、HTTPS/SSL 配置、SSL 证书问题修复、代理配置及 Vite/TypeScript 配置修复的说明，便于统一查阅与实施。

---

## 一、生产环境部署

### 1.1 当前架构（示例）

- **前端访问**：`https://www.icemaplecity.com/admin` → 反向代理到 8001 端口
- **API 服务**：5000 端口
- **数据采集 API 路由**：`/data-collection`

### 1.2 常见问题：API 返回 404

生产环境请求 `https://www.icemaplecity.com/data-collection/...` 返回 404，多为反向代理未正确转发。

### 1.3 解决方案

**方案一：配置反向代理（推荐）**

在 Nginx（或其它反向代理）中增加 API 路由转发：

```nginx
location /data-collection {
    proxy_pass http://localhost:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api {
    proxy_pass http://localhost:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

**方案二：前端直连 API**

若无法改代理，可在生产环境让前端直连 API 地址（需注意 CORS、HTTPS）：

```typescript
production: {
  baseURL: 'https://www.icemaplecity.com',  // 或 API 专用域名
  timeout: 30000
}
```

**方案三：环境变量**

```bash
# .env.production
VITE_API_BASE_URL=https://www.icemaplecity.com
```

### 1.4 验证与注意

- 检查 API：`curl https://www.icemaplecity.com/data-collection/stock-list`
- 确保 CORS 允许前端域名；生产建议使用 HTTPS；做好日志与监控。

---

## 二、HTTPS 与 SSL 配置

### 2.1 配置要点

- **SSL 证书**：放置于统一目录（如 `tools/nginx/ssl/`），nginx 中配置 `ssl_certificate`、`ssl_certificate_key`。
- **HTTP 重定向**：80 端口 `return 301 https://$server_name$request_uri;`。
- **HTTPS 服务器块**：监听 443，启用 `ssl`、可选 `http2`；配置安全头（HSTS、X-Frame-Options、X-Content-Type-Options、X-XSS-Protection）。

### 2.2 证书文件位置（示例）

```
tools/nginx/ssl/
├── www.icemaplecity.com-chain.pem    # 完整证书链（nginx 使用）
├── www.icemaplecity.com-key.pem      # 私钥
└── ...
```

### 2.3 SSL/TLS 与安全头

- **协议**：TLS 1.2、TLS 1.3。
- **加密套件**：ECDHE-RSA-AES128-GCM-SHA256、ECDHE-RSA-AES256-GCM-SHA384 等。
- **会话缓存**：如 `ssl_session_cache shared:SSL:1m;`、`ssl_session_timeout 5m;`。
- **安全头**：HSTS（max-age=31536000）、X-Frame-Options DENY、X-Content-Type-Options nosniff、X-XSS-Protection。

### 2.4 访问地址（示例）

- **HTTPS**：https://www.icemaplecity.com
- **前端**：https://www.icemaplecity.com/
- **API**：https://www.icemaplecity.com/api/
- **管理后台**：https://www.icemaplecity.com/admin/
- **健康检查**：https://www.icemaplecity.com/health

### 2.5 证书管理（Let's Encrypt）

- **有效期**：90 天，需定期续期。
- **自动续期**（示例）：

```bash
# 续期后重载 nginx
certbot renew --quiet && nginx -s reload
```

可将上述命令放入计划任务（如 Windows 任务计划程序每 60 天执行）。

---

## 三、SSL 证书生成失败与修复

### 3.1 典型问题

- **现象**：ACME http-01 验证失败，返回 **HTTP 403 Forbidden**。
- **原因**：ACME 挑战路径 `/.well-known/acme-challenge/` 配置错误或不可访问（路径、权限、隐藏文件规则）。

### 3.2 修复步骤

**1. 创建目录**

```bash
mkdir -p tools/nginx-1.28.0/html/.well-known/acme-challenge
```

（路径按实际 nginx 安装与 root 配置调整。）

**2. Nginx 配置**

- 使用 `root html;`（相对 nginx 安装目录）或正确绝对路径。
- 单独配置 ACME 路径，并允许 `.well-known` 被访问：

```nginx
location /.well-known/acme-challenge/ {
    root html;
    try_files $uri =404;
    access_log logs/acme_access.log;
    error_log logs/acme_error.log debug;
}

# 禁止其他隐藏文件，但允许 .well-known
location ~ /\.(?!well-known) {
    deny all;
}
```

**3. 测试 ACME 路径**

```bash
echo "test" > tools/nginx-1.28.0/html/.well-known/acme-challenge/test.txt
curl http://www.icemaplecity.com/.well-known/acme-challenge/test.txt
```

**4. 申请/续期证书**

```bash
certbot certonly --webroot -w C:/work/stock_quote_analayze/tools/nginx-1.28.0/html -d www.icemaplecity.com -d icemaplecity.com
```

（-w 路径与 nginx `root` 对应。）

### 3.3 常见排查

- **403**：检查 root、try_files、隐藏文件规则；确认 nginx 进程有读权限。
- **验证失败**：确认 80 端口对外可访问；DNS 已解析到本机；防火墙放行 80。

---

## 四、代理配置（数据采集等）

### 4.1 在配置文件中配置代理池

编辑 `backend_core/config/config.py`（或等价配置）：

```python
'akshare': {
    'max_retries': 3,
    'retry_delay': 5,
    'timeout': 30,
    'proxy_pool': [
        {'http': 'http://proxy1.example.com:8080', 'https': 'https://proxy1.example.com:8080'},
        {'http': 'http://proxy2.example.com:8080', 'https': 'https://proxy2.example.com:8080'},
    ],
    'random_delay_range': (1, 3),
    'ssl_verify': False,
    'use_fallback_sources': True,
}
```

支持 HTTP 代理与 SOCKS（如 `socks5://...`）；若需认证，在 URL 中加入 `username:password@`。

### 4.2 环境变量

```bash
# Linux/Mac
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=https://proxy.example.com:8080

# Windows (PowerShell)
$env:HTTP_PROXY = "http://proxy.example.com:8080"
$env:HTTPS_PROXY = "https://proxy.example.com:8080"
```

代码中可从 `os.getenv('HTTP_PROXY')`、`os.getenv('HTTPS_PROXY')` 读取并填入请求。

### 4.3 动态代理配置（JSON）

可维护 `proxy_config.json`，包含 `proxies` 列表及 `enabled`、`rotation_interval` 等，在应用启动时加载并注入到采集器配置。实现细节见原《代理服务器配置指南》。

### 4.4 代理验证与轮换

- 使用 `requests` 通过代理访问固定 URL（如 https://httpbin.org/ip）验证可用性。
- 轮换：简单轮询或按成功率选择代理，避免单代理过载或封禁。

### 4.5 注意事项

- 免费代理稳定性差，生产建议付费代理；使用代理需符合当地法律法规；注意认证与协议类型（HTTP/SOCKS）。

---

## 五、Vite / TypeScript 配置修复（管理端）

### 5.1 问题

在 `admin/vite.config.ts` 中报错：  
`Cannot find module '@vitejs/plugin-vue' or its corresponding type declarations.`

### 5.2 原因

依赖已安装，但 TypeScript 解析 vite 配置时缺少合适类型或 `tsconfig.node.json` 未包含该上下文。

### 5.3 解决方案

修改 `admin/tsconfig.node.json`，确保包含 vite 配置且具备 Node 类型与模块解析：

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "lib": ["ES2020"],
    "target": "ES2020",
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["vite.config.ts"],
  "exclude": ["node_modules", "dist"],
  "types": ["node"]
}
```

关键点：`include` 含 `vite.config.ts`，`exclude` 排除 `node_modules` 与 `dist`，`types` 含 `node`。

### 5.4 验证

- 执行 `npm run build`，类型检查与 Vite 构建应通过。
- 若仍有类型报错，可升级 `vue-tsc`、`@vitejs/plugin-vue` 到与当前 Node/Vite 兼容的版本。

---

## 六、验证与故障排除

### 6.1 HTTPS 与证书

```bash
nginx -t
nginx -s reload
curl -I https://www.icemaplecity.com
curl -I http://www.icemaplecity.com   # 应 301 到 HTTPS
```

### 6.2 证书与 ACME

- 查看证书：`certbot certificates`
- 测试挑战路径：`curl http://www.icemaplecity.com/.well-known/acme-challenge/test.txt`
- 查看 nginx 错误日志：`logs/error.log`、`logs/acme_error.log`

### 6.3 生产 API 与代理

- 检查后端与端口：`netstat -an | findstr "5000 8001"`
- 检查代理：在采集器中用代理请求已知 URL，确认可连通。

### 6.4 常见问题速查

| 现象 | 检查项 |
|------|--------|
| API 404 | 反向代理是否转发 /api、/data-collection 到 5000 |
| SSL 启动失败 | 证书路径、权限、端口 443 占用 |
| ACME 403 | root、.well-known、try_files、隐藏文件规则 |
| CORS 报错 | 后端 CORS 是否允许前端域名与请求方法/头 |
| Vite 类型错误 | tsconfig.node.json、include/exclude、types |

---

## 七、备份与监控建议

- **备份**：定期备份 nginx 配置、SSL 证书目录、代理与前端环境变量。
- **监控**：证书过期时间、nginx 错误日志、HTTPS 可用性、API 与数据采集成功率。

---

## 八、相关文件索引

| 说明 | 路径（示例） |
|------|----------------|
| Nginx 配置 | 见《Nginx配置与修复指南》或项目内 nginx 配置 |
| 采集/代理配置 | backend_core/config/config.py |
| 管理端 Vite | admin/vite.config.ts |
| 管理端 TS Node 配置 | admin/tsconfig.node.json |
| 证书目录 | tools/nginx/ssl/ |
| ACME 根目录 | tools/nginx-1.28.0/html（或当前 nginx root） |

---

本文档由以下原文档整合而成：HTTPS 配置完成总结、代理服务器配置指南、生产环境部署配置、SSL 证书生成失败修复指南、SSL 证书生成失败问题总结、Vite Config TypeScript 错误修复总结。
