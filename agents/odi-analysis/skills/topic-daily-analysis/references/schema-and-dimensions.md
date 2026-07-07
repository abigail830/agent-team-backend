# ChatTopicDailyAnalysis schema 与分析维度

## 表定位

`ChatTopicDailyAnalysis` 是**每日会话主题分析的主落库表**（Function App 定时任务 UPSERT）。一行 = 一个 `chat_id` 在某一 `analysis_date` 上的主题快照。LLM 输出 code 与双语文本，落库时归一化为中英文标签列。

| 约束/索引 | 说明 |
|-----------|------|
| `(analysis_date, chat_id)` | 唯一键 |
| `chat_created_at` | 趋势分析主时间轴（与 Dashboard v2 API 一致） |
| `primary_region_codes` GIN | 区域数组，支持 `@>` / `&&` |

**时间轴选择：**

| 字段 | 含义 | 典型用途 |
|------|------|----------|
| `chat_created_at` | 会话真实创建时间 | **默认**：热点、周/月趋势、新兴/消退、与 Chat 对齐 |
| `analysis_date` | 批处理分析日（T 日分析 T-1 会话） | 数据覆盖检查、落库新鲜度 |

---

## 字段分层

### 主分析（LLM 开放挖掘）

| 字段 | 类型 | 分析方式 |
|------|------|----------|
| `intent_theme` / `intent_theme_en` | text | **核心维度**：议题短语；频次、周环比、新兴/消退、反查；展示列随回复语言 |
| `core_summary` / `core_summary_en` | text | 议题语义检索、`ILIKE`、与 theme 交叉验证；抽样阅读 |
| `primary_region_codes` | text[] | ISO-3166 alpha-2、宏观区域 slug、`UNMENTIONED`；`unnest` 展开 |
| `primary_region_names_zh` / `primary_region_names_en` | text[] | 与 codes 平行数组；展示用 |
| `confidence` | numeric(4,3) | 过滤低质量行（建议 ≥ 0.85）；加权统计 |

**区域 code 规则**（与 `chat_topic_region_labels.py` 一致）：

- ISO 国家：`SG`、`VN`、`CN`、`HK` 等（两位大写字母）
- 宏观区域：`southeast_asia`、`asean`、`east_asia`、`middle_east`、`europe` 等
- 未提及：`UNMENTIONED`（**非**中文「未提及」）
- **不含**省市级自由文本；历史脏数据应过滤

**注意：** `intent_theme` 为开放标签，**字面相同才归为同一主题**。跨周「语义相近但措辞不同」的议题需 Agent 二次聚类（见 SKILL.md §语义归并）。

### 辅助分析（枚举 code + materialized 标签）

| code 列 | 标签列 | 用途 |
|---------|--------|------|
| `primary_service` | `primary_service_name_zh` / `_en` | 话题服务领域分布、与区域交叉矩阵；见 SKILL.md §primary_service |
| `intent_type` | `intent_type_name_zh` / `_en` | 意图结构、辅助解释热点成因 |

### Ingest / 钻取

| 字段 | 用途 |
|------|------|
| `chat_id`, `user_id`, `user_email` | 反查会话、用户、去重统计 |
| `chat_title`, `user_text`, `message_count` | 轻量预览；深度内容 JOIN Message_v2 |
| `created_at`, `updated_at` | 行级审计 |

---

## 可分析维度矩阵

### 1. 时间

- 日趋势：`chat_created_at::date` + COUNT
- 周/月：`date_trunc('week'|'month', chat_created_at)`
- 窗口对比：近 7 天 vs 前 21 天（新兴/消退/份额变化）
- 数据覆盖：`MIN`/`MAX`/`COUNT(DISTINCT analysis_date)`

### 2. 议题（intent_theme + core_summary）

- **热点排行**：频次、独立用户数、平均 message_count
- **持续性热点**：两窗口均 ≥ 阈值
- **新兴议题**：近期出现、基线期为 0（字面匹配）
- **消退议题**：基线期有、近期为 0
- **主题漂移**：周度计数 / 份额变化率
- **语义聚类**（Agent）：对 Top N theme 或 summary 做 LLM 归并（非 SQL 默认）

### 3. 地理（primary_region_codes）

- 国家/宏观区域会话量、独立用户数
- 区域 × 议题 Top N
- 区域 × `primary_service` 矩阵
- 多区域会话占比：`cardinality(primary_region_codes) > 1` 且不含仅 `UNMENTIONED`

### 4. 服务与意图（辅助）

- `primary_service` L2 分布、时序；可选 rollup 到一级（跨境 / 公司服务 / 其他）
- `intent_type` 分布
- 三维切片：区域 + 服务 + 议题（Top K）

### 5. 用户与会话

- 每议题独立 `user_id` 数
- 高价值会话：`message_count` 或 `confidence` 排序
- 跨 service 咨询：同一 `user_id` 在不同 `primary_service` 均有会话（cross-sell 信号，非业务线归属）

### 6. 关联表扩展

| 关联 | JOIN 键 | 扩展维度 |
|------|---------|----------|
| `"Chat"` | `chat_id` = `Chat.id` | visibility、title 更新 |
| `"Message_v2"` | `chat_id` = `"chatId"` | 完整对话、工具调用、附件 |
| `"User"` | `user_id` = `User.id` | 仅当需校验邮箱等扩展信息时 JOIN；**统计人数/会话量请直接用主表 `user_id` / `user_email`** |
| `"InternalUser"` | email 匹配 `user_email` | **排除内部账号的唯一标准写法**（`NOT EXISTS` 子查询，见下方 SQL） |

---

## 数据质量与过滤惯例

```sql
-- 排除内部用户
AND NOT EXISTS (
  SELECT 1 FROM "InternalUser" iu
  WHERE lower(trim(iu.email)) = lower(trim(t.user_email))
)

-- 低置信过滤
AND t.confidence >= 0.85

-- 无地理信息（区域分析时）
AND NOT (t.primary_region_codes @> ARRAY['UNMENTIONED']::text[])
AND t.primary_region_codes IS NOT NULL
AND cardinality(t.primary_region_codes) > 0

-- 时间窗口（默认）
AND t.chat_created_at IS NOT NULL
AND t.chat_created_at::date >= CURRENT_DATE - INTERVAL '14 days'
```
