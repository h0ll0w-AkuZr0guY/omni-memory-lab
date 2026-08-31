# Omni Memory Lab 工程基线 v0.2

> 基线仓库：`a986469`；本次定位修正后文档提交目标为通用多模态记忆基础设施。

## 1. 正确定位

Omni Memory Lab 不是 neuro-book 专属后端。它要实现的是一套类似 mem0、memU、Zep 和 LangChain memory 的**通用长期记忆底层**：应用通过 adapter/mapper 把自己的数据结构映射到统一协议，底层负责记忆的存取、更新、删除、版本、检索、来源、审计和评估。

长篇小说是优先验证场景，因为它集中暴露长期事实、实体关系、时间线、版本冲突、证据引用和图文资产管理问题。neuro-book 是第一个真实 consumer 与适配器，而不是核心模型的业务边界。

## 2. 参考系统带来的设计启发

| 参考 | 值得吸收的能力 | Omni Memory Lab 的对应方向 |
|---|---|---|
| Mem0 | 跨 session/tool/run 的记忆层、应用集成、混合召回、实体与时间信号 | 通用 API、adapter、hybrid temporal retriever |
| memU | 跨 agent/device 的共享 memory backend、host adapter、可检查的 source-linked memory | adapter contract、统一 provenance、外部 Agent 接入 |
| LangGraph | checkpointer 负责 thread-scoped state，store 负责跨线程长期数据 | graph state 与 long-term memory 分离 |
| Zep/同类系统 | 服务化、会话/用户/事实分层、可运营检索 | API、租户/命名空间、审计与生命周期 |

参考资料只用于提炼架构原则，Omni Memory Lab 不复制任何一个项目的业务字段或实现细节。[1] [2] [3] [4]

## 3. 通用领域协议

核心采用“最小必填 + 推荐字段 + 扩展 payload”：

| 层级 | 字段 | 约束 |
|---|---|---|
| 最小必填 | `memory_id`、`tenant_id`、`namespace`、`memory_type`、`content` 或 `asset_ref`、`source_ref`、`created_at`、`status` | 用于身份、隔离、内容/资产和来源追踪 |
| 推荐 | `subject_refs`、`valid_time`、`observed_at`、`confidence`、`tags`、`provenance`、`supersedes` | 支持实体、时间、更新、排序和审核 |
| 扩展 | `app_payload`、`schema_version`、`modality_metadata`、`policy` | 承载具体应用差异，不污染核心语义 |

`content`、`asset_ref` 至少存在其一；`source_ref` 不是可选的。对由模型生成但没有外部原文的记忆，来源必须指向 generation event、模型调用记录或用户确认事件，而不能伪造文本 evidence。

## 4. 统一生命周期

```text
ingest -> extract -> validate -> review/commit
                                -> version/supersede
                                -> retrieve/query
                                -> revise/delete/tombstone
                                -> audit/retention
```

应用层通过 `MemoryService` 访问生命周期，不直接操作 SQLite：

| 操作 | 语义 | 结果 |
|---|---|---|
| `ingest` | 接收事件、文本或资产 | 候选、校验结果、提交版本或 review 状态 |
| `retrieve` | 获取排序后的证据 | `RetrievalResult[]`，包含来源、时间和解释信息 |
| `query` | 以记忆为证据回答问题 | grounded answer、citations 或 abstention |
| `revise` | 修改已知记忆 | 新版本 + `supersedes` + 审计事件 |
| `delete` | 删除逻辑记忆 | tombstone/soft delete；同步索引与派生物策略 |
| `link/unlink` | 建立或解除关系 | memory、asset、entity、document 的关系事件 |
| `audit` | 查看变更和模型调用 | 可追溯、可脱敏、不可静默覆盖 |

neuro-book 的角色、章节、时间线和绘图都只是 adapter 层的映射：角色设定映射为 `memory_type=entity_fact`，章节内容映射为 `source_ref=document/chapter/span`，立绘映射为 `asset_ref`，用户改稿映射为 `revise`，删除操作映射为 `delete`。

## 5. 多模态工程方案

图片能力是本项目区别于仅处理文本记忆的重点，但不会停留在“把图片路径存进 SQLite”：

```text
raw blob
  -> hash/dedup/manifest
  -> OCR + caption + entities + thumbnails + visual embedding
  -> memory/asset/entity/document links
  -> multimodal hybrid retrieval
  -> grounded answer with asset provenance
```

### 5.1 Blob 与 manifest

原始图片和文件使用内容 hash 寻址，放在本地 blob store 或 S3-compatible/MinIO；数据库只保存 `asset_id、sha256、media_type、size、dimensions、storage_uri、tenant_id、source_ref、status`。同一内容不可重复存储，删除时根据引用计数和 retention policy 决定物理清理。

### 5.2 派生表示

每个 OCR、caption、实体识别、缩略图和 embedding 都是有版本的 `DerivedAsset`，至少包含 `derived_from、pipeline_name、pipeline_version、model_name、created_at、status、error`。模型变化后可以重建派生物，不覆盖原始资产，也不让旧 embedding 与新模型混用。

### 5.3 检索与引用

召回层分别计算文本 BM25、文本向量、OCR/caption 向量、视觉向量、实体匹配和时间/命名空间过滤，再使用可解释 fusion/rerank。回答引用必须能回溯到 `memory_id` 或 `asset_id`，图片还应支持缩略图、页码或区域坐标等 provenance。

## 6. 当前真实完成度

| 阶段 | 定义 | 状态 |
|---|---|---|
| S0 | 通用领域模型、证据规则、基础审计 | 基础版已完成 |
| S1 | 离线 ingest -> extract -> validate -> store -> query | 核心切片已完成 |
| S2 | 授权 TXT/EPUB 真实评估 | 进行中 |
| S3 | 通用 Memory API、application service、任务、幂等 | 未完成 |
| S4 | adapter/mapper、Agent tool contract、update/delete | 未完成 |
| S5 | BM25 + semantic + multimodal + temporal retrieval | 未完成 |
| S6 | blob、OCR/caption/embedding、asset lifecycle | 目前只有 EPUB 资产元数据 |
| S7 | model-call observability、回归门禁、运维文档 | 未完成 |

## 7. 下一阶段唯一主线

下一阶段交付顺序固定为：

1. 通用 schemas：`MemoryInput`、`MemoryRecord`、`AssetRecord`、`MutationResult`、`RetrievalResult`、`AuditEvent`。
2. `MemoryService` application boundary：应用不直接依赖 graph state 或 SQLite。
3. HTTP API：health、ingest、search、query、revise、delete、asset ingest、run status。
4. run/request/model-call audit：记录 call id、耗时、状态、重试、usage 可得性、provider request id（如有），不保存 API key，默认不保存原始小说正文。
5. 幂等、版本、soft delete、review queue 和失败恢复。
6. adapter contract 与 neuro-book adapter 参考实现。
7. hybrid temporal retrieval。
8. 多模态资产 pipeline。

## 8. 每次提交必须配套本地验证

因为开发环境拥有真实 API key 和授权小说，而远端开发环境不具备这两项条件，所以每一次 GitHub 代码提交必须同时包含 `docs/verification-<milestone>.md`，文档固定包含：

| 部分 | 内容 |
|---|---|
| Changed | 修改的文件、接口和行为 |
| Setup | Windows Python 3.13 环境要求 |
| Run | 可复制的完整命令 |
| Expected | 成功输出和关键计数 |
| Failure | 失败类别及脱敏日志采集方式 |
| Acceptance | 进入下一阶段的门槛 |
| Feedback | 用户只需反馈的字段；禁止上传 key 和原文 |

## 9. 验收门槛

S3/S4 完成必须同时满足：API 可启动；重复 episode 不产生重复 committed memory；单 fact 校验失败不丢弃同一 Episode 的合法 facts；更新产生新版本并保留旧版本；删除产生 tombstone 和审计；每次 LLM 调用可查 call record；query 返回 citation 或 abstention；README 和 verification 文档能让本地用户独立复现。

## References

[1]: https://docs.langchain.com/oss/python/langgraph/persistence "LangGraph Persistence"
[2]: https://docs.mem0.ai/introduction "Mem0 Documentation"
[3]: https://github.com/mem0ai/mem0 "mem0ai/mem0"
[4]: https://github.com/NevaMind-AI/memU "NevaMind-AI/memU"
