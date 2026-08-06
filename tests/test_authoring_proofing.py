from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest import mock

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud.application import DeterminismContext, GameSession, TakeIntent
from lore2mud.application.contracts import (
    ExamineIntent,
    GameIntent,
    ItemView,
    LoadIntent,
    SaveIntent,
    ViewIntent,
)
from lore2mud.authoring.contracts import (
    AcceptanceScenario,
    AdaptationBoundaries,
    ApprovalRecord,
    CapabilityProofingProjection,
    ConditionOutcome,
    GameBlueprint,
    PlayLength,
    PublicInputDescriptor,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.proofing import (
    ProofingProjectionTooLarge,
    admissible_intent_descriptors,
    build_proofing_projection,
    projection_from_view,
)
from lore2mud.authoring.preview import build_preview
from lore2mud.authoring.project import create_game_project
from lore2mud.authoring.serialization import (
    capability_proofing_to_document,
    canonical_json_bytes,
    game_intent_to_document,
    proofing_to_document,
)
from lore2mud.content import load_content_pack


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CONTENT = ROOT / "examples" / "original_demo"


def _blueprint(*, capabilities: tuple[str, ...] = ()) -> GameBlueprint:
    return GameBlueprint(
        format_version=1,
        blueprint_id="proofing_blueprint",
        title="Public Proofing",
        approval=ApprovalRecord(True, "approval_proofing", "product_owner"),
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
        project_id="proofing_project",
        blueprint=_blueprint(capabilities=capabilities),
        content_root=PUBLIC_CONTENT,
        public_inputs=(
            PublicInputDescriptor("public_outline", "application/json", "Public outline"),
        ),
        trace_records=(
            TraceRecord(
                "trace_public",
                "public_outline",
                "proofing_project",
                "approval_proofing",
            ),
            TraceRecord(
                "trace_private",
                "private_source_123",
                "proofing_project",
                "approval_proofing",
            ),
        ),
        workspace_metadata=(
            WorkspaceMetadataEntry("layout", "C:\\private\\novel\\layout.json"),
        ),
    )


def _registry() -> tuple[dict[str, object], Registry]:
    schemas = {
        document["$id"]: document
        for path in (ROOT / "schemas").glob("*.schema.json")
        for document in [json.loads(path.read_text("utf-8"))]
        if "$id" in document
    }
    return schemas, Registry().with_resources(
        (uri, Resource.from_contents(document)) for uri, document in schemas.items()
    )


def _embedded_intents(view) -> tuple[GameIntent, ...]:
    result: list[GameIntent] = []
    if view.player.recover is not None:
        result.append(view.player.recover)
    result.extend(exit_view.move for exit_view in view.room.exits if exit_view.move)
    result.extend(action for item in view.room.items for action in item.actions)
    result.extend(action for item in view.inventory for action in item.actions)
    result.extend(
        monster.attack_intent
        for monster in view.room.monsters
        if monster.attack_intent is not None
    )
    result.extend(
        character.talk
        for character in view.room.characters
        if character.talk is not None
    )
    for equipped in (view.equipment.hand, view.equipment.body):
        if equipped is not None and equipped.unequip is not None:
            result.append(equipped.unequip)
    result.extend(action.intent for action in view.campaign.actions)
    if view.dialogue is not None:
        result.extend(option.intent for option in view.dialogue.options)
        result.append(view.dialogue.end)
    if view.shop is not None:
        result.extend(action for listing in view.shop.catalog for action in listing.actions)
    return tuple(result)


class ProofingTests(unittest.TestCase):
    def test_projection_is_stable_schema_valid_and_omits_private_workspace_data(self) -> None:
        project = _project()
        first = build_proofing_projection(replace(project, workspace_metadata=()))
        second = build_proofing_projection(project)
        self.assertTrue(first.ok)
        self.assertEqual(first, second)
        projection = first.artifact
        assert projection is not None
        document = proofing_to_document(projection)
        payload = canonical_json_bytes(document)
        self.assertNotIn(b"private_source_123", payload)
        self.assertNotIn(b"private", payload.lower())
        self.assertNotIn(b"layout.json", payload)
        self.assertTrue(
            any(
                edge.source_id == "input:public_outline"
                and edge.target_id == "project:proofing_project"
                and edge.kind == "trace"
                for edge in projection.edges
            )
        )

        schemas, registry = _registry()
        proofing_schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/proofing_projection.schema.json"
        ]
        descriptor_schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/admissible_intent_descriptor.schema.json"
        ]
        Draft202012Validator.check_schema(proofing_schema)
        Draft202012Validator.check_schema(descriptor_schema)
        Draft202012Validator(proofing_schema, registry=registry).validate(document)

    def test_descriptors_are_exactly_the_intents_embedded_in_game_view(self) -> None:
        view = GameSession.from_content_pack(load_content_pack(PUBLIC_CONTENT)).view()
        descriptors = admissible_intent_descriptors(view)
        actual = {
            canonical_json_bytes(game_intent_to_document(item.intent)) for item in descriptors
        }
        expected = {
            canonical_json_bytes(game_intent_to_document(intent))
            for intent in _embedded_intents(view)
        }
        self.assertEqual(actual, expected)
        self.assertFalse(
            any(
                isinstance(item.intent, (SaveIntent, LoadIntent, ViewIntent, ExamineIntent))
                for item in descriptors
            )
        )

    def test_reference_capability_proofing_is_player_safe_and_schema_valid(self) -> None:
        project = _project(capabilities=("reference_counter",))

        first = build_proofing_projection(project)
        second = build_proofing_projection(project)

        self.assertTrue(first.ok)
        self.assertEqual(first, second)
        projection = first.artifact
        self.assertIsInstance(projection, CapabilityProofingProjection)
        assert isinstance(projection, CapabilityProofingProjection)
        self.assertEqual(projection.project_id, project.project_id)
        self.assertEqual(
            [item.capability_id for item in projection.capability_views],
            ["reference_counter"],
        )
        document = capability_proofing_to_document(projection)
        self.assertEqual(document["capability_views"][0]["view"], {"count": 0})
        payload = canonical_json_bytes(document)
        self.assertNotIn(b"private_source_123", payload)
        self.assertNotIn(b"ReferenceCounterImplementation", payload)

        schemas, registry = _registry()
        schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/capability_proofing_projection.schema.json"
        ]
        Draft202012Validator(schema, registry=registry).validate(document)

    def test_admissible_descriptor_limit_rejects_without_truncation(self) -> None:
        view = GameSession.from_content_pack(load_content_pack(PUBLIC_CONTENT)).view()
        oversized_inventory = tuple(
            ItemView(
                id=f"item_{index}",
                name=f"Item {index}",
                description="Public test item",
                quantity=1,
                heal_amount=None,
                slot=None,
                attack_bonus=0,
                defense_bonus=0,
                equipped=False,
                actions=(TakeIntent(f"item_{index}"),),
            )
            for index in range(1025)
        )
        with self.assertRaises(ProofingProjectionTooLarge):
            admissible_intent_descriptors(replace(view, inventory=oversized_inventory))

        project = _project()
        with mock.patch(
            "lore2mud.authoring.proofing.projection_from_view",
            side_effect=ProofingProjectionTooLarge,
        ):
            result = build_proofing_projection(project)
        self.assertFalse(result.ok)
        self.assertIsNone(result.artifact)
        self.assertEqual(result.diagnostics[0].code, "proofing_projection_too_large")

    def test_proofing_text_limit_rejects_instead_of_emitting_invalid_schema(self) -> None:
        project = _project()
        preview = build_preview(project).artifact
        assert preview is not None
        view = GameSession.from_content_pack(load_content_pack(PUBLIC_CONTENT)).view()
        oversized_view = replace(
            view,
            room=replace(view.room, name="x" * 4097),
        )

        with self.assertRaises(ProofingProjectionTooLarge):
            projection_from_view(project, preview, oversized_view)


if __name__ == "__main__":
    unittest.main()
