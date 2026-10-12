from __future__ import annotations

import asyncio
import contextvars
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
from src.exceptions import (
    ChunkingError,
    DocumentReadError,
    EmbeddingError,
    Error,
    ExtractionError,
    GraphStoreError,
)
from src.observability import tracing as obs

# Submission blocks once this many items are buffered, so a large corpus cannot
# grow the queue without bound.
_EXTRACT_QUEUE_CAPACITY = 100


class IngestionPipeline:
    """Ingest documents into the Neo4j knowledge graph.

    Wires the kag builder stages into one async flow and translates stage
    failures into typed domain errors.
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
        self._llm = llm
        self._embed = embedder

        # One process-wide pool caps how many extractions run at once across all
        # in-flight documents. Started lazily because it needs a running loop.
        self._model_execute_num = max(1, model_execute_num)
        self._work_queue: asyncio.Queue | None = None
        self._workers: list[asyncio.Task] = []
        self._workers_lock = asyncio.Lock()

        # Routes to the matching reader by file extension.
        self._reader = MixReader(
            txt_reader=TXTReader(),
            pdf_reader=PDFReader(llm=self._llm),
            docx_reader=DocxReader(llm=self._llm),
            md_reader=MarkDownReader(),
            dict_reader=DictReader(),
            xlsx_reader=XlsxReader(),
            email_reader=EmailReader(),
        )

        # Length split, no LLM call. The LLM SemanticSplitter was trialled and
        # its chunk boundaries regressed multi-hop retrieval (0.943 to 0.886),
        # so this only caps chunks the readers already aligned to headings.
        self._splitter = LengthSplitter(split_length=1500, window_length=150)

        # Supplied by the index_list path, one extractor per active index. The
        # default pair keeps direct callers and tests working.
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

        # Merges and de-duplicates the per-chunk subgraphs.
        self._aligner = KAGAligner()

        self._vectorizer = BatchVectorizer(vectorize_model=self._embed, schema_path=schema_path)

        # Drops invalid nodes/edges, then entity-links against the graph store.
        self._postprocessor = KAGPostProcessor(
            schema_path=schema_path,
            namespace=namespace,
            similarity_threshold=similarity_threshold,
            search_client=Neo4jSearchClient(graph_store),
        )

        # Vector and text indexes are created at startup by
        # bootstrap.initialize_graph_schema, not here.
        self._writer = GraphStoreWriter(graph_store, namespace=namespace)

    @contextmanager
    def _stage(self, error_cls: type[Error], message: str, source: str):
        """Wrap any stage failure in a typed domain error.

        Errors already translated by an earlier stage pass through unchanged.
        """
        try:
            yield
        except Error:
            raise
        except Exception as err:
            raise error_cls(message, details={"source": source}) from err

    async def _ensure_workers(self) -> None:
        """Start the shared extraction pool once, guarded against concurrent first calls."""
        if self._work_queue is not None:
            return
        async with self._workers_lock:
            if self._work_queue is not None:
                return
            queue: asyncio.Queue = asyncio.Queue(maxsize=_EXTRACT_QUEUE_CAPACITY)
            loop = asyncio.get_running_loop()
            # Fresh context per worker. The pool starts inside the first
            # document's extract span, and a plain create_task would copy that
            # span into every worker for the life of the process, which
            # re-parents later documents onto the wrong trace.
            self._workers = [
                loop.create_task(self._extract_worker(queue), context=contextvars.Context())
                for _ in range(self._model_execute_num)
            ]
            self._work_queue = queue

    async def _extract_worker(self, queue: asyncio.Queue) -> None:
        """Run queued extractions forever, handing each result back on its future."""
        while True:
            extractor, chunk, future, parent = await queue.get()
            try:
                if not future.done():
                    # The pool is process-global so it holds no per-document
                    # context. parent re-attaches this extraction, and its LLM
                    # calls, to the right document trace. None when tracing is off.
                    if parent is not None:
                        with obs.span(type(extractor).__name__, parent=parent):
                            result = await extractor.ainvoke(chunk)
                    else:
                        result = await extractor.ainvoke(chunk)
                    future.set_result(result)
            except Exception as err:  # hand it to the awaiter, keep the worker alive
                if not future.done():
                    future.set_exception(err)
            finally:
                queue.task_done()

    async def _extract_all(self, chunks: list, parent: dict | None = None) -> list:
        """Submit every chunk and extractor pair to the pool and gather the results.

        Submission blocks while the queue is full, which backpressures the caller.
        """
        await self._ensure_workers()
        assert self._work_queue is not None
        loop = asyncio.get_running_loop()
        futures: list[asyncio.Future] = []
        for chunk in chunks:
            for extractor in self._extractors:
                future: asyncio.Future = loop.create_future()
                await self._work_queue.put((extractor, chunk, future, parent))
                futures.append(future)
        return await asyncio.gather(*futures)

    async def ingest(self, source: str) -> SubGraph:
        """Ingest one document, given a file path or a dict for dict_reader.

        Each stage becomes a child span of the document trace the runner opened.
        """
        # Reading and splitting block, so keep them off the event loop.
        chunks = await asyncio.to_thread(self._read_and_split, source)

        # current_parent lets the detached worker pool attach its spans back to
        # this document.
        with obs.span("extract"), self._stage(ExtractionError, "extraction failed", source):
            subgraph_lists = await self._extract_all(chunks, obs.current_parent())
            all_subgraphs = [sg for subgraphs in subgraph_lists for sg in subgraphs]
            with obs.span("align"):
                merged = await asyncio.to_thread(self._aligner.invoke, all_subgraphs)

        with obs.span("embed"), self._stage(EmbeddingError, "embedding failed", source):
            merged = (await self._vectorizer.ainvoke(merged))[0]

        with (
            obs.span("postprocess"),
            self._stage(GraphStoreError, "post-processing / entity linking failed", source),
        ):
            merged = (await asyncio.to_thread(self._postprocessor.invoke, merged))[0]

        with obs.span("write"), self._stage(GraphStoreError, "failed to persist graph", source):
            await asyncio.to_thread(self._writer.invoke, merged)

        return merged

    def ingest_sync(self, source: str) -> SubGraph:
        """Blocking wrapper around ingest for non-async callers."""
        return asyncio.run(self.ingest(source))

    def _read_and_split(self, source: str) -> list[Chunk]:
        """Read and split the source. Runs in a worker thread; neither stage costs tokens."""
        try:
            with obs.span("read"):
                documents = self._reader.invoke(source)
        except Exception as err:
            raise DocumentReadError("failed to read document", details={"source": source}) from err

        chunks: list[Chunk] = []
        try:
            with obs.span("split"):
                for document in documents:
                    chunks.extend(self._splitter.invoke(document))
        except Exception as err:
            raise ChunkingError("failed to split document", details={"source": source}) from err
        return chunks
