# GMS 选股「全部 A 股」生产环境 502 说明

## 现象

- 前端：选股 → GMS 策略 → 范围选「全部 A 股」时，浏览器报 **502**，提示「服务暂时不可用」。
- 选「港股」或「自选股」正常；本地环境三种范围往往都正常。

## 原因说明

「全部 A 股」股票池约 **6000+** 只，GMS 需在单次请求内完成大量指标读取与策略计算（即使后端已按批处理），**整体耗时常达数分钟**。

生产环境前面通常有 **Nginx / 云负载均衡 / API 网关**，若 **`proxy_read_timeout`（或等价读超时）默认约 60 秒**，会在 **应用尚未返回 JSON 前** 断开连接，网关向浏览器返回 **502 Bad Gateway**。  

这与应用本身是否报错无关：本地无网关或超时较大时不易复现。

后端已对 `/api/screening/gms-strategy` 使用 `asyncio.wait_for`，默认 **`GMS_SCREENING_TIMEOUT=600` 秒**（可通过环境变量调整）。**网关超时必须 ≥ 该值**，否则仍会出现 502。

## 运维处理（推荐）

在反向代理上为 **GMS 选股接口单独加长读超时**。仓库示例已写入 **`docs/prod/nginx.conf`**（历史副本见 `docs/prod/nginx.legacy.conf`）：请使用 **`location ^~ /api/screening/gms-strategy`**（**`^~` 很重要**），否则请求仍会命中通用 **`location /api/`** 里的 **`proxy_read_timeout 30s`**，改「别处」无效。

```nginx
location ^~ /api/screening/gms-strategy {
    proxy_pass http://backend_api;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_connect_timeout 60s;
    proxy_buffering off;
}
```

改完后执行 **`nginx -t`**，再 **`nginx -s reload`**。用 **`nginx -T 2>/dev/null | grep -E "gms-strategy|proxy_read_timeout"`** 确认线上生效片段为 **600s**。

### 改完仍 502 时请排查

1. **实际未加载你改的配置**（多份 conf、另一台机、未 reload）。
2. **Cloudflare 等 CDN**：免费版源站请求常见 **约 100 秒**上限，全 A 股仍可能断 → 对该域名关闭代理（DNS 仅解析）或换规则后重试。
3. **Gunicorn `--timeout`** 若小于计算时间，worker 会被杀 → 502。
4. **后端崩溃 / OOM**：看 Nginx `error.log` 与系统日志。

### Gunicorn 的 `--timeout` 改哪里？

- **本仓库默认启动脚本 `start_backend_api.py` 使用的是 `uvicorn` 子进程**，**没有** Gunicorn，因此**没有** `--timeout` 这一项可改（长请求主要受 **Nginx** 与后端 `GMS_SCREENING_TIMEOUT` 限制）。
- 若生产环境**自行用 Gunicorn** 托管（如 `systemd` 的 `ExecStart`、`Supervisor` 的 `command`、Docker 的 `CMD`、或自建 shell），在 **`gunicorn` 命令行**中增加或调大：  
  `--timeout 600`（或与 `GMS_SCREENING_TIMEOUT` 一致）。  
  仓库里仅在 **`deploy.py` 文档示例**中有示例命令，可按上式修改你服务器上的真实启动命令。

## 应用配置

- 环境变量 **`GMS_SCREENING_TIMEOUT`**（秒）：后端等待 GMS 计算的最长时间，默认 `600`，最小有效值 `60`。
- 部署时请保持：**网关读超时 ≥ `GMS_SCREENING_TIMEOUT`**。

## 业务侧缓解（无需改网关时）

1. 优先使用「自选股」或「港股」缩小范围。  
2. 通过定时任务预先写入 `gms_signal_trace`，使在线请求以读表为主、计算量下降（需单独规划任务）。

## 相关代码

- 路由：`backend_api/stock/stock_screening_routes.py`（`GMS_SCREENING_TIMEOUT`）
- 前端提示：`frontend/js/screening.js`（GMS + 502/503/504 时的说明文案）
