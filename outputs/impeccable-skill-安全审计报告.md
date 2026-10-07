# 🔍 安全审计报告

## 📊 执行摘要

- **审计对象**: `impeccable` skill v4.3.1（Apache 2.0）
  - 路径：`.cursor/skills/impeccable/`（52 个文件）
  - 附带子代理：`.cursor/agents/impeccable-*.md`（4 个）
- **审计时间**: 2026-10-07 10:20 (GMT+8)
- **发现问题总数**: 1 个
  - 🔴 P0 阻断级: **0 个**
  - ⚠️ P1 需关注: **1 个**
  - 📝 信息性提醒: 3 个（非风险项，不计入风险总数）
- **安全评分**: **88 / 100**

**审计范围**：`SKILL.md`、`reference/`（38 个 md）、`scripts/`（2 个启动器、5 个 JS、3 个 JSON 数据、1 个 14.7MB 二进制）、`.cursor/hooks.json`、`.cursor/agents/`。

---

## 🔴 P0 阻断级风险发现

✅ 未发现 P0 风险。

未发现以下任一 P0 特征：自动下载后立即执行未校验内容、读取敏感凭据外送、自动执行破坏性命令、隐蔽执行、权限提升。

---

## ⚠️ P1 需关注风险发现

### 1. 启动器具备「自动下载 + 执行远程二进制」兜底能力

- **位置**:
  - `scripts/impeccable:95–201`（sh/Unix 启动器）
  - `scripts/impeccable.cmd:64–158`（Windows 启动器）
- **代码片段**:
  ```sh
  base="${IMPECCABLE_DOWNLOAD_BASE:-https://github.com/pbakaus/impeccable/releases/download}"
  url="$base/engine-v$version/$asset"
  curl -fsSL --retry 2 -o "$tmp" "$1"
  ...
  exec "$cached" "$@"
  ```
  ```bat
  set "IMPECCABLE_DOWNLOAD_BASE=https://github.com/pbakaus/impeccable/releases/download"
  curl.exe -fsSL -o "%cached%.part" "%url%" >nul 2>nul
  ```
- **风险描述**: 当本地找不到引擎二进制时，启动器会自动从远程下载对应平台的可执行文件并运行。
- **攻击场景**: 若下载通道被劫持或 GitHub Release 被篡改，可能执行到被替换的二进制。
- **实际缓解措施（同类中较优）**:
  1. **强制校验、fail-closed**：下载后必须比对 `.sha256` sidecar；sidecar 取不到、本机无 `shasum/sha256sum/certutil`、或哈希不一致，一律拒绝执行并以 127 退出，绝不放行未校验文件。
  2. **本机已自带二进制，该分支不会触发**：`scripts/bin/windows-x64/impeccable.exe`（14,720,392 字节，sha256=`477e544fc8880a5e82e427490cb9a5f5adab480c0e02966d33fd50772b531c71`）。启动器优先使用同级二进制，下载仅在「二进制缺失」时才走。
  3. **下载源为官方仓库**：`github.com/pbakaus/impeccable`（作者 Paul Bakaus，真实开源项目，含 npm 包与 Releases 通道）。
- **定级说明**: 依据审计规则，二进制文件**无法静态分析**内容安全性 → 「下载+执行」由 P0 降为 **P1**。建议固化本地二进制（本次安装即整目录复制，已满足）或自行核对 sha256。

---

## 📝 信息性提醒（非风险项）

### 1. 二进制内嵌 `api.openai.com`
- **位置**: `scripts/bin/windows-x64/impeccable.exe`（字符串）
- **说明**: 对应 `generate-image` 兜底能力——当 harness 无原生出图工具时，用**用户自己的** API Key 调用官方图像接口。属「读取自身凭证调用对应官方服务」，合理。
- **建议**: 使用时确认密钥由环境变量注入，不要硬编码。

### 2. `AKIA...` 字符串命中（误报）
- **位置**: `scripts/bin/windows-x64/impeccable.exe`（数据段）
- **说明**: 命中形如 `AKIA02AggLIAtBEGokAC` 的字符串，但含小写字母，不符合 AWS Access Key ID 格式（`AKIA` + 16 位大写），系二进制数据段的随机字节巧合，**非真实凭据**。

### 3. `.cursor/hooks.json` 的 preToolUse 钩子
- **位置**: `.cursor/hooks.json:6`
- **代码**: `[ ! -f ".cursor/skills/impeccable/scripts/impeccable" ] || ".cursor/skills/impeccable/scripts/impeccable" hook-before-edit`
- **说明**: 每次编辑前端文件时自动运行**本地**设计检测器（非危险操作）。该文件是 **Cursor 专属格式**，WorkBuddy 不读取，安装后不会在 WorkBuddy 中生效。
- **建议**: 如需在 WorkBuddy 使用等价钩子，需另行配置。

---

## 📋 详细检查结果

### 命令执行与权限检查
- 发现次数: 6（全部集中在 2 个启动器脚本）
- 详细列表:
  - `scripts/impeccable:42,61,65,73,81,84,196` — `exec`（运行本地引擎二进制）
  - `scripts/impeccable:96–99,155–159` — `curl` / `wget` 下载（含 `--retry`）
  - `scripts/impeccable:164–167` — `shasum -a 256` / `sha256sum` 校验
  - `scripts/impeccable.cmd:85,90,100` — `curl.exe` 下载；`:110` — `certutil -hashfile` 校验
  - **未发现** `sudo`、`chmod 777`、`rm -rf`、`eval`、`base64 -d | bash`、`nohup`、`authorized_keys`、`crontab` 等危险/隐蔽命令

### 文件操作与敏感路径检查
- 发现次数: 0（真实命中）
- 说明: 启动器仅写入自有缓存目录 `~/.impeccable/bin/<version>/`；未读取 `~/.ssh`、`~/.aws`、`.env`、`credentials` 等敏感路径。`reference/*.md` 中大量 `token` / `secret` / `password` 命中均为**设计术语**（design tokens）或文档正文，非敏感文件访问。

### 网络请求检查
- 发现的 URL（文本类文件）:
  - `https://github.com/pbakaus/impeccable/releases/download`（下载源，官方）
  - `https://impeccable.style`、`https://impeccable.style/docs/`（官方文档）
  - `http://localhost:PORT/...`、`http://localhost:8400`、`http://127.0.0.1`（live 模式本地回环，仅本地）
  - `https://github.com/pbakaus/impeccable/blob/.../tests/live-e2e/agent.mjs`（文档引用）
- **Base64 编码检测**: 未发现可疑长 Base64 载荷。
- **结论**: 文本类文件**不含任何数据外送**；`live-browser*.js` 的全部 `fetch`/`EventSource` 目标均为 `localhost`。二进制内嵌域名为 `localhost`、`www.w3.org`、`microsoft.com`（运行时库）、`impeccable.style`、`github.com`、`fonts.googleapis.com`、`api.openai.com`，与声称功能一致。

### 远程脚本深度分析
- **URL**: `https://github.com/pbakaus/impeccable/releases/download/engine-v<version>/impeccable-windows-x64.exe`
- **脚本可访问性**: 官方 Release 通道，可达；内容为**二进制文件 → 无法静态分析**
- **发现的恶意/可疑行为**: 未发现（无法解析二进制内容）
- **脚本主要功能**: Impeccable 设计引擎 CLI
- **深度分析结论**: 无法验证内容安全性
- **定级影响**: 依据规则「无法解析 → P1」，该项最终定为 **P1**

### 依赖安装风险检查
- **全局安装检测**: ✅ 无。未发现 `npm install -g`、`pip install`、`gem/cargo/go install` 等任何依赖安装指令。
- **虚拟环境检查**: 不适用（无依赖安装）。
- **依赖来源检查**: ✅ 无第三方源。skill 自带二进制 + 自带 JS 库（`modern-screenshot.umd.js` 为打包的成熟前端库），运行不需要 Node 或任何运行时。

---

## 💡 总体建议

1. **保持整目录安装**：复制时务必包含 `scripts/bin/` 下的自带二进制，避免触发远程下载分支。
2. **如需更强保证**：核对已记录的 sha256（`477e544f...b531c71`），或设置 `IMPECCABLE_BIN` 指向自行校验过的引擎二进制。
3. **注意路径迁移**：技能内部多处引用 `.cursor/skills/impeccable/scripts/...`。安装到新位置后，请以 SKILL.md 所在目录（base dir）解析这些路径；原 `.cursor/` 副本保留可兼容。
4. **钩子不随安装迁移**：`.cursor/hooks.json` 为 Cursor 专属，WorkBuddy 不读取。
5. **凭据管理**：`generate-image` 兜底会使用你的 API Key 调用官方接口，请用环境变量注入。

---

## ✅ 审计结论

**风险等级**: ⚠️ **P1 - 需关注**

**使用建议**: ⚠️ **建议确认后使用**。未发现任何投毒行为与恶意意图；唯一 P1 项是「远程下载兜底」这一固有供应链攻击面，且已被强制哈希校验 + 本地自带二进制双重缓解，实际触发概率极低。相比之下，该技能在同规模第三方技能中安全设计属于**较好**水平（fail-closed 校验、无依赖安装、无数据外送、无敏感路径访问）。

---

**📌 审计原则提醒**：本报告仅覆盖 skill 自身的供应链投毒风险，不评估其设计指导内容的质量。
