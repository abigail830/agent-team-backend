# 产品、SKU 与组合分析

## 指标定义

| 指标 | 定义 |
|------|------|
| SKU 出现次数 | 从 `chat_states.state` 展开 `business_cases[].services[]`，按 `sku` 计数 |
| 套餐/方案 | `business_cases[].name` 分布 |
| Cross-sell 共现 | 同一会话内 SKU 对 (A,B) 共现次数 |
| 目录对照 | `service_and_fee_ph_incorp` 补充 `service_name`、`is_package` |

默认统计**最新态** `chat_states`，时间过滤在 `chat_sessions` 上。

## Top SKU（出现次数）

```sql
SELECT
  jt.sku,
  jt.service_name,
  COUNT(*) AS proposal_lines,
  COUNT(DISTINCT cs.id) AS proposal_count
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
JOIN JSON_TABLE(
  st.state,
  '$.business_case_services.business_cases[*].services[*]'
  COLUMNS (
    sku VARCHAR(128) PATH '$.sku',
    service_name VARCHAR(255) PATH '$.service_name'
  )
) AS jt ON TRUE
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
  AND jt.sku IS NOT NULL AND jt.sku <> ''
GROUP BY jt.sku, jt.service_name
ORDER BY proposal_count DESC, proposal_lines DESC
LIMIT 100;
```

## 业务方案 / 套餐名分布

```sql
SELECT
  jt.case_name,
  COUNT(DISTINCT cs.id) AS proposal_count
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
JOIN JSON_TABLE(
  st.state,
  '$.business_case_services.business_cases[*]'
  COLUMNS (case_name VARCHAR(255) PATH '$.name')
) AS jt ON TRUE
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
GROUP BY jt.case_name
ORDER BY proposal_count DESC
LIMIT 100;
```

## SKU 共现（Cross-sell 信号）

先取每会话 SKU 集合，再自连接（示例：Top 20 SKU 两两共现）：

```sql
WITH session_skus AS (
  SELECT DISTINCT
    cs.id AS session_id,
    jt.sku
  FROM chat_sessions cs
  JOIN chat_states st ON st.session_id = cs.id
  JOIN JSON_TABLE(
    st.state,
    '$.business_case_services.business_cases[*].services[*]'
    COLUMNS (sku VARCHAR(128) PATH '$.sku')
  ) AS jt ON TRUE
  WHERE cs.is_template = 0
    AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
    AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
    AND jt.sku IS NOT NULL AND jt.sku <> ''
)
SELECT
  a.sku AS sku_a,
  b.sku AS sku_b,
  COUNT(*) AS co_occurrence_sessions
FROM session_skus a
JOIN session_skus b
  ON a.session_id = b.session_id AND a.sku < b.sku
GROUP BY a.sku, b.sku
HAVING co_occurrence_sessions >= 3
ORDER BY co_occurrence_sessions DESC
LIMIT 100;
```

## 对照产品目录（套餐标记）

```sql
SELECT
  cat.sku,
  cat.service_name,
  cat.is_package,
  cat.hubspot_price,
  usage_stats.proposal_count
FROM service_and_fee_ph_incorp cat
LEFT JOIN (
  SELECT jt.sku, COUNT(DISTINCT cs.id) AS proposal_count
  FROM chat_sessions cs
  JOIN chat_states st ON st.session_id = cs.id
  JOIN JSON_TABLE(
    st.state,
    '$.business_case_services.business_cases[*].services[*]'
    COLUMNS (sku VARCHAR(128) PATH '$.sku')
  ) AS jt ON TRUE
  WHERE cs.is_template = 0
    AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
  GROUP BY jt.sku
) AS usage_stats ON usage_stats.sku = cat.sku
WHERE cat.is_active = 1
ORDER BY usage_stats.proposal_count DESC
LIMIT 200;
```

## 注意

- `amount` / fee 字段在 JSON 中可能是字符串，定价专题见 [pricing-analytics.md](pricing-analytics.md)
- Cross-sell 结论写「常一起出现在同一份报价中」，避免因果表述
