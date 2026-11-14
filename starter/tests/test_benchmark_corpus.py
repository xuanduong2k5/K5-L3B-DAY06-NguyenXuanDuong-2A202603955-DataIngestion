import json
import unittest
from pathlib import Path

from pypdf import PdfReader

from src.ingestion import load_pdf
from src.run import _pages_from_ranges, _validate_questions


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
        cls.source = cls.manifest["source"]
        cls.pdf_path = ROOT / cls.source["local_path"]
        if not cls.pdf_path.is_file():
            raise FileNotFoundError(
                f"Download the corpus PDF before running tests: {cls.source['pdf_url']}"
            )
        cls.pages = load_pdf(
            cls.pdf_path,
            cls.source["source_id"],
            cls.source["citation"],
            _pages_from_ranges(cls.manifest["included_page_ranges"]),
            cls.manifest["section_ranges"],
        )
        cls.questions = json.loads(
            (ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8")
        )

    def test_manifest_page_counts_match_extracted_corpus(self) -> None:
        self.assertEqual(len(PdfReader(str(self.pdf_path)).pages), self.manifest["physical_page_count"])
        self.assertEqual(len(self.pages), self.manifest["content_page_count"])

    def test_questions_have_valid_page_evidence_and_splits(self) -> None:
        _validate_questions(self.questions, self.pages, self.source["source_id"])
        self.assertEqual(sum(question["split"] == "dev" for question in self.questions), 15)
        self.assertEqual(sum(question["split"] == "test" for question in self.questions), 5)


if __name__ == "__main__":
    unittest.main()
