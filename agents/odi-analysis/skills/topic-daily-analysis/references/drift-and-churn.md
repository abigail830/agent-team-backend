# 主题漂移、新兴与消退

时间轴默认 `chat_created_at`。`GROUP BY` 用 `intent_theme`（中文列）；英文报告可并列 `intent_theme_en` 或按英文列单独聚合。

## 周环比份额变化

```sql
WITH bounds AS (
  SELECT
    CURRENT_DATE - 7 AS recent_start,
    CURRENT_DATE AS recent_end,
    CURRENT_DATE - 14 AS prev_start,
    CURRENT_DATE - 7 AS prev_end
),
recent AS (
  SELECT intent_theme, COUNT(*)::int AS cnt
  FROM "ChatTopicDailyAnalysis" t, bounds b
  WHERE t.chat_created_at::date >= b.recent_start
    AND t.chat_created_at::date < b.recent_end
    AND t.confidence >= 0.85
  GROUP BY 1
),
prev AS (
  SELECT intent_theme, COUNT(*)::int AS cnt
  FROM "ChatTopicDailyAnalysis" t, bounds b
  WHERE t.chat_created_at::date >= b.prev_start
    AND t.chat_created_at::date < b.prev_end
    AND t.confidence >= 0.85
  GROUP BY 1
)
SELECT
  COALESCE(r.intent_theme, p.intent_theme) AS intent_theme,
  COALESCE(p.cnt, 0) AS prev_week_cnt,
  COALESCE(r.cnt, 0) AS recent_week_cnt,
  COALESCE(r.cnt, 0) - COALESCE(p.cnt, 0) AS delta
FROM recent r
FULL OUTER JOIN prev p ON p.intent_theme = r.intent_theme
ORDER BY delta DESC NULLS LAST, recent_week_cnt DESC
LIMIT 40;
```

## 新兴议题（字面匹配版）

```sql
WITH w AS (
  SELECT
    intent_theme,
    COUNT(*) FILTER (WHERE chat_created_at::date >= CURRENT_DATE - 7)::int AS recent_cnt,
    COUNT(*) FILTER (
      WHERE chat_created_at::date >= CURRENT_DATE - 28
        AND chat_created_at::date < CURRENT_DATE - 7
    )::int AS baseline_cnt
  FROM "ChatTopicDailyAnalysis" t
  WHERE chat_created_at::date >= CURRENT_DATE - 28
    AND confidence >= 0.85
  GROUP BY intent_theme
)
SELECT * FROM w
WHERE recent_cnt >= 2 AND baseline_cnt = 0
ORDER BY recent_cnt DESC;
```

## 持续性热点（两窗均活跃）

```sql
SELECT intent_theme, recent_cnt, baseline_cnt
FROM (
  SELECT
    intent_theme,
    COUNT(*) FILTER (WHERE chat_created_at::date >= CURRENT_DATE - 7)::int AS recent_cnt,
    COUNT(*) FILTER (
      WHERE chat_created_at::date >= CURRENT_DATE - 28
        AND chat_created_at::date < CURRENT_DATE - 7
    )::int AS baseline_cnt
  FROM "ChatTopicDailyAnalysis"
  WHERE chat_created_at::date >= CURRENT_DATE - 28
    AND confidence >= 0.85
  GROUP BY 1
) x
WHERE recent_cnt >= 2 AND baseline_cnt >= 2
ORDER BY recent_cnt + baseline_cnt DESC;
```

## 语义漂移（Agent 流程，非 SQL 默认）

开放 `intent_theme` 会导致「同一议题多种写法」。当用户问「主题漂移」且字面匹配结果过于分散时：

1. 取近 N 周 Top 80 议题列（按回复语言）+ 对应 summary 样本（各 1–2 条）
2. LLM 归并为 15–25 个**语义簇**（簇名使用回复语言 + 成员 theme 列表）
3. 用簇名重绘周度趋势与新兴/消退结论
4. 报告中注明：「基于语义归并，非字面 intent_theme」

**不要**为此重新跑 Function App 打标。

## 服务领域维度漂移（L2）

```sql
SELECT
  date_trunc('week', chat_created_at)::date AS week_start,
  primary_service,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis"
WHERE chat_created_at::date >= CURRENT_DATE - 56
  AND confidence >= 0.85
GROUP BY 1, 2
ORDER BY 1, sessions DESC;
```

## 一级 grouping 漂移（可选 rollup）

```sql
SELECT
  date_trunc('week', chat_created_at)::date AS week_start,
  CASE
    WHEN primary_service IN ('market_entry_structuring', 'licensing_permits')
      THEN 'cross_border'
    WHEN primary_service IN (
      'incorporation_setup',
      'corporate_governance_secretarial',
      'restructuring_liquidation'
    ) THEN 'corporation'
    ELSE 'other_services'
  END AS service_group,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis"
WHERE chat_created_at::date >= CURRENT_DATE - 56
  AND confidence >= 0.85
GROUP BY 1, 2
ORDER BY 1, sessions DESC;
```

展示 label 随回复语言切换（见 regions-and-services.md §一级 grouping）。
