# Nginx 配置与修复指南

本文档整合 Nginx 配置修复说明、错误排查、管理端刷新 404 修复，以及 HTTP/HTTPS、Windows/Linux、SSL 与 ACME 等配置示例，便于统一查阅与部署。

---

## 一、常见问题与原因

### 1.1 错误日志示例

```
no live upstreams while connecting to upstream,
server: erp.icemaplecity.com,
request: "GET /favicon.ico HTTP/1.1", upstream: "http://localhost/favicon.ico",
host: "www.icemaplecity.com"
```

### 1.2 原因归纳

| 现象 | 可能原因 |
|------|----------|
| no live upstreams | 未定义 upstream 或直接写 `http://localhost:5000/` 等，未使用 upstream 名 |
| favicon.ico 404 | 未单独配置 favicon 或静态资源，被错误代理到 upstream |
| 管理端刷新 404 | Vue Router history 模式，子路径刷新时 Nginx 未做 SPA fallback，直接 404 |
| 域名混乱 | server_name 含错误域名（如 erp.icemaplecity.com）或与请求 Host 不一致 |
| CORS 报错 | /api/ 未处理 OPTIONS 或未加 CORS 响应头 |

---

## 二、核心修复要点

### 2.1 定义 upstream

```nginx
upstream backend_api {
    server 127.0.0.1:5000;
}

upstream frontend_server {
    server 127.0.0.1:8000;
}

upstream admin_server {
    server 127.0.0.1:8001;
}
```

所有 `proxy_pass` 应使用上述名称（如 `http://backend_api`），不要写 `http://localhost:5000/`。

### 2.2 域名与 server_name

```nginx
server {
    listen 80;
    server_name www.icemaplecity.com icemaplecity.com;  # 与对外域名一致，移除错误域名
    # ...
}
```

### 2.3 API 代理与 CORS

```nginx
location /api/ {
    proxy_pass http://backend_api;   # 或 http://backend_api/ 视是否保留 /api/ 路径
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Max-Age' 1728000 always;
        add_header 'Content-Type' 'text/plain; charset=utf-8' always;
        add_header 'Content-Length' 0 always;
        return 204;
    }
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
}
```

### 2.4 管理端 SPA fallback（解决刷新 404）

管理端使用 Vue Router history 且部署在 `/admin/` 时，需对 404 做 fallback 到 `index.html`：

```nginx
location /admin/ {
    proxy_pass http://admin_server/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    proxy_intercept_errors on;
    error_page 404 = @admin_fallback;

    access_log logs/admin_access.log;
    error_log logs/admin_error.log;
}

location @admin_fallback {
    proxy_pass http://admin_server/index.html;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

管理端静态资源建议单独 location，并做长期缓存：

```nginx
location ~ ^/admin/assets/ {
    proxy_pass http://admin_server;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location = /admin/favicon.ico {
    proxy_pass http://admin_server/favicon.ico;
    proxy_set_header Host $host;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 2.5 前端 SPA fallback（可选）

若前端也是 history 模式且根路径 `/`：

```nginx
location / {
    proxy_pass http://frontend_server/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_intercept_errors on;
    error_page 404 = @frontend_fallback;
}

location @frontend_fallback {
    proxy_pass http://frontend_server/index.html;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 2.6 favicon 与静态资源

- 若前端/管理端由后端服务提供静态文件（如 8000/8001），可用 `proxy_pass` 到对应 upstream，并加 `expires` / `Cache-Control`。
- 若使用本地 root：`location = /favicon.ico { root /path/to/frontend; try_files /favicon.ico =404; }`，路径按实际替换。

### 2.7 隐藏文件与 ACME

禁止除 `.well-known` 外的隐藏文件：

```nginx
location ~ /\.(?!well-known) {
    deny all;
    access_log off;
    log_not_found off;
}

location /.well-known/acme-challenge/ {
    root html;
    try_files $uri =404;
    access_log logs/acme_access.log;
    error_log logs/acme_error.log debug;
}
```

### 2.8 HTTPS 与 SSL（生产示例）

- HTTP 80 重定向到 HTTPS：`return 301 https://$server_name$request_uri;`
- 443 使用 `ssl_certificate` / `ssl_certificate_key`，并设置 `ssl_session_cache`、`ssl_ciphers`、`ssl_prefer_server_ciphers`。
- Windows 上证书路径使用正斜杠，例如：`C:/work/stock_quote_analayze/tools/nginx/ssl/www.icemaplecity.com-chain.pem`。

---

## 三、配置模板说明

项目曾提供多份参考配置，对应关系如下，可按需选用或合并：

| 用途 | 原文件名 | 说明 |
|------|----------|------|
| HTTP 版（Linux/通用） | nginx_final_fix.conf | 80 端口，upstream + /api/ + /admin/ + /，CORS，无 fallback |
| HTTP 版（Windows） | nginx_final_fix_windows.conf | 与上结构相同，路径按 Windows 调整 |
| HTTP + ACME | nginx_ssl_fix.conf | 增加 /.well-known/acme-challenge/，禁止隐藏文件时保留 .well-known |
| HTTPS + 管理端刷新修复 | nginx_admin_fix.conf | 80→301 HTTPS，443 全站 + 管理端 fallback + /admin/assets/ + 前端 fallback + SSL 证书路径（Windows） |

生产环境推荐：**HTTPS + 管理端 fallback**（以 nginx_admin_fix.conf 为底），再按需改域名与证书路径。

---

## 四、完整示例：HTTPS + 管理端 fallback（Windows 证书路径）

以下为基于 `nginx_admin_fix.conf` 的完整 server 块示例，可直接放入 `http { }` 内使用；证书路径请按本机修改。

```nginx
# HTTP 重定向到 HTTPS
server {
    listen       80;
    server_name  www.icemaplecity.com icemaplecity.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS
server {
    listen       443 ssl http2;
    server_name  www.icemaplecity.com icemaplecity.com;

    ssl_certificate      C:/work/stock_quote_analayze/tools/nginx/ssl/www.icemaplecity.com-chain.pem;
    ssl_certificate_key  C:/work/stock_quote_analayze/tools/nginx/ssl/www.icemaplecity.com-key.pem;
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;
    ssl_ciphers  ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers  on;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    upstream backend_api { server 127.0.0.1:5000; }
    upstream frontend_server { server 127.0.0.1:8000; }
    upstream admin_server { server 127.0.0.1:8001; }

    location /api/ {
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
            add_header 'Access-Control-Max-Age' 1728000 always;
            add_header 'Content-Type' 'text/plain; charset=utf-8' always;
            add_header 'Content-Length' 0 always;
            return 204;
        }
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
    }

    location ~ ^/admin/assets/ {
        proxy_pass http://admin_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location = /admin/favicon.ico {
        proxy_pass http://admin_server/favicon.ico;
        proxy_set_header Host $host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /admin/ {
        proxy_pass http://admin_server/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_intercept_errors on;
        error_page 404 = @admin_fallback;
        access_log logs/admin_access.log;
        error_log logs/admin_error.log;
    }

    location @admin_fallback {
        proxy_pass http://admin_server/index.html;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~ ^/assets/ {
        proxy_pass http://frontend_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location = /favicon.ico {
        proxy_pass http://frontend_server/favicon.ico;
        proxy_set_header Host $host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://frontend_server/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_intercept_errors on;
        error_page 404 = @frontend_fallback;
    }

    location @frontend_fallback {
        proxy_pass http://frontend_server/index.html;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location ~ /\.(?!well-known) {
        deny all;
        access_log off;
        log_not_found off;
    }

    location /.well-known/acme-challenge/ {
        root html;
        try_files $uri =404;
        access_log logs/acme_access.log;
        error_log logs/acme_error.log debug;
    }
}
```

---

## 五、实施步骤

### 5.1 备份

```bash
# Linux
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# Windows
copy C:\nginx\conf\nginx.conf C:\nginx\conf\nginx.conf.backup
```

### 5.2 替换或合并配置

- 将上述 server 块合并进现有 `nginx.conf` 的 `http { }`，或替换对应 include 中的站点配置。
- 修改 `server_name`、SSL 证书路径、upstream 端口（若非 5000/8000/8001）。

### 5.3 测试与重载

```bash
# Linux
sudo nginx -t
sudo nginx -s reload   # 或 systemctl reload nginx

# Windows
cd C:\nginx
nginx.exe -t
nginx.exe -s reload
```

### 5.4 验证

- 确认后端 5000、前端 8000、管理端 8001 已启动：`netstat -an | findstr "5000 8000 8001"`（Windows）或 `netstat -tulpn | grep -E '5000|8000|8001'`（Linux）。
- 访问：`https://www.icemaplecity.com/admin/login`，刷新页面应不再 404。
- 检查：`/favicon.ico`、`/api/`、`/health` 返回正常；错误日志无 `no live upstreams`。

---

## 六、故障排查

| 现象 | 检查项 |
|------|--------|
| no live upstreams | 是否用 upstream 名做 proxy_pass；后端 5000/8000/8001 是否监听 |
| 管理端刷新 404 | 是否配置了 `error_page 404 = @admin_fallback` 与 `@admin_fallback` |
| favicon/静态 404 | /admin/assets/、/admin/favicon.ico、/assets/ 是否单独 location 并正确 proxy_pass |
| CORS 报错 | /api/ 下 OPTIONS 与 CORS 头是否按第二节配置 |
| 证书错误 | 路径是否正确（Windows 用 `/`）；证书是否过期；443 是否监听 |

---

## 七、前端与 Vite 配置确认

- **Vue Router**：生产 base 应为 `/admin/`，例如 `createWebHistory(process.env.NODE_ENV === 'production' ? '/admin/' : '/')`。
- **Vite**：`vite.config.ts` 中 `base: process.env.NODE_ENV === 'production' ? '/admin/' : '/'`。

与 Nginx 的 `location /admin/` 及 fallback 配合，才能保证刷新不 404。

---

本文档由以下原文件整合而成：nginx_admin_fix.conf、NGINX_CONFIG_FIX_GUIDE.md、NGINX_ERROR_FIX_GUIDE.md、nginx_final_fix_windows.conf、nginx_final_fix.conf、nginx_ssl_fix.conf。原 .conf 文件已不再单独保留，统一以本指南为准。
