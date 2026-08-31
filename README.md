# Omni Memory Lab

Omni Memory Lab 是一个**通用、可复用、本地优先、证据优先、可审计的多模态长期记忆基础设施**。它不专属于 neuro-book，也不把任何单一应用的数据结构硬编码进核心层。不同应用通过 adapter/mapper 将自己的事件、消息、文件、图片、实体和业务字段映射到统一记忆协议，再通过稳定接口完成记忆的写入、读取、更新、删除和审计。

长篇小说是本项目的优先验证场景，因为它同时暴露了长期一致性、角色关系、时间线、前文引用、事实更新、版权数据隔离和图文资产管理等复杂问题。neuro-book 是第一个真实 consumer 和适配器场景，而不是项目的领域边界。

## 一句话目标

> 做一套类似 mem0、memU、Zep 和 LangChain memory 可复用能力的底层记忆平台，并在长篇小说与 neuro-book 场景中用真实数据验证其可靠性；核心记忆协议不绑定任何具体应用。

## 核心分层

```text
应用层：neuro-book / coding agent / assistant / knowledge app
    -> Adapter / Mapper：应用事件、消息、文件、图片、实体 -> 通用 MemoryInput
    -> Memory API：ingest / retrieve / update / delete / link / audit
    -> Workflow：LangGraph 抽取、校验、审核、提交和查询编排
    -> Memory Core：版本、来源、时序、实体、策略和租户隔离
    -> Retrieval：BM25 + semantic + multimodal + temporal + rerank
    -> Storage：metadata DB + vector index + blob/object storage
```

LangGraph 是工作流编排层，不是整个后端。长期记忆数据不应混在 graph state 中：短期线程状态使用 checkpoint，跨线程的用户偏好、事实、实体和资产关系使用长期 store。[1]

## 通用记忆协议

核心字段采用“最小必填 + 推荐字段 + 扩展 payload”，避免要求每个应用填写不适用字段：

| 层级 | 字段 | 作用 |
|---|---|---|
| 最小必填 | `memory_id`、`tenant_id`、`namespace`、`memory_type`、`content` 或 `asset_ref`、`source_ref`、`created_at`、`status` | 身份、隔离、内容/资产、来源和生命周期 |
| 推荐 | `subject_refs`、`valid_time`、`observed_at`、`confidence`、`tags`、`provenance`、`supersedes` | 实体、时序、更新、检索和审核 |
| 扩展 | `app_payload`、`schema_version`、`modality_metadata`、`policy` | 承载不同应用的业务字段 |

核心层只保证协议语义，不规定应用必须使用“角色”“章节”或“用户偏好”等具体业务名词。

## 记忆生命周期

应用通过统一操作与底层交互：

| 应用动作 | 通用操作 | 平台行为 |
|---|---|---|
| 写入一条新事实 | `ingest` / `upsert` | 抽取候选、验证 evidence、执行 commit policy、形成版本 |
| 修改已有事实 | `update` / `revise` | 保留旧版本，建立 `supersedes`，重新生成并验证来源 |
| 删除一条事实 | `delete` | 默认 soft delete，记录审计；按 retention policy 清理派生索引 |
| 查询记忆 | `retrieve` | 返回排序结果、来源、时间和可解释分数 |
| 让 Agent 回答 | `query` | 检索后生成 grounded answer，强制 citation 或 abstention |
| 上传图片/文件 | `asset.ingest` | hash 去重、登记 blob、生成派生表示并建立链接 |
| 生成新图片 | `asset.create` | 记录生成模型、prompt hash、seed、父资产和应用来源 |
| 关联图片与事实 | `link` | 建立 asset、memory、entity、document 之间的可审计关系 |

## 多模态设计

图片不是数据库中的一行 metadata，也不应把二进制直接塞进关系表。平台拆分为五层：

1. **Blob 层**保存原始文件，按 SHA-256 寻址，可使用本地文件系统、S3-compatible storage 或 MinIO。
2. **Asset manifest 层**记录媒体类型、大小、hash、尺寸、来源、存储 URI、租户和生命周期状态。
3. **Derived representation 层**保存 OCR、caption、实体/对象、缩略图、视觉 embedding，以及生成这些表示的模型和 pipeline 版本。
4. **Memory link 层**把图片与文本记忆、实体、章节、会话建立可审计多对多关系。
5. **Retrieval/grounding 层**融合文本 BM25、文本向量、图像向量、OCR/caption、实体和时间信号，并在答案中返回 `memory_id`、`asset_id` 及 provenance。

这样本地开发可以先使用 SQLite + 本地 blob，后续切换到 Postgres/pgvector + S3/MinIO 时不改变应用接口。

## neuro-book 如何接入

neuro-book 不直接访问 SQLite，不需要知道内部表结构。它实现一个 adapter，将自己的消息、章节、角色设定、时间线、生成图片和用户修改映射为通用操作：

```text
neuro-book chapter/event
    -> NeuroBookAdapter.to_memory_input(...)
    -> /v1/memories/ingest
    -> committed memory + provenance + version

neuro-book query
    -> /v1/query 或 /v1/memories/search
    -> grounded answer + citations + asset refs

neuro-book edit/delete
    -> /v1/memories/{id}/revise 或 /v1/memories/{id}/delete
    -> new version / tombstone + audit event
```

同一核心接口未来也可以被个人助手、coding agent、客服系统或知识库应用使用。

## 当前真实完成度

| 阶段 | 定义 | 状态 |
|---|---|---|
| S0 | 通用领域模型与证据规则 | 已完成基础版 |
| S1 | 离线 ingest -> extract -> validate -> store -> query | 已完成核心切片 |
| S2 | 授权 TXT/EPUB 真实评估 | 进行中 |
| S3 | 通用 Memory API、任务、幂等和审计 | 尚未完成 |
| S4 | 可复用 Adapter/Mapper 与 Agent tool contract | 尚未完成 |
| S5 | BM25 + semantic + multimodal + temporal retrieval | 尚未完成 |
| S6 | 图片/文件 blob 与派生表示生命周期 | 目前只有资产元数据 |
| S7 | API/模型调用观测、回归门禁和运维文档 | 尚未完成 |

因此当前仓库不是“完成的生产记忆平台”，而是通用平台的核心验证切片。后续每个阶段都要同时提交代码、文档和本地验收命令。

## 本地安装与验证

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\dev.txt
python -m pip check
python -m pytest -q
python -m ruff check src tests scripts
```

配置 `.env`：

```dotenv
API_KEY=your-provider-key
BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-5.3-flash
REQUEST_TIMEOUT_S=180
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=omni-memory-lab
```

真实 LLM smoke test：

```powershell
python scripts\smoke_model.py
```

当前版本会真实调用 `ChatOpenAI.invoke`，但还没有完整记录 provider request id 和 token usage；这将作为 S3 的首要工程任务。小说数据只在本地 `data/raw` 处理，禁止提交原文、图片、SQLite、进度 JSONL、候选 JSONL 和密钥。

## 文档与反馈循环

每次远端提交必须配套一个 `docs/verification-<milestone>.md`：

| 文档部分 | 必须回答的问题 |
|---|---|
| Changed | 这次具体改了哪些文件和行为？ |
| Run | Windows 本地完整命令是什么？ |
| Expected | 成功时应看到什么关键输出？ |
| Failure | 失败时应收集哪些脱敏日志？ |
| Acceptance | 哪些条件满足后才能进入下一阶段？ |
| Feedback | 用户只需反馈哪些字段，不要上传原文或密钥？ |

## 后续主线

先实现通用 Memory API、application service、run/model-call audit、幂等和 update/delete 生命周期；然后实现 Adapter contract；随后实现 hybrid temporal retrieval；最后实现多模态 blob、OCR/caption/embedding、图文链接和 grounded multimodal query。每次变更都会同步提供本地验证文档，确保 GitHub 代码能通过用户的真实 API 和本地授权小说形成闭环。

## References

[1]: https://docs.langchain.com/oss/python/langgraph/persistence "LangGraph Persistence"
[2]: https://docs.mem0.ai/introduction "Mem0 Documentation"
[3]: https://github.com/mem0ai/mem0 "mem0ai/mem0"
[4]: https://github.com/NevaMind-AI/memU "NevaMind-AI/memU"
