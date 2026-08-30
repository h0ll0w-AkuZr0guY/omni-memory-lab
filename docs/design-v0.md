# Omni Memory v0 设计基线

## 1. 项目目标

Omni Memory 是一个证据优先、可审计、可评估的长期记忆服务，首先服务于 neuro-book 的长篇小说创作场景，同时保留接入 Chronicle Memory 等其他 Agent 应用的能力。系统的第一目标不是“让模型记住更多”，而是让记忆能够被验证、追溯、更新、撤销和评估。

## 2. 四个必须分离的概念

### 2.1 Agent State

Agent State 是一次 LangGraph 运行中正在流转的数据，例如本轮用户输入、当前候选记忆、校验错误、检索上下文和最终响应。它属于当前 graph run，不能自动等同于长期记忆。

### 2.2 Checkpoint

Checkpoint 是 LangGraph 对 thread 状态的持久化快照，用于恢复同一个会话或工作流。它解决的是“这个 thread 运行到哪里了”，不是跨用户、跨项目的知识库。

### 2.3 Long-term Memory Store

Long-term Store 保存跨 thread 的可复用记忆。第一版按 namespace 隔离租户、用户、项目和应用，例如：

```text
(tenant_id, user_id, application, project_id, memory_type)
```

它保存结构化 JSON 记录，但不能替代领域数据库、原始文件存储或证据对象存储。

### 2.4 Domain Retrieval

Domain Retrieval 负责从长期记忆中根据查询、主体、时间和来源约束召回证据。它不负责决定记忆是否应该写入，也不负责生成最终答案。

## 3. 第一版记忆对象

第一阶段只实现四类对象：

| 类型 | 含义 | neuro-book 对应物 | 第一版写入策略 |
|---|---|---|---|
| `Episode` | 原始叙事/对话单元 | episode | append-only |
| `Fact` | 从 Episode 抽取的可验证事实 | fact | 证据绑定后写入 |
| `State` | 某个主体在某时点的当前状态 | state | 暂缓，先定义模型 |
| `Asset` | 图片、音频、文档等外部资产的元数据 | future | 暂缓实现 |

每一条 `Fact` 必须包含 `source_episode_id`、原文 `evidence_quote`、摄入时间 `ingested_at`、可选事件时间 `valid_at`、置信度和生命周期状态。没有证据引用的模型输出只能作为 candidate，不能成为 committed memory。

## 4. 第一条 LangGraph 流程

```text
START
  -> ingest_input
  -> extract_candidates
  -> validate_evidence
  -> route_by_validation
      -> persist_candidates（后续实现）
      -> return_validation_errors
  -> END
```

第一阶段只实现 `ingest_input`、`validate_evidence` 和路由；抽取节点先用显式接口接入，持久化节点先用内存 Store。这样每个节点都能单独测试，不会一开始就把模型、数据库和业务逻辑耦合起来。

## 5. 证据优先不变量

1. `evidence_quote` 必须是原始输入的精确子串。
2. `Fact` 的 `source_episode_id` 必须指向当前或已存在的 Episode。
3. 未通过校验的 candidate 不得进入 committed memory。
4. 所有时间字段必须区分摄入时间和事件/故事时间；不能用一个 timestamp 表示两种语义。
5. 任何最终回答都应能够回指召回的 memory id 和原始证据。
6. 删除、撤销和冲突解决必须保留审计事件，不能物理覆盖历史证据。

## 6. 与现有项目的对齐

Chronicle 的 Source→事件/陈述/实体→叙事草稿链路对应 Episode→Fact/State→derived view；其 evidence quote 约束应升级为 schema 校验与 graph invariant。neuro-book 已有双时间轴：`tick` 表示知识边界，`instant` 表示故事时间；Omni Memory 后续应保留这两个字段，而不是退化成单一时间戳。

## 7. 暂不实现的能力

本版本暂不实现混合时序检索、向量数据库、自动遗忘、复杂实体消歧、自循环评估、多模态 embedding 和生产级并发存储。它们会在基础协议、测试和数据集适配稳定后逐个加入。