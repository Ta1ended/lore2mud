"""Tests for pipeline.chapter_manifests — manifest v2 validation and source binding."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.chapter_manifests import (
    ChapterManifest,
    ChapterManifestEntry,
    ChapterManifestValidationError,
    FactCandidateSourceValidationError,
    validate_chapter_manifest,
    validate_fact_candidate_sources,
)
from pipeline.fact_candidates import FactCandidateDocument, validate_fact_candidate_document

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "chapter_manifests"


def _valid_primary() -> dict:
    return json.loads((FIXTURE_DIR / "valid_primary.json").read_text(encoding="utf-8"))


def _valid_scan() -> dict:
    return json.loads((FIXTURE_DIR / "valid_scan.json").read_text(encoding="utf-8"))


def _single_entry(**overrides: object) -> dict:
    """Minimal valid primary manifest with one chapter."""
    entry: dict = {
        "chapter_id": "chapter_000001",
        "title": "第一章 测试",
        "source_chapter_label": "第一章",
        "source_title": "测试",
        "volume_label": "第一卷",
        "source_offset": 0,
        "source_line": 1,
        "path": "chapter_000001.txt",
        "character_count": 100,
        "sha256": "a" * 64,
        "previous_id": None,
        "next_id": None,
    }
    entry.update(overrides)
    return {
        "format_version": 2,
        "source_encoding": "utf-8-sig",
        "chapter_count": 1,
        "chapters": [entry],
    }


def _scan_entry(**overrides: object) -> dict:
    """Minimal valid scan manifest with one chapter."""
    entry: dict = {
        "chapter_id": "chapter_000001",
        "title": "第一行",
        "source_chapter_label": None,
        "source_title": None,
        "volume_label": None,
        "source_offset": None,
        "source_line": None,
        "path": "chapter_000001.txt",
        "character_count": 50,
        "sha256": "b" * 64,
        "previous_id": None,
        "next_id": None,
    }
    entry.update(overrides)
    return {
        "format_version": 2,
        "source_encoding": None,
        "chapter_count": 1,
        "chapters": [entry],
    }


# ── fixture loading ─────────────────────────────────────────────────────────

class FixtureTests(unittest.TestCase):
    def test_valid_primary_loads(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        self.assertEqual(doc.format_version, 2)
        self.assertEqual(doc.source_encoding, "gbk")
        self.assertEqual(doc.chapter_count, 3)
        self.assertEqual(len(doc.chapters), 3)

    def test_valid_scan_loads(self) -> None:
        doc = validate_chapter_manifest(_valid_scan())
        self.assertIsNone(doc.source_encoding)
        self.assertEqual(doc.chapter_count, 2)
        self.assertEqual(len(doc.chapters), 2)

    def test_primary_entry_fields(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        e = doc.chapters[0]
        self.assertEqual(e.chapter_id, "chapter_000001")
        self.assertEqual(e.source_chapter_label, "第一章")
        self.assertEqual(e.volume_label, "第一卷 雾岭边站")
        self.assertEqual(e.source_offset, 0)
        self.assertEqual(e.source_line, 1)

    def test_scan_entry_nulls(self) -> None:
        doc = validate_chapter_manifest(_valid_scan())
        e = doc.chapters[0]
        self.assertIsNone(e.source_chapter_label)
        self.assertIsNone(e.source_title)
        self.assertIsNone(e.volume_label)
        self.assertIsNone(e.source_offset)
        self.assertIsNone(e.source_line)


# ── frozen ──────────────────────────────────────────────────────────────────

class FrozenTests(unittest.TestCase):
    def test_manifest_frozen(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        with self.assertRaises(AttributeError):
            doc.format_version = 3  # type: ignore[misc]

    def test_entry_frozen(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        with self.assertRaises(AttributeError):
            doc.chapters[0].title = "changed"  # type: ignore[misc]

    def test_chapters_is_tuple(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        self.assertIsInstance(doc.chapters, tuple)

    def test_entry_source_offset_is_int_or_none(self) -> None:
        doc = validate_chapter_manifest(_valid_primary())
        self.assertIsInstance(doc.chapters[0].source_offset, int)
        doc2 = validate_chapter_manifest(_valid_scan())
        self.assertIsNone(doc2.chapters[0].source_offset)


# ── non-dict root ───────────────────────────────────────────────────────────

class NonDictRootTests(unittest.TestCase):
    def test_list_rejected(self) -> None:
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest([1, 2])

    def test_string_rejected(self) -> None:
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest("bad")

    def test_none_rejected(self) -> None:
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(None)

    def test_bool_rejected(self) -> None:
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(True)


# ── root unknown fields ────────────────────────────────────────────────────

class RootUnknownFieldTests(unittest.TestCase):
    def test_unknown_rejected(self) -> None:
        d = _valid_primary()
        d["extra"] = 1
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("未知字段" in i and "extra" in i for i in ctx.exception.issues))


# ── format_version ──────────────────────────────────────────────────────────

class FormatVersionTests(unittest.TestCase):
    def test_version_1_rejected(self) -> None:
        d = _valid_primary()
        d["format_version"] = 1
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_bool_rejected(self) -> None:
        d = _valid_primary()
        d["format_version"] = True
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_missing_rejected(self) -> None:
        d = _valid_primary()
        del d["format_version"]
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)


# ── source_encoding ─────────────────────────────────────────────────────────

class SourceEncodingTests(unittest.TestCase):
    def test_invalid_encoding_rejected(self) -> None:
        d = _valid_primary()
        d["source_encoding"] = "latin-1"
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_null_for_scan(self) -> None:
        d = _valid_scan()
        d["source_encoding"] = None
        doc = validate_chapter_manifest(d)
        self.assertIsNone(doc.source_encoding)

    def test_bool_rejected(self) -> None:
        d = _valid_primary()
        d["source_encoding"] = True
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)


# ── chapter_count ───────────────────────────────────────────────────────────

class ChapterCountTests(unittest.TestCase):
    def test_mismatch_rejected(self) -> None:
        d = _valid_primary()
        d["chapter_count"] = 99
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("chapter_count" in i for i in ctx.exception.issues))

    def test_negative_rejected(self) -> None:
        d = _valid_primary()
        d["chapter_count"] = -1
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_bool_rejected(self) -> None:
        d = _valid_primary()
        d["chapter_count"] = False
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_zero_empty_chapters(self) -> None:
        d = {"format_version": 2, "source_encoding": None, "chapter_count": 0, "chapters": []}
        doc = validate_chapter_manifest(d)
        self.assertEqual(doc.chapter_count, 0)
        self.assertEqual(len(doc.chapters), 0)


# ── chapters array ──────────────────────────────────────────────────────────

class ChaptersArrayTests(unittest.TestCase):
    def test_non_array_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"] = "not-array"
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_non_object_element_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"] = ["not-object"]
        d["chapter_count"] = 1
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_entry_unknown_field_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][0]["bad_field"] = 1
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("未知字段" in i and "bad_field" in i for i in ctx.exception.issues))


# ── chapter_id ──────────────────────────────────────────────────────────────

class ChapterIdTests(unittest.TestCase):
    def test_bad_format_rejected(self) -> None:
        d = _single_entry(chapter_id="ch1")
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_duplicate_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["chapter_id"] = "chapter_000001"
        d["chapter_count"] = 3
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))

    def test_skip_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["chapter_id"] = "chapter_000003"  # skip 002
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("连续递增" in i for i in ctx.exception.issues))

    def test_out_of_order_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][0]["chapter_id"] = "chapter_000002"
        d["chapters"][1]["chapter_id"] = "chapter_000001"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("连续递增" in i for i in ctx.exception.issues))


# ── title ───────────────────────────────────────────────────────────────────

class TitleTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        d = _single_entry(title="   ")
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_missing_rejected(self) -> None:
        d = _single_entry()
        del d["chapters"][0]["title"]
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)


# ── path ────────────────────────────────────────────────────────────────────

class PathTests(unittest.TestCase):
    def test_mismatch_rejected(self) -> None:
        d = _single_entry(path="wrong.txt")
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("path" in i for i in ctx.exception.issues))

    def test_absolute_rejected(self) -> None:
        d = _single_entry(path="/chapter_000001.txt")
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("绝对路径" in i for i in ctx.exception.issues))

    def test_backslash_rejected(self) -> None:
        d = _single_entry(path="chapter_000001\\extra.txt")
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("路径分隔符" in i for i in ctx.exception.issues))

    def test_traversal_rejected(self) -> None:
        d = _single_entry(path="../chapter_000001.txt")
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("路径穿越" in i for i in ctx.exception.issues))

    def test_correct_path_accepted(self) -> None:
        doc = validate_chapter_manifest(_single_entry())
        self.assertEqual(doc.chapters[0].path, "chapter_000001.txt")


# ── character_count ─────────────────────────────────────────────────────────

class CharacterCountTests(unittest.TestCase):
    def test_negative_rejected(self) -> None:
        d = _single_entry(character_count=-1)
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_bool_rejected(self) -> None:
        d = _single_entry(character_count=True)
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_zero_accepted(self) -> None:
        doc = validate_chapter_manifest(_single_entry(character_count=0))
        self.assertEqual(doc.chapters[0].character_count, 0)


# ── sha256 ──────────────────────────────────────────────────────────────────

class Sha256Tests(unittest.TestCase):
    def test_too_short_rejected(self) -> None:
        d = _single_entry(sha256="abc123")
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_uppercase_rejected(self) -> None:
        d = _single_entry(sha256="A" * 64)
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_non_hex_rejected(self) -> None:
        d = _single_entry(sha256="g" * 64)
        with self.assertRaises(ChapterManifestValidationError):
            validate_chapter_manifest(d)

    def test_valid_accepted(self) -> None:
        doc = validate_chapter_manifest(_single_entry(sha256="a" * 64))
        self.assertEqual(doc.chapters[0].sha256, "a" * 64)


# ── previous_id / next_id ──────────────────────────────────────────────────

class ChainTests(unittest.TestCase):
    def test_first_prev_must_be_null(self) -> None:
        d = _valid_primary()
        d["chapters"][0]["previous_id"] = "chapter_000001"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("首章节" in i for i in ctx.exception.issues))

    def test_last_next_must_be_null(self) -> None:
        d = _valid_primary()
        d["chapters"][2]["next_id"] = "chapter_000004"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("末章节" in i for i in ctx.exception.issues))

    def test_middle_prev_null_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["previous_id"] = None
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("非首章节" in i for i in ctx.exception.issues))

    def test_middle_next_null_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["next_id"] = None
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("非末章节" in i for i in ctx.exception.issues))

    def test_wrong_prev_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["previous_id"] = "chapter_000003"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("previous_id" in i for i in ctx.exception.issues))

    def test_wrong_next_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][0]["next_id"] = "chapter_000003"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("next_id" in i for i in ctx.exception.issues))


# ── primary vs scan conditions ──────────────────────────────────────────────

class PrimaryScanConditionTests(unittest.TestCase):
    def test_scan_with_non_null_label_rejected(self) -> None:
        d = _scan_entry()
        d["chapters"][0]["source_chapter_label"] = "第一章"
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("scan 路径" in i for i in ctx.exception.issues))

    def test_scan_with_non_null_offset_rejected(self) -> None:
        d = _scan_entry()
        d["chapters"][0]["source_offset"] = 0
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("scan 路径" in i for i in ctx.exception.issues))

    def test_scan_with_non_null_line_rejected(self) -> None:
        d = _scan_entry()
        d["chapters"][0]["source_line"] = 1
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("scan 路径" in i for i in ctx.exception.issues))

    def test_primary_with_null_label_rejected(self) -> None:
        d = _single_entry()
        d["chapters"][0]["source_chapter_label"] = None
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("source_chapter_label" in i for i in ctx.exception.issues))

    def test_primary_with_null_offset_rejected(self) -> None:
        d = _single_entry()
        d["chapters"][0]["source_offset"] = None
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("source_offset" in i for i in ctx.exception.issues))


# ── offset/line monotonic ──────────────────────────────────────────────────

class MonotonicTests(unittest.TestCase):
    def test_offset_non_increasing_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["source_offset"] = 0  # same as first
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("source_offset" in i and "严格大于" in i for i in ctx.exception.issues))

    def test_line_non_increasing_rejected(self) -> None:
        d = _valid_primary()
        d["chapters"][1]["source_line"] = 1  # same as first
        with self.assertRaises(ChapterManifestValidationError) as ctx:
            validate_chapter_manifest(d)
        self.assertTrue(any("source_line" in i and "严格大于" in i for i in ctx.exception.issues))

    def test_primary_zero_offset_accepted(self) -> None:
        d = _single_entry(source_offset=0, source_line=1)
        doc = validate_chapter_manifest(d)
        self.assertEqual(doc.chapters[0].source_offset, 0)


# ── issues order determinism ───────────────────────────────────────────────

class IssuesOrderTests(unittest.TestCase):
    def test_deterministic(self) -> None:
        d = _valid_primary()
        d["format_version"] = 1
        d["chapters"][0]["title"] = "   "
        results = []
        for _ in range(5):
            try:
                validate_chapter_manifest(d)
            except ChapterManifestValidationError as exc:
                results.append(exc.issues)
        self.assertTrue(all(r == results[0] for r in results))


# ── Schema parseable ───────────────────────────────────────────────────────

class SchemaParseTests(unittest.TestCase):
    def test_schema_is_valid_json(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "chapter_manifest.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn("$schema", schema)
        self.assertIn("properties", schema)
        self.assertIn("$defs", schema)

    def test_schema_has_additional_properties_false(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "chapter_manifest.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertFalse(schema.get("additionalProperties"))
        self.assertFalse(schema["$defs"]["entry"].get("additionalProperties"))

    def test_schema_has_source_encoding_conditional(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "chapter_manifest.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        se = schema["properties"]["source_encoding"]
        self.assertIn("oneOf", se)


# ── source binding ──────────────────────────────────────────────────────────

class SourceBindingTests(unittest.TestCase):
    def _make_manifest(self) -> ChapterManifest:
        return validate_chapter_manifest(_valid_primary())

    def _make_doc(self, source_chapter: str) -> FactCandidateDocument:
        return validate_fact_candidate_document({
            "format_version": 1,
            "source_chapter": source_chapter,
            "extracted_by": "test",
            "candidates": [{
                "candidate_id": "character_test",
                "entity_type": "character",
                "proposed_entity_id": None,
                "display_name": "测试",
                "aliases": [],
                "claims": [{
                    "claim_id": "claim_test",
                    "predicate": "origin",
                    "value": {"kind": "text", "text": "文本"},
                    "source_chapters": [source_chapter],
                    "source_support": "explicit",
                    "certainty": "certain",
                    "inference_basis": None,
                }],
            }],
        })

    def test_valid_source_accepted(self) -> None:
        m = self._make_manifest()
        doc = self._make_doc("chapter_000001")
        result = validate_fact_candidate_sources(m, [doc])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_chapter, "chapter_000001")

    def test_missing_source_rejected(self) -> None:
        m = self._make_manifest()
        doc = self._make_doc("chapter_999999")
        with self.assertRaises(FactCandidateSourceValidationError) as ctx:
            validate_fact_candidate_sources(m, [doc])
        self.assertTrue(any("chapter_999999" in i for i in ctx.exception.issues))

    def test_empty_documents_valid(self) -> None:
        m = self._make_manifest()
        result = validate_fact_candidate_sources(m, [])
        self.assertEqual(result, ())

    def test_multiple_docs_same_chapter_valid(self) -> None:
        m = self._make_manifest()
        doc1 = self._make_doc("chapter_000001")
        doc2 = self._make_doc("chapter_000001")
        result = validate_fact_candidate_sources(m, [doc1, doc2])
        self.assertEqual(len(result), 2)

    def test_order_preserved(self) -> None:
        m = self._make_manifest()
        doc1 = self._make_doc("chapter_000002")
        doc2 = self._make_doc("chapter_000001")
        result = validate_fact_candidate_sources(m, [doc1, doc2])
        self.assertEqual(result[0].source_chapter, "chapter_000002")
        self.assertEqual(result[1].source_chapter, "chapter_000001")

    def test_non_document_rejected(self) -> None:
        m = self._make_manifest()
        with self.assertRaises(FactCandidateSourceValidationError) as ctx:
            validate_fact_candidate_sources(m, ["not-a-document"])  # type: ignore
        self.assertTrue(any("FactCandidateDocument" in i for i in ctx.exception.issues))

    def test_return_is_tuple(self) -> None:
        m = self._make_manifest()
        doc = self._make_doc("chapter_000001")
        result = validate_fact_candidate_sources(m, [doc])
        self.assertIsInstance(result, tuple)

    def test_does_not_modify_input(self) -> None:
        m = self._make_manifest()
        doc = self._make_doc("chapter_000001")
        original_chapter = doc.source_chapter
        validate_fact_candidate_sources(m, [doc])
        self.assertEqual(doc.source_chapter, original_chapter)


# ── build_manifest integration ─────────────────────────────────────────────

class BuildManifestIntegrationTests(unittest.TestCase):
    """Prove that build_manifest's two output paths pass the new validator."""

    def test_primary_path_generates_valid_manifest(self) -> None:
        import tempfile
        from pipeline.split_novel import split_text
        from pipeline.build_manifest import build_manifest

        source = "第一卷 测试\r\n第一章 雾中来客\r\n正文一。\r\n第二章 渡台微光\r\n正文二。\r\n"
        chapters = split_text(source)
        with tempfile.TemporaryDirectory() as td:
            manifest = build_manifest(Path(td), chapters=chapters, source_encoding="utf-8")
        doc = validate_chapter_manifest(manifest)
        self.assertEqual(doc.format_version, 2)
        self.assertEqual(doc.source_encoding, "utf-8")
        self.assertEqual(doc.chapter_count, 2)
        self.assertEqual(len(doc.chapters), 2)
        self.assertEqual(doc.chapters[0].chapter_id, "chapter_000001")
        self.assertEqual(doc.chapters[1].chapter_id, "chapter_000002")
        self.assertEqual(doc.chapters[0].next_id, "chapter_000002")
        self.assertIsNone(doc.chapters[0].previous_id)

    def test_scan_path_generates_valid_manifest(self) -> None:
        import tempfile
        from pipeline.build_manifest import build_manifest

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "chapter_000001.txt").write_text("第一章 内容\n正文一。\n", encoding="utf-8")
            (p / "chapter_000002.txt").write_text("第二章 内容\n正文二。\n", encoding="utf-8")
            manifest = build_manifest(p)
        doc = validate_chapter_manifest(manifest)
        self.assertIsNone(doc.source_encoding)
        self.assertEqual(doc.chapter_count, 2)
        self.assertEqual(doc.chapters[0].chapter_id, "chapter_000001")
        self.assertIsNone(doc.chapters[0].source_chapter_label)

    def test_empty_scan_path_generates_valid_manifest(self) -> None:
        import tempfile
        from pipeline.build_manifest import build_manifest

        with tempfile.TemporaryDirectory() as td:
            manifest = build_manifest(Path(td))
        doc = validate_chapter_manifest(manifest)
        self.assertEqual(doc.chapter_count, 0)
        self.assertEqual(len(doc.chapters), 0)


if __name__ == "__main__":
    unittest.main()
