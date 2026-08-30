# Omni Memory v0 评估协议

## 1. 评估原则

评估必须区分记忆写入质量、记忆检索质量、基于记忆的回答质量和系统工程质量。不能只用最终回答的 LLM-as-a-judge 分数代替所有指标。

所有测试实例必须保存数据版本、模型配置、prompt 版本、随机种子、cutoff、候选记忆数量、召回结果、最终回答和错误信息。评估结果应可在本地重复运行。

## 2. 公开基准

### 2.1 LongMemEval-S

LongMemEval 覆盖 single-session、multi-session、knowledge update、temporal reasoning 和 abstention 等能力。我们先使用小规模固定子集开发，再使用完整测试集做阶段性报告。原始 history 可以包含大量干扰 session，因此必须区分 oracle retrieval、可检索 history 和最终回答三个实验条件。

### 2.2 LoCoMo

LoCoMo 用长程、多 session、带 persona 和 temporal event graph 的对话评估 question answering、event summarization 和 multimodal dialog generation。第一阶段只接入文本 QA 子任务，后续再接入图片和多模态上下文。

## 3. Novel Memory Completion Benchmark

### 3.1 数据许可

优先使用用户拥有版权的小说、明确允许处理的文本或公共领域作品。未经授权的商业小说不能上传到第三方服务或提交到公开仓库。原文默认只存在本地 `data/raw/`，Git 中只提交 manifest、哈希和脱敏评估结果。

### 3.2 文本切分

按卷、章、节建立稳定的 document_id 和 chapter_index。每个 chunk 必须保留 source_document_id、chapter_index、character_offset、ingested_at 和可选 story_time。切分不能跨越无法解释的边界；原文 offset 是证据定位的基础。

### 3.3 Cutoff 与遮蔽

开发集可使用前 80% 作为 ingest、后 20% 作为 gold；正式测试应使用按章节分层的多个 cutoff，并增加随机 span masking。随机策略必须固定 seed 并落盘，避免每次测试生成不同题目。

严禁以下泄漏：把 gold 章节送入记忆抽取器、把 gold 文本放入 prompt、用 gold 章节建立 embedding/BM25 index、用未来章节的实体摘要作为当前状态、或在问题生成后把答案文本写回系统上下文。

### 3.4 查询类型

至少包含：人物/实体属性、事件发生与顺序、跨章节多跳关系、状态变化、伏笔与后文回收、明确不存在的信息、以及需要回到原文证据的引用查询。每个 query 必须保存 gold_answer、gold_source_spans、cutoff 和 query_type。

## 4. 指标

### 4.1 写入指标

测量 candidate-to-committed precision、evidence quote precision、schema validity、duplicate rate、unsupported claim rate 和 invalidation correctness。

### 4.2 检索指标

对 gold source spans 或 gold document/chapter ids 计算 Recall@k、Precision@k、MRR 和 nDCG。对于带 cutoff 的查询，计算 temporal leakage rate；任何来自 cutoff 之后的证据都属于严重错误，而不是普通排序误差。

### 4.3 回答指标

同时报告 Exact Match、token-level F1、citation precision、citation recall、answer groundedness 和 abstention precision/recall。LLM judge 只能作为辅助指标，必须保存 judge prompt、judge model 和原始评分理由。

### 4.4 工程指标

报告 p50/p95 latency、每个 query 的输入/输出 token、模型调用次数、失败率、重试次数、索引构建耗时和 trace completeness。任何质量提升都必须同时观察成本与延迟变化。

## 5. 实验对照组

至少保留 no-memory、full-context、BM25-only、semantic-only、hybrid/oracle 五组对照。第一阶段实际实现 no-memory、BM25-only 和 full-context 的最小适配；混合时序检索在基础协议稳定后加入。

## 6. 质量门禁

任何候选记忆若没有可定位证据，不得进入 committed memory。任何 temporal leakage rate 大于 0 的版本不能进入下一阶段。评估结果必须能由固定数据版本和配置重新生成，且单元测试、数据校验、指标计算和报告生成彼此分离。

## 7. 当前不做的事

暂不下载整套大型数据集、暂不批量调用模型、暂不把用户小说上传到云端，也暂不实现自循环评估。先完成 manifest schema、cutoff/masking 规则和离线指标接口，再选择最小可运行的 LongMemEval-S 子集。

## References

- LongMemEval: https://github.com/xiaowu0162/longmemeval
- LoCoMo: https://snap-research.github.io/locomo/
- LongMemEval paper: https://arxiv.org/abs/2402.17753
- MemoryAgentBench: https://arxiv.org/abs/2507.05257
