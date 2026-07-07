# 区域热度与服务交叉（辅助维度）

区域已归一化为 **ISO 国家 code** 或 **宏观区域 slug**（无省市级）。展示名称用 `primary_region_names_zh` / `primary_region_names_en`（与 codes 平行数组）。

## 区域热度（展开 primary_region_codes）

```sql
SELECT
  r AS region_code,
  MAX(t.primary_region_names_zh[array_position(t.primary_region_codes, r)]) AS region_name_zh,
  MAX(t.primary_region_names_en[array_position(t.primary_region_codes, r)]) AS region_name_en,
  COUNT(*)::int AS sessions,
  COUNT(DISTINCT t.user_id)::int AS users
FROM "ChatTopicDailyAnalysis" t
CROSS JOIN LATERAL unnest(t.primary_region_codes) AS r
WHERE t.chat_created_at::date >= CURRENT_DATE - 14
  AND r IS NOT NULL
  AND r <> 'UNMENTIONED'
  AND t.confidence >= 0.85
  AND NOT EXISTS (
    SELECT 1 FROM "InternalUser" iu
    WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
  )
GROUP BY r
ORDER BY sessions DESC
LIMIT 25;
```

报告展示时按回复语言选用 `region_name_zh` 或 `region_name_en`；也可直接用 `chat_topic_region_labels` 中的标准 label。

## 某区域 Top 议题（按 ISO code）

```sql
SELECT
  t.intent_theme,
  t.intent_theme_en,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND t.primary_region_codes @> ARRAY['SG']::text[]
  AND t.confidence >= 0.85
GROUP BY t.intent_theme, t.intent_theme_en
ORDER BY sessions DESC
LIMIT 15;
```

用户说「新加坡」→ 用 `SG`；「越南」→ `VN`。不确定时可用 names ILIKE：

```sql
AND EXISTS (
  SELECT 1 FROM unnest(t.primary_region_names_zh, t.primary_region_names_en) AS n(name)
  WHERE n.name ILIKE '%越南%' OR n.name ILIKE '%Vietnam%'
)
```

## 服务领域分布（L2 code）

```sql
SELECT
  t.primary_service,
  MAX(t.primary_service_name_zh) AS name_zh,
  MAX(t.primary_service_name_en) AS name_en,
  COUNT(*)::int AS sessions,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND t.confidence >= 0.85
  AND NOT EXISTS (
    SELECT 1 FROM "InternalUser" iu
    WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
  )
GROUP BY t.primary_service
ORDER BY sessions DESC;
```

## 一级 grouping rollup（跨境 / 公司服务 / 其他）

```sql
SELECT
  CASE
    WHEN t.primary_service IN ('market_entry_structuring', 'licensing_permits')
      THEN 'cross_border'
    WHEN t.primary_service IN (
      'incorporation_setup',
      'corporate_governance_secretarial',
      'restructuring_liquidation'
    ) THEN 'corporation'
    ELSE 'other_services'
  END AS service_group,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND t.confidence >= 0.85
GROUP BY 1
ORDER BY sessions DESC;
```

展示 label：中文 → 跨境业务 / 公司服务 / 其他一级服务；英文 → Cross-Border / Corporation / Other Services。

## 服务 × 区域矩阵

```sql
SELECT
  t.primary_service,
  r AS region_code,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
CROSS JOIN LATERAL unnest(t.primary_region_codes) AS r
WHERE t.chat_created_at::date >= CURRENT_DATE - 30
  AND r <> 'UNMENTIONED'
  AND t.confidence >= 0.85
GROUP BY 1, 2
ORDER BY sessions DESC
LIMIT 50;
```

## 区域 × 意图类型（看咨询形态）

```sql
SELECT
  r AS region_code,
  t.intent_type,
  COUNT(*)::int AS sessions
FROM "ChatTopicDailyAnalysis" t
CROSS JOIN LATERAL unnest(t.primary_region_codes) AS r
WHERE t.chat_created_at::date >= CURRENT_DATE - 14
  AND r <> 'UNMENTIONED'
  AND t.confidence >= 0.85
GROUP BY 1, 2
ORDER BY sessions DESC;
```

---

## primary_service 枚举（v2）

权威来源：`src/ops_backend/db/chat_topic_taxonomy_v2.py`

| code | 中文 | English | 一级 grouping |
|------|------|---------|---------------|
| market_entry_structuring | 市场准入与跨境架构筹划 | Market Entry & Cross-Border Structuring | 跨境业务 |
| licensing_permits | 资质牌照与准入审批 | Licensing & Permits | 跨境业务 |
| incorporation_setup | 公司设立与实体组建 | Incorporation & Entity Setup | 公司服务 |
| corporate_governance_secretarial | 公司日常管治与秘书服务 | Corporate Governance & Secretarial | 公司服务 |
| restructuring_liquidation | 企业重组、撤资与清算 | Restructuring & Liquidation | 公司服务 |
| legal_and_contracts | 法律咨询与合同事务 | Legal & Contracts | 其他 |
| tax_compliance_planning | 税务合规、筹划与转让定价 | Tax Compliance & Planning | 其他 |
| accounting_financial_ops | 会计、记账与日常财务外包 | Accounting & Financial Operations | 其他 |
| audit_risk_assurance | 审计与风险咨询 | Audit, Risk & Assurance | 其他 |
| hr_payroll_visa | 人力资源、薪酬与签证服务 | HR, Payroll & Visa | 其他 |
| fund_services | 基金服务 | Fund Services | 其他 |
| private_client_trusts | 私人客户与信托 | Private Client & Trusts | 其他 |
| other | 其他 | Other | 其他 |

**语义**：code 描述**话题**所属服务领域，非用户业务线归属；cross-sell 导致跨 service 分布正常。

## intent_type 枚举（v2）

| code | 中文 | English |
|------|------|---------|
| process | 咨询流程 | Process inquiry |
| compliance_risk | 合规风险 | Compliance & risk |
| cost_timeline | 费用时效 | Cost & timeline |
| comparison_selection | 对比选型 | Comparison & selection |
| policy_interpretation | 政策解读 | Policy interpretation |
| other | 其他 | Other |

枚举由打标管道映射，**不能**覆盖开放议题的全部语义；交叉分析时以 `intent_theme` 为主、`primary_service` / `intent_type` 为辅。

## 宏观区域 code 参考

`southeast_asia`, `asean`, `east_asia`, `south_asia`, `central_asia`, `middle_east`, `europe`, `north_america`, `south_america`, `latin_america`, `oceania`, `africa`, `apac`

权威来源：`src/ops_backend/db/chat_topic_region_labels.py`
