"""Automatic evidence retrieval metrics and trace preparation."""
from collections import defaultdict
from typing import Any

from .ingestion import normalize_for_match


def _is_evidence_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    if hit["document_id"] != question["gold_source_id"]:
        return False
    gold_pages = question.get("gold_pages", [question["gold_page"]])
    if hit["page"] not in gold_pages:
        return False
    quote = normalize_for_match(question["evidence_quote"])
    return quote in normalize_for_match(hit["text"])


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    hit_flags = [_is_evidence_hit(question, hit) for hit in hits]
    required_filter = question.get("filter")
    filter_compliant = (
        bool(hits)
        and all(
            hit["metadata"].get(key) == value
            for hit in hits
            for key, value in required_filter.items()
        )
        if required_filter
        else None
    )
    return {
        "question_id": question["id"],
        "split": question["split"],
        "hit_at_1": bool(hit_flags and hit_flags[0]),
        "evidence_hit_at_3": any(hit_flags),
        "evidence_hit_flags": hit_flags,
        "filter_compliant": filter_compliant,
        "hits": hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        grouped[(trace["strategy"], trace["split"])].append(trace)

    summary = {}
    for (strategy, split), records in sorted(grouped.items()):
        total = len(records)
        hit1 = sum(record["hit_at_1"] for record in records)
        hit3 = sum(record["evidence_hit_at_3"] for record in records)
        summary[f"{strategy}/{split}"] = {
            "questions": total,
            "hit_at_1": {"hits": hit1, "total": total, "rate": hit1 / total},
            "evidence_hit_at_3": {"hits": hit3, "total": total, "rate": hit3 / total},
        }
    return summary
