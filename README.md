# Omni Memory Lab

Omni Memory Lab 是一个面向 **neuro-book 长篇小说创作场景**的本地优先、证据优先记忆后端实验工程。它的目标不是让模型“尽可能记住”，而是让每条长期记忆都能够被验证、定位、审计、检索、引用、更新和评估。

当前仓库处于 **S1 核心垂直切片已完成、S2 真实小说评估进行中、S3 后端服务尚未开始**的阶段。它还不是可以直接部署到生产环境的完整服务；本 README 既是使用手册，也是当前工程边界的明确声明。

## 项目主线

```text
TXT/EPUB/应用事件
    -> 解析与 Episode 标准化
    -> LangGraph 抽取工作流
    -> evidence_quote 精确校验
    -> review / commit policy
    -> SQLite 版本化记忆
    -> 检索
    -> 带 citation 的 grounded query
    -> 评估、审计与服务 API
```

LangGraph 负责工作流编排，SQLite 负责当前本地持久化，LLM 只负责受约束的候选抽取和答案生成。任何候选事实都不能绕过 evidence 校验直接成为 committed memory。

## 当前已实现

| 模块 | 状态 | 说明 |
|---|---|---|
| Pydantic 领域模型 | 已完成 | Episode、FactCandidate、CommittedFact、Query、Asset |
| LangGraph ingestion | 已完成核心路径 | extract -> validate -> persist/review |
| 证据校验 | 已完成基础版 | evidence quote 必须是 Episode 原文连续子串 |
| SQLite store | 已完成原型版 | memories、audit events、assets |
| Query graph | 已完成基础版 | retrieval -> LLM answer -> citation grounding -> abstention |
| TXT/EPUB 解析 | 已完成 | 本地解析，不上传小说原文 |
| 小说评估框架 | 进行中 | cutoff、gold span、Recall@k、MRR、citation、leakage |
| Hybrid Temporal Retrieval | 未开始 | 后续实现 BM25 + semantic + temporal |
| HTTP 后端服务 | 未开始 | 下一阶段优先交付 |
| 多模态理解 | 未开始 | 当前仅登记 EPUB 图片元数据 |
| LLM 调用审计 | 未完成 | 下一阶段记录 call id、耗时、状态和 usage 可得性 |

完整审计和路线图见 [`docs/engineering-baseline-v0.1.md`](docs/engineering-baseline-v0.1.md)。设计草案见 [`docs/design-v0.md`](docs/design-v0.md)，评估协议见 [`docs/evaluation-v0.md`](docs/evaluation-v0.md)。

## Windows 安装

项目目标环境是 Python 3.13。建议在仓库根目录创建并激活虚拟环境：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\dev.txt
```

验证依赖和代码质量：

```powershell
python -m pip check
python -m pytest -q
python -m ruff check src tests scripts
```

## 配置 OpenAI-compatible 模型

复制配置模板并填写本地 `.env`。`.env` 永远不要提交 Git：

```powershell
Copy-Item .env.example .env
notepad .env
```

配置格式如下：

```dotenv
API_KEY=your-provider-key
BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-5.3-flash
REQUEST_TIMEOUT_S=180
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=omni-memory-lab
```

`BASE_URL`、模型名称和 API key 必须属于同一个 provider 路由。项目使用 `langchain-openai.ChatOpenAI` 的 OpenAI-compatible 接口；初始化模型对象本身不会产生网络请求，真正请求发生在 `invoke` 或 `ainvoke`。

## 明确验证是否调用 LLM

先运行最小真实模型 smoke test：

```powershell
python scripts\smoke_model.py
```

成功时会打印：

```text
model_call=ok
elapsed_seconds=...
response=模型连接成功
```

这只能证明目标接口返回了响应，不能证明供应商账户页面已经即时更新额度。当前版本还没有保存 provider request id 和 token usage；这属于下一阶段的观测缺口。不要把一次业务脚本的长耗时误认为“没有调用”，也不要把 `needs_review` 误认为“没有调用”：模型可能已经返回候选，只是候选的 evidence_quote 没有通过精确子串校验。

## 处理本地授权小说

真实 TXT/EPUB 只在本地 `data/raw` 中处理。不要把小说、数据库、进度文件或完整候选文件提交 Git。先检查来源：

```powershell
python scripts\inspect_sources.py
python scripts\parse_sources.py "data/raw/01我想成为影之强者！.epub"
```

当前正文批处理脚本会排除目录、关键词、录入和校对等前置文档，并写入新的正文专用 SQLite：

```powershell
$env:REQUEST_TIMEOUT_S = "180"
python scripts\batch_ingest_epub.py "data/raw/01我想成为影之强者！.epub" `
  --max-chapters 2 `
  --max-episodes 2 `
  --batch-size 2
```

生成评估候选：

```powershell
python scripts\generate_case_candidates.py `
  "data/raw/01我想成为影之强者！.epub" `
  --limit 2
```

旧数据库不会自动删除。建议将旧库视为历史实验产物，新库命名为 `*-content-batch.sqlite3`，这样可以避免目录文档污染正文评估。

## 运行查询切片

当前查询切片仍是脚本级入口，而不是 HTTP API：

```powershell
python scripts\smoke_query.py
```

它验证检索、带 citation 的答案生成以及证据不足时的 abstention。下一阶段会把这些能力封装为稳定的 application service 和 `/v1/query` API，调用方不再直接操作 LangGraph state 或 SQLite 连接。

## 运行评估

候选 gold case 需要人工检查后，将 `approved` 改为 `true`，再交给评估 runner。评估输入只允许使用 cutoff 之前可见的正文，held-out 内容不能泄漏到被测检索器或 Agent。运行入口：

```powershell
python scripts\run_evaluation.py --help
```

当前评估重点包括 Recall@k、MRR、citation precision 和 temporal leakage。真实报告形成前，不应把自动生成但未人工审批的候选当作 gold truth。

## 目录结构

```text
src/omni_memory/
  config/       环境配置
  evaluation/   TXT/EPUB、cutoff、gold span、metrics、runner
  graphs/       LangGraph ingestion/query workflows
  llm/          OpenAI-compatible client、prompts、extractors
  retrieval/   retriever protocol、SQLite retriever、grounding
  schemas/      Episode、memory、query、asset、evaluation schemas
  stores/       SQLite persistence、commit policy
scripts/        本地 smoke、解析、摄入、候选和评估命令
tests/          unit/integration tests
docs/           设计、评估和工程基线
```

## 后续唯一主线

下一阶段先完成后端闭环，而不是继续堆零散指标：

1. 提供 `/health`、`/v1/memories/ingest`、`/v1/memories/search`、`/v1/query` 和 `/v1/runs/{run_id}`。
2. 将 LangGraph 封装在 application service 后面，建立稳定 request/response schema。
3. 增加 run、request、model-call 审计，记录调用状态、耗时、重试和 usage 可得性，但默认不保存原文。
4. 加入 Episode 幂等键、任务状态和失败恢复。
5. 将 fact 级失败隔离，合法事实提交，非法事实进入 review queue。
6. 在 API 闭环稳定后实现 BM25 + semantic + temporal hybrid retrieval。
7. 最后扩展图片 OCR/caption/embedding 和多模态引用。

## 数据与提交规则

授权小说仍属于受版权保护的本地数据。仓库只提交代码、schema、脱敏测试夹具、统计报告和 offset，不提交小说正文、图片原文件、SQLite、progress JSONL、gold case 原文或 API key。提交前检查：

```powershell
git status --short
```

## 工程基线

截至仓库提交 `a986469`，准确的完成度是：S0 领域模型已完成，S1 离线核心垂直切片基本完成，S2 真实小说评估进行中，S3 可用本地后端未开始，S4 Agent 服务化未完成，S5 混合检索未开始，S6 多模态仅有资产元数据，S7 质量门禁只有基础框架。
