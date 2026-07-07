# 定价与金额分析

## 指标定义

| 指标 | 数据源 |
|------|--------|
| 行项目金额 | `services[].amount`, `one_off_fee`, `annual_fee`, `recurring_fee` |
| 首单合计 | `first_total_invoice[].total` / `price` |
| 目录标准价 | `service_and_fee_au_incorp.hubspot_price`, `standard_pricing` |
| 覆盖定价 | `pricing_overrides`（对象，按路径对照 Skill §proposalState） |

JSON 中金额常为 **字符串**，分析时用 `CAST(... AS DECIMAL(18,2))` 并过滤非数字。

## 行项目金额分布（按 SKU）

```sql
SELECT
  jt.sku,
  COUNT(*) AS n,
  MIN(CAST(jt.amount AS DECIMAL(18,2))) AS min_amount,
  MAX(CAST(jt.amount AS DECIMAL(18,2))) AS max_amount,
  AVG(CAST(jt.amount AS DECIMAL(18,2))) AS avg_amount
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
JOIN JSON_TABLE(
  st.state,
  '$.business_case_services.business_cases[*].services[*]'
  COLUMNS (
    sku VARCHAR(128) PATH '$.sku',
    amount VARCHAR(64) PATH '$.amount'
  )
) AS jt ON TRUE
WHERE cs.is_template = 0
  AND cs.proposal_type IN ('incorp_au_advisory', 'incorp_au_audit')
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
  AND jt.amount REGEXP '^[0-9]+(\\.[0-9]+)?$'
GROUP BY jt.sku
HAVING n >= 5
ORDER BY n DESC
LIMIT 100;
```

## 首单发票总额分布

```sql
SELECT
  jt.currency,
  COUNT(*) AS lines,
  AVG(CAST(jt.total AS DECIMAL(18,2))) AS avg_total,
  MIN(CAST(jt.total AS DECIMAL(18,2))) AS min_total,
  MAX(CAST(jt.total AS DECIMAL(18,2))) AS max_total
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
JOIN JSON_TABLE(
  st.state,
  '$.first_total_invoice[*]'
  COLUMNS (
    currency VARCHAR(16) PATH '$.currency',
    total VARCHAR(64) PATH '$.total'
  )
) AS jt ON TRUE
WHERE cs.is_template = 0
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
  AND jt.total REGEXP '^[0-9]+(\\.[0-9]+)?$'
GROUP BY jt.currency
LIMIT 200;
```

## 报价金额 vs 目录价（抽样核对）

```sql
SELECT
  jt.sku,
  CAST(jt.amount AS DECIMAL(18,2)) AS quoted_amount,
  cat.hubspot_price AS catalog_price,
  cs.id AS session_id
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
JOIN JSON_TABLE(
  st.state,
  '$.business_case_services.business_cases[*].services[*]'
  COLUMNS (
    sku VARCHAR(128) PATH '$.sku',
    amount VARCHAR(64) PATH '$.amount'
  )
) AS jt ON TRUE
JOIN service_and_fee_au_incorp cat ON cat.sku = jt.sku AND cat.is_active = 1
WHERE cs.is_template = 0
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND jt.amount REGEXP '^[0-9]+(\\.[0-9]+)?$'
LIMIT 500;
```

在应用层或二次查询中统计：报价高于/低于目录价的占比（SQL 中可用 `quoted_amount - catalog_price`）。

## 有 pricing_overrides 的会话占比

```sql
SELECT
  SUM(JSON_LENGTH(JSON_KEYS(st.state, '$.pricing_overrides')) > 0) AS with_overrides,
  COUNT(*) AS total
FROM chat_states st
JOIN chat_sessions cs ON cs.id = st.session_id
WHERE cs.is_template = 0
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
LIMIT 2000;
```

（若 `pricing_overrides` 为空对象，`JSON_KEYS` 行为需用 `describe_table` + 小样本验证后调整。）

## 注意

- 动态定价建议 = **推断**，需写明样本量与时间段
- 勿在报告中罗列单笔客户报价明细，用区间与占比
- `deal_info.amount` 为 varchar，deal 级金额见 [deal-analytics.md](deal-analytics.md)
