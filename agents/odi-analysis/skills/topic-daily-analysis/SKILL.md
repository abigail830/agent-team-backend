---
name: topic-daily-analysis
description: 分析 odi-knowledge-ai 内部销售问答会话（ChatTopicDailyAnalysis）：热点议题、周月漂移、新兴/消退主题、国家/宏观区域与服务领域、反查会话。面向销售管理与知识运营，提炼趋势与商机/知识缺口信号。用户问最近聊什么、热点、主题变化、新兴话题、区域热度、商机趋势、ChatTopicDailyAnalysis 时使用。只读 DB；回复语言跟随用户提问语言。
---

# ChatTopicDailyAnalysis 主题分析

## 与 Agent 系统 Prompt 的分工

| 层 | 位置 | 内容 |
|----|------|------|
| **角色与对外表述** | `agents/odi-analysis/system_prompt.md` | 读者画像、业务语言、禁止泄露实现细节 |
| **运行时** | `agents/odi-analysis/profile.yaml` | 只读 MCP、**必须加载本 Skill** |
| **方法与数据（对内）** | 本 Skill + `references/` | 表结构、SQL、过滤、语义归并、双语字段——**仅供查数，勿写入用户可见正文** |

触发本 Skill 后，查询与拆解步骤以本文与 references 为准；**回复正文遵守 system prompt 的「对外沟通铁律」**。

## 数据源

- **主表**：`"ChatTopicDailyAnalysis"`（每日 UPSERT，唯一键 `analysis_date + chat_id`）
- **重点字段（LLM 开放）**：`intent_theme` / `intent_theme_en`、`core_summary` / `core_summary_en`、`primary_region_codes` + `primary_region_names_zh` / `primary_region_names_en`
- **辅助字段（枚举 code + materialized 标签）**：`primary_service`、`intent_type` 及对应 `*_name_zh` / `*_name_en`
- **钻取**：`chat_id` → `"Chat"` / `"Message_v2"` / `"User"`

Schema 与维度矩阵见 [references/schema-and-dimensions.md](references/schema-and-dimensions.md)。

## 语言与双语字段

**回复语言**（与 system prompt 一致）：

1. 默认使用与用户**当前提问相同**的语言撰写报告。
2. 用户**明确指定**回复语言时，按指定语言输出。
3. 混合语言提问时，以**主体语言**为准；不确定时可简短确认。

**数据列选用**（`label_lang` = 回复语言，`zh` 或 `en`）：

| 用途 | 中文回复 (`zh`) | 英文回复 (`en`) |
|------|-----------------|-----------------|
| 议题 / 热点 | `intent_theme` | `intent_theme_en` |
| 摘要 / 检索 | `core_summary` | `core_summary_en` |
| 服务展示 | `primary_service_name_zh` | `primary_service_name_en` |
| 意图展示 | `intent_type_name_zh` | `intent_type_name_en` |
| 区域展示 | `primary_region_names_zh`（与 codes 平行数组） | `primary_region_names_en` |

**SQL 注意**：

- `GROUP BY`、矩阵轴、过滤仍用 **code 列**（`primary_service`、`intent_type`、`primary_region_codes`）。
- 用户用自然语言指区域（如「越南」「Singapore」）→ 映射 ISO code（`VN`、`SG`）或对 `primary_region_names_*` 做 `ILIKE`。
- 语义归并时，拉取与 `label_lang` 对应的 `intent_theme` + `core_summary` 列；跨语言对比可并列两列。

## primary_service 语义（v2 taxonomy）

`primary_service` 标注**会话话题所属的服务领域**，不是销售/BD 所属业务线。用户常 cross-sell，单用户跨多个 service 完全正常。

**二级 code**（13 个，权威列表见 `src/ops_backend/db/chat_topic_taxonomy_v2.py`）：

| code | 中文 | English |
|------|------|---------|
| market_entry_structuring | 市场准入与跨境架构筹划 | Market Entry & Cross-Border Structuring |
| licensing_permits | 资质牌照与准入审批 | Licensing & Permits |
| incorporation_setup | 公司设立与实体组建 | Incorporation & Entity Setup |
| corporate_governance_secretarial | 公司日常管治与秘书服务 | Corporate Governance & Secretarial |
| restructuring_liquidation | 企业重组、撤资与清算 | Restructuring & Liquidation |
| legal_and_contracts | 法律咨询与合同事务 | Legal & Contracts |
| tax_compliance_planning | 税务合规、筹划与转让定价 | Tax Compliance & Planning |
| accounting_financial_ops | 会计、记账与日常财务外包 | Accounting & Financial Operations |
| audit_risk_assurance | 审计与风险咨询 | Audit, Risk & Assurance |
| hr_payroll_visa | 人力资源、薪酬与签证服务 | HR, Payroll & Visa |
| fund_services | 基金服务 | Fund Services |
| private_client_trusts | 私人客户与信托 | Private Client & Trusts |
| other | 其他 | Other |

**一级 grouping**（管理层 rollup，仅两个重点领域做了二级拆分）：

| 一级 | 包含的 L2 code | 说明 |
|------|----------------|------|
| **跨境业务** | `market_entry_structuring`, `licensing_permits` | ODI/FDI、跨境架构、准入审批等 |
| **公司服务** | `incorporation_setup`, `corporate_governance_secretarial`, `restructuring_liquidation` | 设立、管治秘书、重组清算 |
| **其他一级服务** | 其余 8 个 code | 暂未细拆，按 L2 统计即可 |

**表述禁忌**：勿写「该用户属于 ODI 业务线」；应写「该话题涉及跨境架构筹划类咨询」。

区域与服务交叉、枚举详情见 [references/regions-and-services.md](references/regions-and-services.md)。

## 可视化（按需 suggest_visualization）

SQL 成功后平台**只缓存结果**，**不会**自动出图。在总结或解读阶段，当图表能显著帮助理解时再调用 `suggest_visualization`（只传 `intent`：`auto` / `trend` / `matrix` / `ranking` / `detail` / `none`）。展示顺序**跟随你的 ReAct 流程**（过渡语 → 查数 → 解读 → 按需出图），勿固定「先全部图再全部字」。

- 查数前用一两句说明打算查什么；查完后先用文字给出要点
- **值得可视化时**再 `suggest_visualization`；纯枚举、单行汇总、用户只要数字时可不出图
- 同轮多次 SQL：先 `list_sql_results` 取 `source_call_id`，再传给 `suggest_visualization`

| 场景 | 做法 |
|------|------|
| 多步分析 | 过渡语 → SQL → 文字解读 →（需要时出图）→ 下一 SQL → … → 总结 |
| 交叉矩阵 | SQL 三列（行、列、计数）+ `intent=matrix`；热力图橙色系深浅表强度 |
| 多系列对比 | `intent=auto` 或 `trend`；折线/柱/组合图由平台配色区分 series |
| 图表失败 | 平台降级表格；markdown 或文字补充，继续分析 |

勿粘贴 JSON 或 tool 名称；正文用「如下图」等指代即可。

## 工作流选择

| 用户意图 | 执行方式 | 参考 |
|----------|----------|------|
| 最近热点 / Top 议题 | postgres MCP SQL | [hot-topics.md](references/hot-topics.md) |
| 几周/一月主题变化、新兴、消退 | MCP SQL | [drift-and-churn.md](references/drift-and-churn.md) |
| 某主题有哪些会话、summary | MCP SQL 反查 | [drilldown-and-joins.md](references/drilldown-and-joins.md) |
| 区域热点、服务×区域 | MCP SQL | [regions-and-services.md](references/regions-and-services.md) |
| 数据覆盖情况 | MCP SQL（`analysis_date` 范围、`COUNT`） | [schema-and-dimensions.md](references/schema-and-dimensions.md) |

## 执行顺序

1. **确定回复语言**（见 §语言与双语字段）
2. **postgres MCP**：先用 **`list_tables` / `describe_table` / `get_schema`** 确认表结构，再 **`query_data`** 执行只读 SQL；复用 reference 片段，时间轴默认 `chat_created_at`
3. **`query_data` 必须带完整 `query` 参数**（非空 SELECT）。**禁止**在无 SQL 时调用（空 `{}` 会直接失败）
4. **禁止 `run_skill_script`**：本 Skill 仅含 Markdown references，无可执行脚本
5. **议题过于分散时**：对 Top theme + summary 做 **语义归并**（见下），勿重跑打标任务

## 常见统计（勿猜表结构）

**咨询人数 / 会话量**（如「最近一周有多少人对话」）——只在主表统计，**不要 JOIN `"User"`**：

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

**易错写法（会导致 query_data 失败）**：

- 空参数调用 `query_data`
- JOIN `"User"` 并用 `userType` / `email ILIKE '%internal%'` 过滤——应使用上文的 `"InternalUser"` + `NOT EXISTS`
- 未先 `describe_table` / `get_schema` 就猜测列名（如 `Chat.userId`）

## 语义归并（开放标签漂移）

`intent_theme` 字面唯一才算同一主题。用户问「漂移」「涌现」且 SQL 结果碎片化时：

1. 拉取目标窗口内 Top 60–100 个议题列（按 `label_lang` 选 `intent_theme` 或 `intent_theme_en`）及 1 条对应 summary 样例
2. LLM 归并成 12–20 个语义簇（簇名使用回复语言）
3. 输出：簇趋势、新簇、弱簇；附「成员 intent_theme」附录
4. 反查仍用 `ILIKE` 各成员关键词（在对应语言的 theme/summary 列上）

## 过滤惯例

- 排除 `"InternalUser"` 邮箱匹配的行
- 默认 `confidence >= 0.85`
- 区域分析时排除 `primary_region_codes` 含 `UNMENTIONED`（或空数组）
- 展开 `primary_region_codes` 时忽略非 taxonomy code（非 ISO alpha-2、非宏观区域 slug）

## 输出格式（用户可见）

使用**回复语言**撰写，**全文业务口吻**。结构对齐 system prompt；下列小节为内容要点，**标题与正文均勿使用表名/列名/SQL/MCP/Skill**。

### 摘要（给管理层 30 秒版）
- 时间范围、咨询会话量级、最值得关注的 2–3 条结论

### 大家在聊什么
- 热点议题、国家/区域、话题涉及的服务领域（附关键数字）；新出现 / 明显降温的主题

### 趋势与信号
- **销售管理**：需求升温领域、多位同事反复出现的议题、潜在商机或大单前置问题（谨慎表述，用业务依据说明）
- **知识运营**：高频但知识库覆盖不足的主题、建议补充的 FAQ/培训

### 分析口径（可选，1–3 句白话）
- 例：「统计 2026-03-01 至 2026-03-31 的销售同事对外问答」「已排除内部测试账号」「将字面上不同但含义相近的提问合并为若干主题簇」
- **禁止写法**：列出 `ChatTopicDailyAnalysis`、`chat_created_at`、`confidence >= 0.85`、`语义归并 Top 60` 等

### 建议的下一步
- 可执行动作（例：某区域税务专题复盘会、补充某国 ODI 指引）

### 对内 ↔ 对外 用语对照（写回复时替换）

| 对内（仅思考/查数） | 对用户说 |
|---------------------|----------|
| `ChatTopicDailyAnalysis` | 每日会话主题分析 / 问答主题归类结果 |
| `chat_created_at` 窗口 | 按会话发生时间统计的某段时间 |
| `intent_theme` 字面 vs 语义归并 | 按原话统计 / 将相近问法合并后看趋势 |
| `primary_service` / code | 服务领域（用 `*_name_zh` 或 `*_name_en` 展示名） |
| `confidence` 过滤 | 只纳入归类较有把握的记录 |
| 排除 `InternalUser` | 已排除内部测试账号 |
| `chat_id` 列表 | 仅在用户明确要求「列出具体会话/案例」时提供，且避免批量粘贴原文 |

**附录**：用户明确要求技术细节或对接开发时，可单独简短说明数据来源；默认报告不包含此类附录。

## 禁止

- 不要 `UPDATE`/`INSERT` `"ChatTopicDailyAnalysis"`（打标由 Function App 负责）
- 不要为分析目的重跑全量打标
