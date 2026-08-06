from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from lore2mud.application import DeterminismContext
from lore2mud.authoring.contracts import (
    AcceptanceScenario,
    AdaptationBoundaries,
    ApprovalRecord,
    ConditionOutcome,
    GameBlueprint,
    PlayLength,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.preview import (
    PreviewValidationError,
    build_preview,
    load_preview_document,
)
from lore2mud.authoring.project import create_game_project, validate_project
from lore2mud.authoring.serialization import (
    canonical_json_bytes,
    fingerprint_document,
    preview_to_document,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CONTENT = ROOT / "examples" / "original_demo"


def _blueprint(*, capabilities: tuple[str, ...] = ()) -> GameBlueprint:
    return GameBlueprint(
        format_version=1,
        blueprint_id="preview_blueprint",
        title="Public Preview",
        approval=ApprovalRecord(True, "approval_preview", "product_owner"),
        audience="general",
        genre="fantasy",
        tone="hopeful",
        play_length=PlayLength(5, 10, 20),
        adaptation_boundaries=AdaptationBoundaries(
            ("public-safe original content",),
            ("private source content",),
        ),
        required_game_loops=("explore",),
        acceptance_scenarios=(
            AcceptanceScenario("reach_path", "Reach the public path", ConditionOutcome.WIN),
        ),
        capability_requirement_ids=capabilities,
        asset_requirements=(),
        provenance_requirements=("public_safe",),
        rights_assertions=("original_content",),
        default_determinism=DeterminismContext(7, 11),
    )


def _project(*, capabilities: tuple[str, ...] = ()):
    return create_game_project(
        project_id="preview_project",
        blueprint=_blueprint(capabilities=capabilities),
        content_root=PUBLIC_CONTENT,
    )


class PreviewBuildTests(unittest.TestCase):
    def test_preview_is_deterministic_non_distributable_and_schema_valid(self) -> None:
        project = _project()
        first = build_preview(project)
        second = build_preview(project)

        self.assertTrue(first.ok)
        self.assertEqual(first, second)
        preview = first.artifact
        assert preview is not None
        self.assertEqual(preview.kind, "preview")
        self.assertFalse(preview.sealed)
        self.assertFalse(preview.distributable)
        self.assertFalse(preview.release_evidence)
        document = preview_to_document(preview)
        self.assertEqual(load_preview_document(document), preview)
        self.assertEqual(
            canonical_json_bytes(document),
            canonical_json_bytes(preview_to_document(second.artifact)),
        )

        schema = json.loads(
            (ROOT / "schemas" / "preview_build.schema.json").read_text("utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)

    def test_workspace_metadata_does_not_affect_preview_identity(self) -> None:
        project = _project()
        changed = replace(
            project,
            workspace_metadata=(
                WorkspaceMetadataEntry("layout", "C:\\private\\layout.json"),
            ),
        )
        baseline = build_preview(project)
        with_metadata = build_preview(changed)
        self.assertTrue(baseline.ok)
        self.assertTrue(with_metadata.ok)
        self.assertEqual(baseline.artifact, with_metadata.artifact)

    def test_preview_from_another_engine_version_is_rejected(self) -> None:
        preview = build_preview(_project()).artifact
        assert preview is not None
        changed = replace(preview, engine_version="future-engine", fingerprint="")
        changed = replace(
            changed,
            fingerprint=fingerprint_document(
                preview_to_document(changed, include_fingerprint=False)
            ),
        )

        with self.assertRaisesRegex(PreviewValidationError, "engine_version"):
            load_preview_document(preview_to_document(changed))

    def test_capability_requirement_rejects_after_validation_without_materialization(
        self,
    ) -> None:
        project = _project(capabilities=("v2_dynamic_story",))
        with (
            mock.patch(
                "lore2mud.authoring.preview.validate_project",
                wraps=validate_project,
            ) as validator,
            mock.patch(
                "lore2mud.authoring.preview._materialized_content_pack",
                side_effect=AssertionError("runtime materialization must not run"),
            ),
        ):
            result = build_preview(project)

        validator.assert_called_once_with(project)
        self.assertFalse(result.ok)
        self.assertIsNone(result.artifact)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["capability_requirement_unsupported_v2_2"],
        )
        self.assertEqual(result.diagnostics[0].stage.value, "preview")


if __name__ == "__main__":
    unittest.main()
