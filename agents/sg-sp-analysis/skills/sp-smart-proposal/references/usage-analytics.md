# 使用情况与漏斗分析

## 指标定义

| 指标 | 定义 |
|------|------|
| 新建 Proposal 数 | 时间窗内 `chat_sessions` 计数（`is_template=0`） |
| 活跃用户数 | 时间窗内 `COUNT(DISTINCT user_id)` 或 `user_mail` |
| 互动深度 | 每会话 `chat_messages` 条数、用户消息占比 |
| 生成 Proposal | `session_state_version.is_proposal_generated = 1` 的会话（去重 `session_id`） |
| 漏斗 | 新建 → 有消息 → 有非空 `business_case_services` → `is_proposal_generated` |

时间窗默认：`chat_sessions.created_at` 或 `last_activity_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)`。

## 新建与活跃

```sql
SELECT
  COUNT(*) AS new_proposals,
  COUNT(DISTINCT cs.user_id) AS unique_users
FROM chat_sessions cs
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_sg_sme', 'SME', 'sg_sme')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
LIMIT 2000;
```

## 按日趋势

```sql
SELECT
  DATE(cs.created_at) AS day,
  COUNT(*) AS proposals
FROM chat_sessions cs
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_sg_sme', 'SME', 'sg_sme')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
GROUP BY DATE(cs.created_at)
ORDER BY day
LIMIT 2000;
```

## 消息深度（Top 会话）

```sql
SELECT
  cm.session_id,
  COUNT(*) AS message_count,
  SUM(cm.role = 'user') AS user_messages
FROM chat_messages cm
JOIN chat_sessions cs ON cs.id = cm.session_id
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_sg_sme', 'SME', 'sg_sme')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY cm.session_id
ORDER BY message_count DESC
LIMIT 50;
```

## 已生成 Proposal 的会话数

```sql
SELECT COUNT(DISTINCT ssv.session_id) AS generated_count
FROM session_state_version ssv
JOIN chat_sessions cs ON cs.id = ssv.session_id
WHERE cs.is_template = 0
  AND ssv.is_proposal_generated = 1
  AND ssv.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
LIMIT 2000;
```

## 阶段分布（最新态）

```sql
SELECT
  JSON_UNQUOTE(JSON_EXTRACT(st.state, '$.stage')) AS stage,
  COUNT(*) AS cnt
FROM chat_states st
JOIN chat_sessions cs ON cs.id = st.session_id
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_sg_sme', 'SME', 'sg_sme')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY stage
ORDER BY cnt DESC
LIMIT 2000;
```

## 注意

- 用户去重优先 `user_id`；为空时用 `user_mail`
- 报告用「报价会话」「活跃同事」「完成生成」等业务词，不写表名
