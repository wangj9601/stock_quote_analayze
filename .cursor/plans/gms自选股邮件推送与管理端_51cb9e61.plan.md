---
name: GMS自选股邮件推送与管理端
overview: 实现按用户自选股推送 GMS 均值引力策略选股结果邮件；新增邮件发送日志表与写入逻辑；在管理端提供邮件推送配置界面（含 report_type 含 gms_daily）与邮箱发送日志查询界面。
todos: []
isProject: false
---

# GMS 自选股邮件推送与管理端实现计划

## 一、需求摘要

1. **按用户自选股推送 GMS**：每个用户收到的 GMS 报告仅包含其自选股中通过 GMS 均值引力策略筛选的股票（非全市场）。
2. **管理端邮件发送配置**：管理端提供界面，可配置/编辑用户的推送设置（报告类型含「GMS 自选股」、推送时间、渠道、启用状态等）。
3. **邮件发送日志**：每次发送邮件（成功或失败）均落库一条记录，便于审计与排查。
4. **管理端邮件发送日志查询**：管理端提供页面，支持按用户、时间、成功/失败等条件查询邮件发送日志。

---

## 二、架构与数据流

```mermaid
flowchart TB
  subgraph scheduler [定时调度]
    PushScheduler
    execute_scheduled_push["execute_scheduled_push"]
  end
  subgraph push [PushService]
    push_to_user["push_to_user"]
    report_gen["generate_user_report"]
    email_send["_send_email_to_user"]
    write_log["写入邮件发送日志"]
  end
  subgraph report [ReportService]
    gms_watch
```



