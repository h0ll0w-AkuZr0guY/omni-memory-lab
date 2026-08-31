# 通用记忆平台研究与定位修正

## 研究结论

LangGraph 官方文档将短期线程记忆与长期跨线程记忆明确区分：checkpointer 持久化 graph state，适合 thread-scoped continuity、human-in-the-loop、time travel 和 fault tolerance；store 持久化应用定义的数据，适合跨线程的 facts、preferences 和 shared knowledge。[1]

Mem0 的官方定位是跨 sessions、tools 和 runs 的长期记忆层，并通过 API/SDK、self-hosted server、集成和多层 memory 支持多类应用，而不是绑定单一业务场景。[2] [3]

memU 的公开仓库强调跨 session、agent、device 的共享记忆，并通过 host adapter 将不同 Agent 的 transcript 映射到统一 memory backend；其架构启发是：宿主应用只负责适配输入/注入点，记忆核心负责存储、索引和检索。[4]

Mem0 公开资料还强调 semantic、BM25、entity matching 和 temporal reasoning 的组合，以及通过 source-linked recall 让记忆可追踪；这些能力比单一向量检索更适合长篇小说和通用应用。[3]

## 对 Omni Memory Lab 的定位修正

Omni Memory Lab 不是 neuro-book 专属系统。正确定位是：

> 一个本地优先、证据优先、可审计、可复用、支持文本/文件/图片/多模态资产的通用长期记忆基础设施。它通过 adapter/mapper 接入不同应用；长篇小说是优先验证场景，neuro-book 是第一个真实 consumer，而不是领域边界。

## 通用边界

应用不应直接依赖内部 SQLite 表或 LangGraph state。应用通过 `MemoryAdapter` 将自己的事件、消息、文件、图片和业务实体映射为标准 `MemoryInput`；记忆服务返回稳定的 `MemoryRecord`、`RetrievalResult`、`MutationResult` 和审计事件。

字段分为必填、推荐和扩展三层：

| 层级 | 字段 | 原因 |
|---|---|---|
| 必填 | `memory_id`、`tenant_id`、`namespace`、`memory_type`、`content` 或 `asset_ref`、`source_ref`、`created_at`、`status` | 保证身份、隔离、内容/资产和来源可追踪 |
| 推荐 | `subject_refs`、`valid_time`、`observed_at`、`confidence`、`tags`、`provenance`、`supersedes` | 支持时序、实体、更新、检索和审核 |
| 扩展 | `app_payload`、`schema_version`、`modality_metadata`、`policy` | 支持 neuro-book、客服、个人助手、知识库等不同映射 |

## 应用交互模型

以 neuro-book 为例，应用不直接向数据库写“小说记忆”，而是发出通用操作：

| 应用动作 | 通用操作 | 记忆系统行为 |
|---|---|---|
| 新增角色事实 | `upsert` / `ingest` | 抽取候选、验证 evidence、写入新版本 |
| 用户修改角色设定 | `revise` | 保留旧版本，建立 `supersedes`，重新校验来源 |
| 用户删除一条设定 | `delete` | 默认 soft delete，写审计事件；按策略处理向量和派生资产 |
| 查询角色关系 | `retrieve` / `query` | hybrid + temporal 检索，返回 source citations |
| 上传角色立绘 | `asset.ingest` | 计算 hash、保存 blob 元数据、生成 caption/OCR/embedding 派生物 |
| 图片绑定章节/角色 | `link` | 建立 asset 与 memory/entity/document 的关系 |
| 生成新插图 | `asset.create` | 保存 generation provenance、prompt hash、model、seed/parent refs |

## 多模态路线

图片不应只作为 SQLite 的 metadata 行，也不应把二进制直接塞进关系表。工程上应拆为：

1. **Blob 层**：本地文件系统、S3-compatible object storage 或后续 MinIO，内容按 SHA-256 寻址，支持去重、版本和保留策略。
2. **Asset manifest 层**：记录 `asset_id、media_type、byte_size、sha256、dimensions、created_at、source_ref、tenant_id、storage_uri、status`。
3. **Derived representation 层**：保存 OCR 文本、caption、关键对象/实体、视觉 embedding、缩略图和模型版本；每个派生物都必须有 `derived_from` 和 `pipeline_version`。
4. **Memory link 层**：图片与文本记忆、实体、章节、会话建立可审计的多对多链接。
5. **Retrieval 层**：文本 BM25、文本向量、图像向量、caption/OCR 文本和时间/实体过滤进行分路召回，再统一融合排序。
6. **Answer grounding 层**：答案引用 `memory_id` 和 `asset_id`，必要时返回图片区域或派生文本的 provenance，而不是只给不可解释的相似度。

这条路线允许本地开发阶段使用 SQLite + 本地 blob，规模增大后切换 Postgres/pgvector + S3/MinIO，而不改变应用接口。

## References

[1]: https://docs.langchain.com/oss/python/langgraph/persistence "LangGraph Persistence"
[2]: https://docs.mem0.ai/introduction "Mem0 Documentation: Build AI apps that remember"
[3]: https://github.com/mem0ai/mem0 "mem0ai/mem0 GitHub repository"
[4]: https://github.com/NevaMind-AI/memU "NevaMind-AI/memU GitHub repository"
