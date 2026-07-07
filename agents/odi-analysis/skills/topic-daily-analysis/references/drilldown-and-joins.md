# 反查会话、关联 Message_v2

展示列按回复语言选用对应 `_zh` / `_en` 列；SQL 可同时 SELECT 双语列供 Agent 选择。

## 按 intent_theme 精确反查

```sql
SELECT
  t.chat_created_at::date AS session_date,
  t.chat_id,
  t.user_email,
  t.intent_theme,
  t.intent_theme_en,
  t.primary_region_codes,
  t.primary_region_names_zh,
  t.primary_region_names_en,
  t.core_summary,
  t.core_summary_en,
  t.primary_service,
  t.primary_service_name_zh,
  t.primary_service_name_en,
  t.message_count,
  t.confidence
FROM "ChatTopicDailyAnalysis" t
WHERE t.intent_theme = '越南公司运营合规要求'
  AND t.chat_created_at::date >= CURRENT_DATE - 30
ORDER BY t.chat_created_at DESC;
```

英文议题反查示例：

```sql
WHERE t.intent_theme_en ILIKE '%Vietnam compliance%'
```

## 模糊 / 多字段检索

```sql
SELECT
  t.chat_id,
  t.intent_theme,
  t.intent_theme_en,
  left(t.core_summary, 160) AS summary_zh,
  left(t.core_summary_en, 160) AS summary_en
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND (
    t.intent_theme ILIKE '%原产地%'
    OR t.intent_theme_en ILIKE '%origin%'
    OR t.core_summary ILIKE '%原产地%'
    OR t.core_summary_en ILIKE '%origin%'
    OR t.primary_region_codes && ARRAY['VN']::text[]
    OR EXISTS (
      SELECT 1 FROM unnest(t.primary_region_names_zh, t.primary_region_names_en) AS n(name)
      WHERE n.name ILIKE '%越南%' OR n.name ILIKE '%Vietnam%'
    )
  )
ORDER BY t.confidence DESC, t.message_count DESC
LIMIT 30;
```

## 关联完整对话（Message_v2）

```sql
SELECT
  t.chat_id,
  t.intent_theme,
  t.intent_theme_en,
  t.core_summary,
  t.core_summary_en,
  m.role,
  m.parts,
  m."createdAt"
FROM "ChatTopicDailyAnalysis" t
JOIN "Message_v2" m ON m."chatId" = t.chat_id
WHERE t.intent_theme ILIKE '%ODI%'
   OR t.intent_theme_en ILIKE '%ODI%'
  AND t.chat_created_at::date >= CURRENT_DATE - 14
ORDER BY t.chat_id, m."createdAt"
LIMIT 200;
```

`parts` 为 JSON：文本块 `type=text` 的 `text` 字段为用户/助手正文。

## 关联 Chat 元数据

```sql
SELECT
  t.chat_id,
  c.title,
  c."createdAt",
  c.visibility,
  t.intent_theme,
  t.intent_theme_en,
  t.core_summary,
  t.core_summary_en
FROM "ChatTopicDailyAnalysis" t
JOIN "Chat" c ON c.id = t.chat_id
WHERE t.user_id = '<uuid>'::uuid
ORDER BY c."createdAt" DESC;
```

## 某议题下的用户列表

```sql
SELECT
  COUNT(DISTINCT t.user_id)::int AS users,
  array_agg(DISTINCT t.user_email) AS emails_sample
FROM "ChatTopicDailyAnalysis" t
WHERE (
    t.intent_theme ILIKE '%预扣税%'
    OR t.intent_theme_en ILIKE '%withholding%'
  )
  AND t.chat_created_at::date >= CURRENT_DATE - 30;
```

## 报告中的 PII 规则

- 禁止批量输出 `user_text` 全文；抽样 ≤5 条 summary 预览
- 邮箱：按 system prompt，当前分析场景可不脱敏；对外分享时再脱敏
