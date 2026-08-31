# Omni Memory Lab 工程基线 v0.1

> 审计基线：`a986469 fix: isolate content database for novel evaluation`。
>
> 审计目的：把当前仓库从“分片实验”重新整理为可演进的企业级本地记忆后端工程，并明确已经完成、尚未完成以及下一步的唯一主线。

## 1. 结论先行

当前仓库已经完成一个**可测试的核心算法垂直切片**：本地文档解析、Episode 分片、LLM 候选事实抽取、证据子串校验、SQLite 持久化、文本检索、带引用问答、小说 cutoff/gold span 映射以及离线指标计算均已有代码和测试。

但它目前还不是一个可被 neuro-book 或其他 Agent 直接依赖的“后端记忆系统”，也不是完整的生产级 Agent。仓库缺少服务边界、稳定 API、生命周期管理、请求级可观测性、模型调用审计、任务状态、幂等键、配置校验、迁移策略、权限/租户边界和可操作 README。因此，本轮不再继续增加零散检索功能，而是先把**产品主线和工程边界落盘**。

## 2. 当前代码真实状态

| 层次 | 当前实现 | 当前判断 | 证据 |
|---|---|---|---|
| 配置 | `Settings` 从 `.env` 读取通用 OpenAI-compatible 配置 | 已有基础能力，但缺少启动时可诊断信息 | `src/omni_memory/config/settings.py` |
| LLM 客户端 | `ChatOpenAI`，使用 `api_key/base_url/model/timeout/max_retries` | 真实模型调用链存在 | `src/omni_memory/llm/client.py` |
| 事实抽取 | 单 Episode 与 batch 两种 structured output | 已能调用模型，但失败重试、原始响应、usage、request id 未落盘 | `src/omni_memory/llm/extractor.py`、`batch_extractor.py` |
| 证据校验 | `evidence_quote` 必须是当前 Episode 原文连续子串 | 核心原则正确，但 LLM 生成不合格时整批进入 review | `src/omni_memory/graphs/validation.py`、`stores/commit.py` |
| LangGraph | ingestion graph 与 read-only query graph | 是工作流图，不等同于完整 Agent 产品 | `src/omni_memory/graphs/*.py` |
| 存储 | SQLite committed memories、audit events、assets | 本地原型可用，缺少 schema version、事务边界、索引迁移和并发策略 | `src/omni_memory/stores/sqlite_store.py` |
| 检索 | SQLite 简单文本检索/可插拔协议 | 还没有 BM25、向量、时间过滤、混合排序 | `src/omni_memory/retrieval/*.py` |
| 问答 | 检索后 LLM 生成引用答案，再做 citation grounding | 已有 grounded query slice，但不是服务接口 | `src/omni_memory/graphs/query_graph.py` |
| 数据集 | TXT/EPUB、cutoff、gold span、Recall/MRR/citation/leakage | 评估框架已开始成形，但还没有稳定真实 gold cases 和 CI 门禁 | `src/omni_memory/evaluation/*.py` |
| 多模态 | EPUB 图片元数据写入 assets | 只有资产登记，没有内容理解、派生物、对象存储或图文检索 | `src/omni_memory/schemas/asset.py`、`sqlite_store.py` |
| 后端服务 | 不存在 FastAPI/HTTP/CLI service contract | 当前最大缺口 | 仓库搜索无服务入口 |
| 文档 | `design-v0.md`、`evaluation-v0.md` | 有设计草案，但缺少 README、启动手册、架构图、路线图、验收矩阵 | 根目录没有 README |

## 3. 这次 batch 是否真的调用了 LLM

从代码链路看，`batch_ingest_epub.py` 会调用 `get_chat_model()`，随后进入 `extract_batch()`，其中执行：

```python
structured_model = chat_model.with_structured_output(
    BatchFactExtraction,
    method="json_mode",
)
result = structured_model.invoke(...)
```

因此，若本机 `.env` 中的 `API_KEY`、`BASE_URL` 和 `MODEL` 被正确加载，且命令没有在模型初始化前失败，这条路径就是一次真实的 OpenAI-compatible 网络请求。此次日志中的 `batch_elapsed_seconds=35.07`、同一 batch 返回 7/9 条候选，并出现由模型结果触发的 `quote_not_found`，与“完全没有调用模型”不一致。

但是，当前代码没有保存以下证据，所以不能从仓库反向证明供应商账户的额度统计：原始 HTTP 状态、provider request id、模型响应中的 token usage、重试次数、请求耗时、脱敏后的配置摘要和失败响应。换言之，**调用链存在，调用审计不存在**。用户看到额度未变化，可能是供应商统计延迟、模型/账户路由差异、免费额度口径差异或请求未被目标账户计费；本项目当前没有足够 telemetry 判定是哪一种。

下一阶段必须增加 `ModelCallRecord` 和统一 callback/wrapper，至少记录 `call_id、operation、model、base_url_host、started_at、elapsed_ms、success、retry_count、input_chars、output_chars、usage（若 provider 返回）、error_type、provider_request_id（若可得）`。绝不记录 API key，也不默认保存整段小说正文。

## 4. 当前批处理结果的正确解释

这次运行不是“记忆系统完全失败”，而是暴露了一个真实工程问题：batch LLM 一次为两个 Episode 返回了候选，其中一个 Episode 的至少一条 `evidence_quote` 不是输入 Episode 的精确连续子串，所以证据校验拒绝整条 Episode 的提交。另一个 Episode 成功提交了 9 条记忆。

当前结果应解释为：

| 指标 | 值 | 含义 |
|---|---:|---|
| 输入章节 | 2 | 已使用正文过滤后的章节 |
| 输入 Episode | 2 | 每章按 chunk 切分 |
| LLM batch 请求 | 1 次，按当前代码推断 | 一个请求处理两个 Episode |
| needs review Episode | 1 | 至少一条引用不精确，未写入该 Episode 的事实 |
| committed memories | 9 | 来自另一个 Episode |
| assets | 30 | EPUB 资产元数据登记，不代表图片已被模型理解 |

这里暴露的设计缺陷是：**batch 内一个 Episode 的错误不应该影响另一个 Episode，但单个 Episode 内一条错误事实也不应自动丢弃所有正确事实**。后续应改成逐事实过滤、逐事实审计，并把不合格事实送入 review queue；同时保留 batch 请求和每条 fact 的关联。

## 5. 唯一工程主线

项目后续不再按“再加一个脚本/再加一个指标”的方式推进，而按以下主线推进：

```text
文档/事件输入
    -> Ingestion Service
    -> Episode 标准化与幂等
    -> LangGraph Extraction Workflow
    -> Evidence Validator
    -> Review Queue / Commit Policy
    -> Versioned Memory Store
    -> Hybrid Temporal Retriever
    -> Grounded Query Agent
    -> HTTP API / SDK
    -> Evaluation + Observability + Audit
```

这里的 LangGraph 是**工作流编排层**，不是整个后端。后端应提供服务生命周期、存储、任务和 API；Agent 应通过受控工具访问 Retriever 和 Memory Service，而不是直接持有 SQLite 连接。

## 6. 完成度定义

| 阶段 | 定义 | 当前状态 |
|---|---|---|
| S0 领域模型 | Episode、Candidate、CommittedFact、citation schema | 完成 |
| S1 离线垂直切片 | ingest -> extract -> validate -> store -> query | 基本完成 |
| S2 真实数据实验 | EPUB/TXT 正文、cutoff、gold cases、报告 | 进行中 |
| S3 可用本地后端 | API、任务、幂等、观测、错误与恢复 | 未开始 |
| S4 可用 Agent | tool contract、会话/线程、引用答案、abstention、trace | 部分存在，未服务化 |
| S5 生产级检索 | BM25 + semantic + temporal + rerank + filters | 未开始 |
| S6 多模态记忆 | asset lifecycle、OCR/caption/embedding、引用回溯 | 仅元数据 |
| S7 自循环质量门禁 | 离线数据集、回归阈值、人工 review、CI | 框架存在，门禁未完成 |

当前项目完成度不能写成“完成了记忆系统”。更准确的表述是：**S0 已完成，S1 已完成主要路径，S2 约完成一半，S3-S6 尚未完成，S7 只有基础框架。**

## 7. 下一轮必须交付的最小闭环

下一轮不是继续扩大小说数据量，而是交付一个最小但真实的后端闭环：

1. 增加 `omni_memory.server`，提供 `/health`、`/v1/memories/ingest`、`/v1/memories/search`、`/v1/query` 和 `/v1/runs/{run_id}`。
2. 将当前 LangGraph 封装为 application service；API 不直接操作 graph state 的内部字段。
3. 增加 run/request/call 审计表，记录模型调用状态和错误，但默认不记录原文。
4. 引入 ingestion idempotency key，重复提交同一 Episode 不重复写入记忆。
5. 将 quote 校验改为逐 fact 隔离；正确事实可以提交，错误事实进入 review。
6. 增加一个不依赖 LLM 的 deterministic backend smoke test，以及一个显式 opt-in 的真实 provider smoke test。
7. 更新 README，使新开发者可以在 Windows Python 3.13 环境中完成安装、配置、离线测试、真实模型验证和 API 启动。

只有这一闭环完成后，才进入 BM25、semantic embedding、temporal retrieval 和多模态 pipeline。

## 8. 仓库卫生规则

小说原文、SQLite 数据库、进度 JSONL、候选 gold cases 和任何 API key 均不得提交到 GitHub。仓库只提交代码、schema、脱敏样例、评估协议和不含受版权保护正文的测试夹具。真实小说只在本地处理；报告中只保留统计量、ID、offset 和必要的短引用。

## 9. 验收门槛

下一阶段完成的定义不是“命令跑完”，而是以下条件全部满足：

| 验收项 | 门槛 |
|---|---|
| 离线单测 | `pytest` 全部通过 |
| 静态检查 | `ruff check src tests scripts` 通过 |
| LLM 观测 | 每次真实调用可查 call id、耗时、成功/失败和 usage 可得性 |
| API | health、ingest、search、query、run status 均可调用 |
| 幂等 | 相同 episode 重试不新增重复 committed fact |
| 证据安全 | 任意 committed fact 的 quote 都能在 source span 中定位 |
| 失败隔离 | 一条 fact 失败不丢弃同 Episode 的其他合法 facts |
| 评估 | 至少有一份本地授权小说的脱敏 gold case 和完整 report |
| 文档 | README 能让新环境从安装到 smoke test 无需猜测 |

## References

本报告中的代码判断均基于仓库 `a986469` 的实际文件和提交历史，不依赖外部数据源。
