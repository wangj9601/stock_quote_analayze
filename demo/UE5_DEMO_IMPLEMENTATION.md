# UE5 Demo 落地指南（无 C#）

## 1. 目标
- 在 UE5 中实现与 Web Demo 对齐的 6 项能力：
  - 地图点选联动
  - PiP 拖拽缩放
  - 告警自动弹窗
  - 多窗管理（最多 4 路）
  - 断线重连
  - 性能状态看板

## 2. 工程与插件
- UE5 版本：建议 5.3+
- 必备插件：
  - `Cesium for Unreal`
  - `Pixel Streaming`
  - `WebSocket`（或你团队已有的 Socket/HTTP 插件）
- 推荐目录：
  - `Content/Blueprints/Core`
  - `Content/Blueprints/UI`
  - `Content/Materials/Status`
  - `Content/DataTables`

## 3. 蓝图资产清单
- `BP_MapController`
  - 职责：场景初始化、点位加载、镜头巡航和聚焦。
- `BP_DeviceActor`
  - 职责：显示单设备状态，响应点击，切换告警材质。
- `BP_RealtimeGateway`
  - 职责：WebSocket 连接、心跳、断线重连、消息分发。
- `BP_AlarmDirector`
  - 职责：接收告警事件并编排“高亮 + 飞行 + 弹窗”。
- `WBP_PiPWindow`
  - 职责：单路视频窗口，支持拖拽、缩放、置顶、最小化、关闭。
- `WBP_PiPManager`
  - 职责：多窗口布局管理与上限控制（最多 4 路）。
- `WBP_PerfPanel`
  - 职责：展示 FPS、数据延迟、连接状态。

## 4. 数据结构定义（Blueprint Struct）
- `ST_DeviceSnapshot`
  - `deviceId` (String)
  - `name` (String)
  - `longitude` (Float)
  - `latitude` (Float)
  - `altitude` (Float)
  - `status` (String: online/offline)
  - `alarmLevel` (String: none/low/high)
  - `cameraId` (String)
- `ST_DeviceDelta`
  - `ts` (String)
  - `deviceId` (String)
  - `status` (String)
  - `alarmLevel` (String)
  - `metrics` (Map String->Float)
- `ST_AlarmEvent`
  - `alarmId` (String)
  - `deviceId` (String)
  - `alarmLevel` (String)
  - `alarmType` (String)
  - `startTime` (String)
  - `message` (String)

## 5. 关键蓝图流程

### 5.1 点位点击 -> 打开 PiP
- `BP_DeviceActor.OnClicked`
  - 发送事件：`EventDispatcher_OpenPiP(deviceId, cameraId, name)`
- `WBP_PiPManager`
  - 收到事件后：
    - 若窗口已存在：执行置顶
    - 若窗口不存在且 < 4：创建 `WBP_PiPWindow`
    - 若已达上限：关闭最旧窗口后新建

### 5.2 告警事件 -> 自动联动
- `BP_RealtimeGateway.OnAlarmMessage`
  - 解析消息 -> 广播 `EventDispatcher_AlarmRaised`
- `BP_AlarmDirector`
  - 根据 `deviceId` 查找 `BP_DeviceActor`
  - 执行：
    - 切换高优告警材质（红色脉冲）
    - 调用 `BP_MapController.FocusOnDevice`
    - 调用 `WBP_PiPManager.OpenOrFocus(cameraId)`

### 5.3 断线重连
- `BP_RealtimeGateway`
  - `OnConnectionClosed` -> 状态设为 `Reconnecting`
  - 使用定时器每 1 秒尝试重连，最大 10 次
  - 重连成功后拉取一次全量快照并继续增量订阅

## 6. PiP UI 实现建议（UMG）
- `WBP_PiPWindow` 结构：
  - 顶部标题栏（可拖拽）
  - 视频区域（MediaTexture）
  - 右下角缩放锚点
  - 按钮：最小化/置顶/关闭
- 支持操作：
  - 拖拽：记录鼠标按下偏移并更新 CanvasSlot Position
  - 缩放：限制最小尺寸 320x180，最大尺寸 960x540
  - 置顶：调整 ZOrder

## 7. 后端接口约定（与 Web Demo 一致）
- `GET /api/twin/devices`
- `GET /api/video/stream?cameraId=xxx&protocol=webrtc|hls`
- `WS /ws/twin/state`
- `WS /ws/twin/alarm`

## 8. 演示脚本（3 分钟）
- 第 0-30 秒：全景巡航，展示园区模型和点位分布。
- 第 30-90 秒：点击 2-3 个设备，展示多路 PiP 拖拽缩放。
- 第 90-140 秒：注入高优告警，自动飞行+自动弹窗+设备高亮。
- 第 140-180 秒：模拟断线并恢复，展示重连与状态恢复。

## 9. 验收阈值
- 本地大屏：
  - 1080p 下常态 FPS >= 50
  - 数据延迟 <= 1s
  - 视频首帧 <= 2s
- Web（Pixel Streaming）：
  - 关键交互响应 <= 500ms
