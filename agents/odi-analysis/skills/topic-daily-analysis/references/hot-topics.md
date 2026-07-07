# 热点主题分析 — SQL

时间轴默认 `chat_created_at`。展示列按回复语言选用 `intent_theme` / `intent_theme_en`（SQL 可同时 SELECT 两列）。

## 时间窗口内咨询人数（distinct users）

```sql
SELECT
  COUNT(DISTINCT t.user_id)::int AS unique_users,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at >= NOW() - INTERVAL '7 days'
  AND t.confidence >= 0.85
  AND NOT EXISTS (
    SELECT 1 FROM "InternalUser" iu
    WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
  );
```

## 热点排行（按 intent_theme）

```sql
SELECT
  t.intent_theme,
  t.intent_theme_en,
  COUNT(*)::int AS sessions,
  COUNT(DISTINCT t.user_id)::int AS users,
  ROUND(AVG(t.confidence)::numeric, 3) AS avg_confidence,
  ROUND(AVG(t.message_count)::numeric, 1) AS avg_messages
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - INTERVAL '14 days'
  AND t.confidence >= 0.85
  AND NOT EXISTS (
    SELECT 1 FROM "InternalUser" iu
    WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
  )
GROUP BY t.intent_theme, t.intent_theme_en
ORDER BY sessions DESC, users DESC
LIMIT 30;
```

## 按周热点（看某周 Top 议题）

```sql
SELECT
  date_trunc('week', t.chat_created_at)::date AS week_start,
  t.intent_theme,
  t.intent_theme_en,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at >= date_trunc('week', CURRENT_DATE) - INTERVAL '8 weeks'
  AND NOT EXISTS (
    SELECT 1 FROM "InternalUser" iu
    WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
  )
GROUP BY 1, t.intent_theme, t.intent_theme_en
ORDER BY 1 DESC, sessions DESC;
```

## 高互动议题（message_count 加权）

```sql
SELECT
  t.intent_theme,
  t.intent_theme_en,
  SUM(t.message_count)::int AS total_messages,
  COUNT(*)::int AS sessions,
  ROUND(SUM(t.message_count)::numeric / NULLIF(COUNT(*), 0), 1) AS avg_depth
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 14
  AND t.confidence >= 0.85
GROUP BY t.intent_theme, t.intent_theme_en
HAVING COUNT(*) >= 2
ORDER BY total_messages DESC
LIMIT 20;
```

## core_summary 关键词热点（补充）

当 `intent_theme` 过于分散时，对 summary 做关键词统计（示例：越南 / Vietnam）：

```sql
SELECT COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND (
    t.core_summary ILIKE '%越南%'
    OR t.core_summary_en ILIKE '%Vietnam%'
    OR t.intent_theme ILIKE '%越南%'
    OR t.intent_theme_en ILIKE '%Vietnam%'
  );
```

## 输出解读

- **sessions**：该字面议题下的会话行数（≈ 会话数，因 chat_id 在日表唯一）
- **users**：独立咨询用户数；sessions ≫ users 表示同一议题多人关注
- **avg_messages**：高值可能表示深度追问，适合优先抽样复盘
- **报告展示**：中文回复用 `intent_theme`；英文回复用 `intent_theme_en`（fallback 到中文列若英文为空）
