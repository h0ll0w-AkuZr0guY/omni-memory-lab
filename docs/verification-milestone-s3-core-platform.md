# Milestone S3：通用记忆核心后端本地验收

## 本轮目标

本轮把项目从旧的脚本切片推进到第一个通用后端核心：应用可以通过统一协议创建、查询、更新、软删除、恢复和审计记忆；同一条请求可使用幂等键安全重试；图片/文件以 Asset manifest 进入平台；不同应用通过 adapter 映射自己的字段；FastAPI 提供稳定接口；真实 LLM 调用可写入脱敏 model-call 记录。

本轮不宣称已经完成生产级分布式部署，也不宣称已经完成视觉模型 OCR/caption/embedding。当前已经实现本地内容寻址 blob、SHA-256 去重、multipart 上传和 manifest 登记；OCR/caption/embedding 派生 pipeline 将在后续 milestone 实现。

## 代码变更

| 位置 | 变化 |
|---|---|
| `schemas/platform.py` | 通用 `MemoryInput`、`MemoryRecord`、`MemoryMutation`、search、asset、audit、run 和 model-call schema |
| `stores/platform_store.py` | SQLite version history、current projection、idempotency、assets、audit、runs、model calls |
| `services/memory_service.py` | create/update/delete/restore/get/versions/search/asset/audit service boundary |
| `server.py` | `/health`、memory CRUD、search、assets、audit、run、model-call API |
| `adapters/protocol.py` | 通用 adapter contract 与 dict adapter |
| `adapters/neurobook.py` | neuro-book 参考映射，不污染核心领域模型 |
| `llm/observability.py` | 脱敏模型调用记录，保存耗时、状态、usage 可得性和 provider request id |
| `tests/` | 适配器、生命周期、API、资产去重、model-call 成功/失败测试 |

## Windows 3.13 安装

在仓库根目录执行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\dev.txt
python -m pip check
```

如果虚拟环境还没有创建：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\dev.txt
```

## 离线质量验证

```powershell
python -m pytest -q
python -m ruff check src tests scripts
```

预期：

```text
66 passed
All checks passed!
```

测试数量可能因后续补充而增加，但不应减少。FastAPI/Starlette 若打印 deprecation warning，只要退出码为 0 且测试通过即可记录；warning 不能当作测试失败。

## 启动服务

先创建本地服务数据库目录，再启动：

```powershell
python -m uvicorn omni_memory.server:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期：

```text
status  service
------  -------
ok      omni-memory-platform
```

## API 生命周期验收

创建记忆：

```powershell
$body = @{
  tenant_id = "local-test"
  namespace = "novel"
  content = "林默收藏了一张旧照片。"
  memory_type = "episodic"
  source_ref = "manual:test:1"
  idempotency_key = "manual-test-1"
  tags = @("photo")
} | ConvertTo-Json

$created = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/memories `
  -ContentType "application/json" `
  -Body $body
$created
$memoryId = $created.memory_id
```

如果 PowerShell 版本把返回对象包在 `record` 中，则使用 `$created.record.memory_id`；两者差异取决于实际 response model 展开方式，不要手工修改数据库。

重复发送同一个 `idempotency_key`：

```powershell
$replay = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/memories `
  -ContentType "application/json" `
  -Body $body
$replay.idempotent
```

预期为 `True`，并且数据库不新增第二个 current memory。

查询：

```powershell
$query = @{
  tenant_id = "local-test"
  namespace = "novel"
  query = "旧照片"
  top_k = 5
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/memories/search -ContentType "application/json" -Body $query
```

更新：

```powershell
$updateBody = @{
  tenant_id = "local-test"
  namespace = "novel"
  content = "林默收藏了一张旧照片，并把它放进书里。"
  memory_type = "episodic"
  source_ref = "manual:test:2"
  idempotency_key = "manual-test-2"
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/v1/memories/$memoryId" -ContentType "application/json" -Body $updateBody
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/memories/$memoryId/versions?tenant_id=local-test&namespace=novel"
```

版本号应从 1 变为 2，旧版本仍可查询。

删除、恢复和审计：

```powershell
Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8000/v1/memories/$memoryId?tenant_id=local-test&namespace=novel"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/memories/$memoryId/restore?tenant_id=local-test&namespace=novel"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/audit?tenant_id=local-test&namespace=novel&subject_id=$memoryId"
```

审计 action 应包含 `created、updated、deleted、restored`。

## 文件和图片上传验收

当前服务支持两种资产入口：`POST /v1/assets` 登记已经存在的 storage URI，以及 `POST /v1/assets/upload` 接收 multipart 二进制。上传接口会重新计算 SHA-256 和大小，任何不匹配都会返回 422；内容按 hash 写入数据库路径旁的 `*-blobs` 目录，同一 scope 下相同 hash 返回同一 asset。

单独运行接口上传测试：

```powershell
python -m pytest tests/integration/test_platform_api.py -q
```

测试已经覆盖：PNG-like bytes 上传、`file:` storage URI、hash/size 校验和 manifest 返回。真实图片上传时只需要反馈 HTTP 状态、返回的 asset_id、sha256 前 8 位和 storage URI 类型，不要上传图片本体。

## 适配器验收

适配器测试不需要真实 API key：

```powershell
python -m pytest tests/unit/test_adapters.py -q
```

neuro-book 事件只在 adapter 层转换，核心层只看到通用 `MemoryInput`。后续接入 neuro-book 时，应先扩展 adapter 测试，再调用 service；不要在 `MemoryService` 中增加 `chapter_id`、`character_id` 等业务专属字段。

## 真实 LLM 观测验收

配置 `.env` 后运行旧 smoke：

```powershell
python scripts\smoke_model.py
```

本轮的 observability helper 需要在模型调用方传入 `PlatformStore` 才会落盘 call record。当前 batch EPUB ingestion 已经传入统一 `run_id`，完成时会打印 `run_id、run_status、model_call_count`；单 Episode Graph 也支持 `call_store/run_id` 参数。下一步会把 query LangGraph 和 HTTP service 全部接入统一 run context。当前可通过对应单元测试验证成功和失败记录：

```powershell
python -m pytest tests/unit/test_model_observability.py -q
```

预期至少包含一条 `success=True`、一条 `success=False`。使用真实小说批处理后，查询新数据库时应能看到与最终输出中 `model_call_count` 相同数量的记录：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/model-calls"
```

注意：如果批处理使用的 database 不是 API 默认的 `artifacts/platform.sqlite3`，应直接读取对应数据库，或用同一路径启动 API。不要把 API key、小说原文或完整 prompt 贴到反馈中。

## Timeout 与运行审计复验

如果 provider 请求超时，进程可以抛出 `OpenAITimeoutError`，但 observer 仍应写入一条 `success=False` 的 model-call。使用同一数据库检查：

```powershell
python -c "from omni_memory.stores.platform_store import PlatformStore; s=PlatformStore(r'artifacts/observability-test.sqlite3'); print([(c.run_id,c.operation,c.model,c.provider_host,c.success,c.error_type) for c in s.list_model_calls()]); print([(r.run_id,r.operation,r.status,r.error_type,r.counters) for r in s.list_runs()]); s.close()"
```

正常失败记录应包含 `error_type=OpenAITimeoutError`，而不应丢失。成功调用应显示配置中的模型名和 provider host，例如 `glm-5.3-flash` 与 `open.bigmodel.cn`；如果仍显示 `unknown-model` 或 `provider`，说明调用方没有传入原始 chat model。

HTTP 查询也支持：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/model-calls"
```

不要把 API key、小说原文或完整 prompt 贴到反馈中。

## 反馈格式

请只反馈以下脱敏字段：

```text
python_version=
pytest_result=
ruff_result=
health_result=
create_status=
replay_idempotent=
search_hit_count=
update_version=
delete_lifecycle=
restore_lifecycle=
audit_actions=
model_call_success=
model_call_failure_type=
elapsed_seconds=
```

如果失败，请同时给出异常类型、最后 20 行 traceback 和请求路径；不要提供 API key、`.env` 内容、小说原文、完整图片或数据库文件。

## 本轮验收门槛

本 milestone 只有在以下条件同时满足时才算通过：

| 项目 | 通过条件 |
|---|---|
| 回归 | 全部 pytest 通过 |
| 静态检查 | Ruff 通过 |
| 幂等 | 相同 key 重试不重复写入 |
| 版本 | update 保留旧版本且 version 递增 |
| 删除 | delete 是 soft delete，audit 有事件 |
| 恢复 | restore 恢复 active 状态 |
| 隔离 | tenant/namespace 不能互相检索 |
| 资产 | 相同 sha256 在同一 scope 去重，上传内容 hash/size 校验通过 |
| 观测 | 模型成功/失败均可写 call record |
| 文档 | 本文件命令可在 Windows 本地复现 |
