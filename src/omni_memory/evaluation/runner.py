from pathlib import Path
from tempfile import TemporaryDirectory

from omni_memory.evaluation.chunking import split_chapters
from omni_memory.evaluation.cutoff import NovelChapter, apply_cutoff
from omni_memory.evaluation.gold_mapping import map_source_span_to_chunks
from omni_memory.evaluation.ingest import chunks_to_episodes
from omni_memory.evaluation.metrics import answer_metrics, retrieval_metrics
from omni_memory.graphs.memory_graph import build_memory_graph
from omni_memory.graphs.query_graph import build_query_graph
from omni_memory.schemas.evaluation import CutoffPolicy, DatasetManifest, EvaluationCase
from omni_memory.schemas.query import MemoryQuery
from omni_memory.schemas.report import CaseEvaluationResult, EvaluationReport
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


class EvaluationRunner:
    """运行不把 gold 文本传给被测 Agent 的小说记忆评估。"""

    def __init__(self, extraction_model, answer_model, database_path: str | Path | None = None):
        self.extraction_model = extraction_model
        self.answer_model = answer_model
        self.database_path = Path(database_path) if database_path else None

    def run(
        self,
        manifest: DatasetManifest,
        chapters: list[NovelChapter],
        cases: list[EvaluationCase],
        cutoff_policy: CutoffPolicy,
        *,
        top_k: int = 5,
    ) -> EvaluationReport:
        cutoff = apply_cutoff(chapters, cutoff_policy)
        visible_chunks = split_chapters(cutoff.visible_chapters, max_chars=800)
        episodes = chunks_to_episodes(
            visible_chunks,
            ingested_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            source=manifest.dataset_id,
        )

        temporary_directory = None
        if self.database_path is None:
            temporary_directory = TemporaryDirectory()
            database_path = Path(temporary_directory.name) / "evaluation.sqlite3"
        else:
            database_path = self.database_path

        try:
            with SQLiteMemoryStore(database_path) as store:
                ingest_graph = build_memory_graph(
                    model=self.extraction_model,
                    store=store,
                )
                for episode in episodes:
                    ingest_graph.invoke({"episode": episode})

                query_graph = build_query_graph(store, model=self.answer_model)
                case_results: list[CaseEvaluationResult] = []
                for case in cases:
                    gold_memory_ids = self._gold_memory_ids(case, visible_chunks, store)
                    result = query_graph.invoke(
                        {"query": MemoryQuery(query=case.query, top_k=top_k)}
                    )
                    retrieved = result.get("retrieved", [])
                    answer = result["answer"]
                    retrieval = retrieval_metrics(
                        retrieved,
                        gold_memory_ids,
                        k=top_k,
                    )
                    answer_result = answer_metrics(
                        answer,
                        gold_memory_ids,
                        gold_answerable=case.answerable,
                    )
                    leakage = self._leakage_rate(
                        retrieved,
                        cutoff.visible_chapters,
                    )
                    case_results.append(
                        CaseEvaluationResult(
                            case_id=case.case_id,
                            recall_at_k=retrieval.recall_at_k,
                            precision_at_k=retrieval.precision_at_k,
                            mrr=retrieval.mrr,
                            citation_precision=answer_result.citation_precision,
                            citation_recall=answer_result.citation_recall,
                            abstention_correct=answer_result.abstention_correct,
                            temporal_leakage_rate=leakage,
                            status=result["status"],
                        )
                    )

            return self._aggregate(manifest, case_results)
        finally:
            if temporary_directory is not None:
                temporary_directory.cleanup()

    @staticmethod
    def _gold_memory_ids(case, visible_chunks, store) -> set[str]:
        if not case.answerable or not case.gold_source_spans:
            return set()

        ids: set[str] = set()
        for span in case.gold_source_spans:
            try:
                mapping = map_source_span_to_chunks(span, visible_chunks)
            except ValueError:
                # gold 位于 cutoff 之后时，不把未来内容转换成可检索答案。
                continue
            for episode_id in mapping.episode_ids:
                ids.update(
                    memory.memory_id
                    for memory in store.list_by_episode(episode_id)
                )
        return ids

    @staticmethod
    def _leakage_rate(retrieved, visible_chapters) -> float:
        if not retrieved:
            return 0.0
        visible_ids = {chapter.chapter_index for chapter in visible_chapters}
        leaked = sum(
            1
            for item in retrieved
            if item.memory.metadata.get("chapter_index") not in visible_ids
        )
        return leaked / len(retrieved)

    @staticmethod
    def _aggregate(manifest, results):
        count = len(results)
        if count == 0:
            return EvaluationReport(
                dataset_id=manifest.dataset_id,
                dataset_version=manifest.version,
                model_name="injected-models",
                case_count=0,
                mean_recall_at_k=0.0,
                mean_precision_at_k=0.0,
                mean_mrr=0.0,
                mean_citation_precision=0.0,
                mean_citation_recall=0.0,
                abstention_accuracy=0.0,
                temporal_leakage_rate=0.0,
                case_results=[],
            )

        mean = lambda field: sum(getattr(item, field) for item in results) / count
        return EvaluationReport(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.version,
            model_name="injected-models",
            case_count=count,
            mean_recall_at_k=mean("recall_at_k"),
            mean_precision_at_k=mean("precision_at_k"),
            mean_mrr=mean("mrr"),
            mean_citation_precision=mean("citation_precision"),
            mean_citation_recall=mean("citation_recall"),
            abstention_accuracy=sum(item.abstention_correct for item in results) / count,
            temporal_leakage_rate=mean("temporal_leakage_rate"),
            case_results=results,
        )
