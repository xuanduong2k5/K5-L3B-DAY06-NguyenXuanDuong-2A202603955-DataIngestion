"""Ingest the selected paper and run the fixed A/B/C retrieval benchmark."""
import csv
import json
import logging
import os
import statistics
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pypdf import PdfReader

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf, normalize_for_match
from .models import Chunk
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("day6")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _pages_from_ranges(ranges: list[list[int]]) -> set[int]:
    pages: set[int] = set()
    for start, end in ranges:
        if start <= 0 or end < start:
            raise ValueError(f"Invalid physical page range: {start}-{end}")
        pages.update(range(start, end + 1))
    return pages


def _validate_questions(questions: list[dict[str, Any]], pages: list[Any], document_id: str) -> None:
    if len(questions) < 20:
        raise ValueError(f"Benchmark needs at least 20 questions; found {len(questions)}")
    splits = {split: sum(q["split"] == split for q in questions) for split in ("dev", "test")}
    if splits["dev"] < 15 or splits["test"] < 5:
        raise ValueError(f"Benchmark split must be at least 15 dev / 5 test; got {splits}")
    filtered = [question for question in questions if question.get("filter")]
    if len(filtered) < 3 or not any(question["split"] == "test" for question in filtered):
        raise ValueError("Benchmark needs at least 3 metadata-filter questions, including a test question")
    if len({question["id"] for question in questions}) != len(questions):
        raise ValueError("Benchmark question IDs must be unique")

    page_text = {page.page: normalize_for_match(page.text) for page in pages}
    page_metadata = {page.page: page.metadata for page in pages}
    for question in questions:
        if question.get("gold_source_id") != document_id:
            raise ValueError(f"Question {question['id']} references an unknown document")
        gold_page = question["gold_page"]
        if gold_page not in page_text:
            raise ValueError(f"Question {question['id']} references excluded page {gold_page}")
        evidence = normalize_for_match(question["evidence_quote"])
        if evidence not in page_text[gold_page]:
            raise ValueError(f"Question {question['id']} evidence is not on page {gold_page}")
        for key, value in (question.get("filter") or {}).items():
            if page_metadata[gold_page].get(key) != value:
                raise ValueError(f"Question {question['id']} filter conflicts with its gold page")


def _build_chunks(pages: list[Any]) -> dict[str, list[Chunk]]:
    configurations = {
        "A": lambda page: fixed_size(page, size=800, overlap=100),
        "B": lambda page: by_paragraph(page, max_size=1200),
        "C": lambda page: by_paragraph(page, max_size=1200),
    }
    return {
        strategy: [chunk for page in pages for chunk in chunker(page)]
        for strategy, chunker in configurations.items()
    }


def _embed_chunks(embedder: MyEmbedder, chunks: list[Chunk], batch_size: int = 32) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        vectors.extend(
            embedder.embed_documents([chunk.text for chunk in chunks[start : start + batch_size]])
        )
    return vectors


def _length_stats(chunks: list[Chunk]) -> dict[str, float | int]:
    lengths = [len(chunk.text) for chunk in chunks]
    return {
        "chunks": len(lengths),
        "min_chars": min(lengths),
        "median_chars": statistics.median(lengths),
        "max_chars": max(lengths),
        "total_chars": sum(lengths),
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError as error:
        raise RuntimeError(f"Required package is missing: {package}") from error


def _run_split(
    strategies: tuple[str, ...],
    questions: list[dict[str, Any]],
    embedder: MyEmbedder,
    store: PgVectorStore,
) -> list[dict[str, Any]]:
    vectors = {question["id"]: embedder.embed_query(question["question"]) for question in questions}
    records = []
    for strategy in strategies:
        for question in questions:
            filters = question.get("filter") if strategy == "C" else None
            hits = store.search(strategy, vectors[question["id"]], top_k=3, filters=filters)
            record = evaluate_query(question, hits)
            record.update(
                {
                    "strategy": strategy,
                    "question": question["question"],
                    "expected_answer": question["expected_answer"],
                    "gold_source_id": question["gold_source_id"],
                    "gold_page": question["gold_page"],
                    "evidence_quote": question["evidence_quote"],
                    "filter": question.get("filter"),
                }
            )
            records.append(record)
    return records


def _write_manual_audits(
    results_dir: Path,
    pages: list[Any],
    chunks_by_strategy: dict[str, list[Chunk]],
    traces: list[dict[str, Any]],
) -> None:
    ordered_pages = sorted({page.page for page in pages})
    sample_indexes = {
        round(index * (len(ordered_pages) - 1) / 9) for index in range(10)
    }
    sample_pages = [ordered_pages[index] for index in sorted(sample_indexes)]
    with (results_dir / "coherence_audit.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["strategy", "physical_page", "chunk_id", "chunk_text", "score_0_1_2", "reason"],
        )
        writer.writeheader()
        for strategy, chunks in chunks_by_strategy.items():
            by_page: dict[int, list[Chunk]] = {}
            for chunk in chunks:
                by_page.setdefault(chunk.page, []).append(chunk)
            for page_number in sample_pages:
                candidates = by_page.get(page_number, [])
                if candidates:
                    chunk = candidates[0]
                    writer.writerow(
                        {
                            "strategy": strategy,
                            "physical_page": page_number,
                            "chunk_id": chunk.chunk_id,
                            "chunk_text": chunk.text,
                            "score_0_1_2": "",
                            "reason": "",
                        }
                    )

    with (results_dir / "grounding_audit.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["strategy", "question_id", "top3_chunk_ids", "score_0_1_2", "reason"],
        )
        writer.writeheader()
        for strategy in ("A", "B", "C"):
            for trace in traces:
                if trace["strategy"] == strategy and trace["split"] == "test":
                    writer.writerow(
                        {
                            "strategy": strategy,
                            "question_id": trace["question_id"],
                            "top3_chunk_ids": ";".join(hit["chunk_id"] for hit in trace["hits"]),
                            "score_0_1_2": "",
                            "reason": "",
                        }
                    )

    with (results_dir / "metadata_audit.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "strategy",
                "question_id",
                "rank",
                "chunk_id",
                "source",
                "physical_page",
                "section",
                "metadata_correct",
                "reason",
            ],
        )
        writer.writeheader()
        for trace in traces:
            if trace["split"] != "test":
                continue
            for rank, hit in enumerate(trace["hits"], start=1):
                writer.writerow(
                    {
                        "strategy": trace["strategy"],
                        "question_id": trace["question_id"],
                        "rank": rank,
                        "chunk_id": hit["chunk_id"],
                        "source": hit["source"],
                        "physical_page": hit["page"],
                        "section": hit["metadata"].get("section", ""),
                        "metadata_correct": "",
                        "reason": "",
                    }
                )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pipeline_started = time.perf_counter()
    run_started_at = datetime.now(timezone.utc).isoformat()
    load_dotenv(ROOT / ".env")
    manifest = _read_json(ROOT / "data" / "manifest.json")
    source_info = manifest["source"]
    document_id = source_info["source_id"]
    pdf_path = ROOT / source_info["local_path"]
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Corpus PDF is missing: {pdf_path}. Download it using the source URL in data/manifest.json."
        )

    expected_page_count = manifest["physical_page_count"]
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) != expected_page_count:
        raise ValueError(
            f"PDF version mismatch: manifest expects {expected_page_count} pages, "
            f"found {len(reader.pages)}"
        )
    pages = load_pdf(
        pdf_path,
        document_id=document_id,
        source=source_info["citation"],
        included_pages=_pages_from_ranges(manifest["included_page_ranges"]),
        section_ranges=manifest["section_ranges"],
    )
    if len(pages) != manifest["content_page_count"]:
        raise ValueError(
            f"Manifest expects {manifest['content_page_count']} readable pages, found {len(pages)}"
        )
    if len(pages) < 30:
        raise ValueError(f"Corpus has only {len(pages)} readable content pages; at least 30 are required")
    questions = _read_json(ROOT / "benchmark" / "questions.json")
    _validate_questions(questions, pages, document_id)

    chunks_by_strategy = _build_chunks(pages)
    if any(not chunks for chunks in chunks_by_strategy.values()):
        raise ValueError("A strategy produced no chunks")
    model_load_started = time.perf_counter()
    embedder = MyEmbedder(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    model_load_seconds = time.perf_counter() - model_load_started
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing; configure starter/.env")
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()
    database_versions = store.version_info()

    results_dir = ROOT / "results"
    strategy_stats: dict[str, Any] = {}
    vectors_by_strategy: dict[str, list[list[float]]] = {}
    for strategy in ("A", "B", "C"):
        chunks = chunks_by_strategy[strategy]
        started = time.perf_counter()
        if strategy == "C":
            vectors = vectors_by_strategy["B"]
        else:
            vectors = _embed_chunks(embedder, chunks)
            vectors_by_strategy[strategy] = vectors
        store.upsert(strategy, chunks, vectors)
        strategy_stats[strategy] = {
            **_length_stats(chunks),
            "ingest_seconds": round(time.perf_counter() - started, 3),
            "embedding_reused_from": "B" if strategy == "C" else None,
        }

    dev_questions = [question for question in questions if question["split"] == "dev"]
    test_questions = [question for question in questions if question["split"] == "test"]
    dev_traces = _run_split(("A", "B", "C"), dev_questions, embedder, store)
    dev_metrics = summarize(dev_traces)
    selected_strategy = max(
        ("A", "B", "C"),
        key=lambda strategy: (
            dev_metrics[f"{strategy}/dev"]["evidence_hit_at_3"]["rate"],
            dev_metrics[f"{strategy}/dev"]["hit_at_1"]["rate"],
            -strategy_stats[strategy]["ingest_seconds"],
        ),
    )
    selection = {
        "selected_strategy": selected_strategy,
        "criterion": [
            "highest dev Evidence Hit@3",
            "then highest dev Hit@1",
            "then shortest ingestion time",
        ],
        "selection_metrics": dev_metrics,
        "test_evaluated_after_selection": False,
    }
    _write_json(results_dir / "selection.json", selection)

    test_traces = _run_split(("A", "B", "C"), test_questions, embedder, store)
    traces = dev_traces + test_traces
    selection["test_evaluated_after_selection"] = True
    _write_json(results_dir / "selection.json", selection)

    summary = summarize(traces)
    _write_json(results_dir / "metrics.json", summary)
    _write_jsonl(results_dir / "traces.jsonl", traces)
    _write_json(
        results_dir / "ingestion_summary.json",
        {
            "document_id": document_id,
            "run_started_at_utc": run_started_at,
            "total_elapsed_seconds": round(time.perf_counter() - pipeline_started, 3),
            "physical_pages": len(reader.pages),
            "readable_content_pages": len(pages),
            "content_characters": sum(len(page.text) for page in pages),
            "model_load_seconds": round(model_load_seconds, 3),
            "embedding_model": embedder.model_name,
            "embedding_dimensions": embedder.dimensions,
            "package_versions": {
                "pypdf": _package_version("pypdf"),
                "psycopg": _package_version("psycopg"),
                "sentence-transformers": _package_version("sentence-transformers"),
            },
            "vector_store": "PostgreSQL + pgvector",
            "database_versions": database_versions,
            "metric": "cosine distance; exact search",
            "cost_usd": 0,
            "strategies": strategy_stats,
            "automatic_filter_compliance": _filter_compliance(traces),
        },
    )
    _write_manual_audits(results_dir, pages, chunks_by_strategy, traces)
    print(json.dumps({"metrics": summary, "ingestion": strategy_stats}, ensure_ascii=False, indent=2))


def _filter_compliance(traces: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {strategy: {"compliant_queries": 0, "filtered_queries": 0} for strategy in ("A", "B", "C")}
    for trace in traces:
        if not trace["filter"]:
            continue
        strategy = trace["strategy"]
        counts[strategy]["filtered_queries"] += 1
        if trace["filter_compliant"]:
            counts[strategy]["compliant_queries"] += 1
    return counts


if __name__ == "__main__":
    main()
