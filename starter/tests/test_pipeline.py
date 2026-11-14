import unittest

from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query
from src.models import DocumentPage


class ChunkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = DocumentPage(
            document_id="doc",
            source="source",
            page=1,
            text="First paragraph. Still first.\n\nSecond paragraph. More text.",
            metadata={"section": "Intro"},
        )

    def test_fixed_size_keeps_overlap_and_traceability(self) -> None:
        chunks = fixed_size(self.page, size=20, overlap=5)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].text[-5:] in chunks[1].text)
        self.assertEqual(chunks[0].page, 1)
        self.assertEqual(chunks[0].metadata, {"section": "Intro"})

    def test_paragraph_chunking_keeps_paragraph_boundaries(self) -> None:
        chunks = by_paragraph(self.page, max_size=40)

        self.assertEqual(len(chunks), 2)
        self.assertIn("First paragraph.", chunks[0].text)
        self.assertIn("Second paragraph.", chunks[1].text)


class EvaluationTests(unittest.TestCase):
    def test_evidence_hit_requires_gold_page_and_quote(self) -> None:
        question = {
            "id": "q1",
            "split": "dev",
            "gold_source_id": "doc",
            "gold_page": 2,
            "evidence_quote": "verified fact",
        }
        hit = {
            "document_id": "doc",
            "page": 3,
            "text": "verified fact",
            "metadata": {},
        }

        result = evaluate_query(question, [hit])

        self.assertFalse(result["hit_at_1"])
        self.assertFalse(result["evidence_hit_at_3"])

    def test_missing_filtered_results_are_not_reported_as_compliant(self) -> None:
        question = {
            "id": "q1",
            "split": "test",
            "gold_source_id": "doc",
            "gold_page": 1,
            "evidence_quote": "evidence",
            "filter": {"section": "Intro"},
        }

        result = evaluate_query(question, [])

        self.assertFalse(result["filter_compliant"])


if __name__ == "__main__":
    unittest.main()
