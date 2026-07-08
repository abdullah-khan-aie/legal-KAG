from __future__ import annotations

import asyncio
from contextlib import contextmanager

from kag.builder.component.aligner.kag_aligner import KAGAligner
from kag.builder.component.extractor.schema_constraint_extractor import (
    SchemaConstraintExtractor,
)
from kag.builder.component.extractor.summary_extractor import SummaryExtractor
from kag.builder.component.postprocessor.kag_postprocessor import KAGPostProcessor
from kag.builder.component.reader.dict_reader import DictReader
from kag.builder.component.reader.docx_reader import DocxReader
from kag.builder.component.reader.email_reader import EmailReader
from kag.builder.component.reader.markdown_reader import MarkDownReader
from kag.builder.component.reader.mix_reader import MixReader
from kag.builder.component.reader.pdf_reader import PDFReader
from kag.builder.component.reader.txt_reader import TXTReader
from kag.builder.component.reader.xlsx_reader import XlsxReader
from kag.builder.component.splitter.length_splitter import LengthSplitter
from kag.builder.component.vectorizer.batch_vectorizer import BatchVectorizer
from kag.builder.component.writer.graph_store_writer import GraphStoreWriter
from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import SubGraph
from kag.builder.prompt.spg_prompt import (
    SPGEntityPrompt,
    SPGEventPrompt,
    SPGRelationPrompt,
)
from kag.common.tools.search_api.impl.neo4j_search_client import Neo4jSearchClient
from kag.interface import LLMClient, VectorizeModelABC
from src.lodestone.exceptions import (
    ChunkingError,
    DocumentReadError,
    EmbeddingError,
    ExtractionError,
    GraphStoreError,
    LodestoneError,
)

# Bounded capacity of the shared extraction work queue: submission blocks once
# this many items are buffered, applying backpressure instead of letting the
# queue grow without bound.
_EXTRACT_QUEUE_CAPACITY = 100


class IngestionPipeline:
    """Ingest documents into the Neo4j knowledge graph.

    Wires the kag builder stages (read, split, extract, align, vectorize,
    post-process, write) into a single async flow, translating stage failures
    into typed domain errors.
    """

    def __init__(
        self,
        llm: LLMClient,
        embedder: VectorizeModelABC,
        schema_path: str,
        graph_store,
        extractors: list | None = None,
        similarity_threshold: float = 0.9,
        namespace: str = "",
        model_execute_num: int = 1,
    ) -> None:
        # The LLM and embedding clients shared across the pipeline stages.
        self._llm = llm
        self._embed = embedder

        # Extraction concurrency control: a single fixed-size pool of worker
        # coroutines drains a shared, bounded queue. One work item is one
        # (chunk, extractor) pair; at most `model_execute_num` run at once,
        # shared across every in-flight document (the pool is process-global).
        # Remaining items wait in the queue as plain data rather than being
        # spawned as coroutines up front. Workers start lazily on the first
        # ingest (they need a running loop) and live for the process;
        # `_extract_all` enqueues work and awaits the results.
        self._model_execute_num = max(1, model_execute_num)
        self._work_queue: asyncio.Queue | None = None
        self._workers: list[asyncio.Task] = []
        self._workers_lock = asyncio.Lock()

        # 1) reader: auto-routes by file extension (txt/pdf/docx/md/xlsx) or dict input.
        self._reader = MixReader(
            txt_reader=TXTReader(),
            pdf_reader=PDFReader(llm=self._llm),
            docx_reader=DocxReader(llm=self._llm),
            md_reader=MarkDownReader(),
            dict_reader=DictReader(),
            xlsx_reader=XlsxReader(),
            email_reader=EmailReader(),
        )

        # 2) splitter: sliding-window split by character length. Makes no LLM call.
        #    NOTE: we trialled the LLM SemanticSplitter, but its changed chunk
        #    boundaries regressed the multi-hop pipelines' tier-3 detail retrieval
        #    (deep_thought 0.943 -> 0.886 on the doc goldset) while only the
        #    single-shot retriever benefited. Reverted to the length splitter; the
        #    docx/pdf readers already emit heading/outline-aligned chunks, so this
        #    stage just caps oversized ones.
        self._splitter = LengthSplitter(split_length=1500, window_length=150)

        # 3) extractors (run concurrently per chunk). When ``extractors`` is
        #    supplied (the index_list-driven path: each active KAGIndexManager
        #    contributes its extractor via build_extractor_config), those are
        #    used. Otherwise fall back to the default schema_constraint + summary
        #    pair, so direct callers and tests keep working unchanged.
        self._extractors = (
            extractors
            if extractors is not None
            else [
                SchemaConstraintExtractor(
                    llm=self._llm,
                    schema_path=schema_path,
                    ner_prompt=SPGEntityPrompt(schema_path=schema_path),
                    relation_prompt=SPGRelationPrompt(schema_path=schema_path),
                    event_prompt=SPGEventPrompt(schema_path=schema_path),
                ),
                SummaryExtractor(llm_module=self._llm),
            ]
        )

        # 4) align: merge + de-duplicate per-chunk subgraphs.
        self._aligner = KAGAligner()

        # 5) vectorize: embed index-marked fields.
        self._vectorizer = BatchVectorizer(vectorize_model=self._embed, schema_path=schema_path)

        # 6) post-process: filter invalid nodes/edges + Neo4j entity linking.
        self._postprocessor = KAGPostProcessor(
            schema_path=schema_path,
            namespace=namespace,
            similarity_threshold=similarity_threshold,
            search_client=Neo4jSearchClient(graph_store),
        )

        # 7) write: persist the SubGraph to Neo4j. Vector/text indexes are created
        # at startup (bootstrap.initialize_graph_schema), not here.
        self._writer = GraphStoreWriter(graph_store, namespace=namespace)

    @contextmanager
    def _stage(self, error_cls: type[LodestoneError], message: str, source: str):
        """Translate any failure inside a pipeline stage into a typed domain error.

        Raw third-party exceptions are wrapped (with ``from err`` so the original
        traceback is preserved); errors already translated by an earlier stage
        (e.g. read vs split) pass through unchanged.
        """
        try:
            yield
        except LodestoneError:
            raise
        except Exception as err:
            raise error_cls(message, details={"source": source}) from err

    async def _ensure_workers(self) -> None:
        """Lazily start the shared extraction worker pool on the running loop.

        The pool is created once and then shared for the life of the process,
        guarded by a lock so concurrent first-ingest calls start it exactly once.
        """
        if self._work_queue is not None:
            return
        async with self._workers_lock:
            if self._work_queue is not None:
                return
            queue: asyncio.Queue = asyncio.Queue(maxsize=_EXTRACT_QUEUE_CAPACITY)
            loop = asyncio.get_running_loop()
            self._workers = [
                loop.create_task(self._extract_worker(queue))
                for _ in range(self._model_execute_num)
            ]
            self._work_queue = queue

    async def _extract_worker(self, queue: asyncio.Queue) -> None:
        """One pool worker: pull (extractor, chunk, future) items and run them.

        Each worker loops forever pulling items off the queue. Results and
        exceptions are handed back on the per-item future so the submitting
        `_extract_all` can await them in order.
        """
        while True:
            extractor, chunk, future = await queue.get()
            try:
                if not future.done():
                    result = await extractor.ainvoke(chunk)
                    future.set_result(result)
            except Exception as err:  # deliver to the awaiter, keep the worker alive
                if not future.done():
                    future.set_exception(err)
            finally:
                queue.task_done()

    async def _extract_all(self, chunks: list) -> list:
        """Submit every (chunk, extractor) to the shared pool and gather results.

        Enqueue one item per chunk-extractor pair, then collect the futures in
        submission order. Only `model_execute_num` run at once; the rest wait in
        the queue, and submission itself blocks once the queue is full, which
        applies backpressure to the caller.
        """
        await self._ensure_workers()
        assert self._work_queue is not None
        loop = asyncio.get_running_loop()
        futures: list[asyncio.Future] = []
        for chunk in chunks:
            for extractor in self._extractors:
                future: asyncio.Future = loop.create_future()
                await self._work_queue.put((extractor, chunk, future))
                futures.append(future)
        return await asyncio.gather(*futures)

    async def ingest(self, source: str) -> SubGraph:
        """Ingest a document (file path, or a dict for dict_reader) into the graph."""
        # read (IO/LLM-bound) + semantic split run off the event loop
        chunks = await asyncio.to_thread(self._read_and_split, source)

        # extract every chunk with every extractor via the shared worker pool
        # (bounded to model_execute_num, global across documents), then merge.
        with self._stage(ExtractionError, "extraction failed", source):
            subgraph_lists = await self._extract_all(chunks)
            all_subgraphs = [sg for subgraphs in subgraph_lists for sg in subgraphs]
            merged = await asyncio.to_thread(self._aligner.invoke, all_subgraphs)

        # embed index-marked fields (real async vectorizer)
        with self._stage(EmbeddingError, "embedding failed", source):
            merged = (await self._vectorizer.ainvoke(merged))[0]

        # filter + entity-link against the graph store, off the event loop
        with self._stage(GraphStoreError, "post-processing / entity linking failed", source):
            merged = (await asyncio.to_thread(self._postprocessor.invoke, merged))[0]

        # persist to Neo4j
        with self._stage(GraphStoreError, "failed to persist graph", source):
            await asyncio.to_thread(self._writer.invoke, merged)

        return merged

    def ingest_sync(self, source: str) -> SubGraph:
        """Blocking convenience wrapper around ``ingest`` for non-async callers."""
        return asyncio.run(self.ingest(source))

    def _read_and_split(self, source: str) -> list[Chunk]:
        """Read the source (extension-routed) and semantically split it (sync)."""
        try:
            documents = self._reader.invoke(source)
        except Exception as err:
            raise DocumentReadError("failed to read document", details={"source": source}) from err

        chunks: list[Chunk] = []
        try:
            for document in documents:
                chunks.extend(self._splitter.invoke(document))
        except Exception as err:
            raise ChunkingError("failed to split document", details={"source": source}) from err
        return chunks
