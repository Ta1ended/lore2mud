"""Golden V2-2 compatibility checks for the V2-3 empty-capability lane."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from lore2mud.application import (
    DeterminismContext,
    GameSession,
    MoveIntent,
    SaveIntent,
    TakeIntent,
)
from lore2mud.authoring import AgentAuthoringSDK
from lore2mud.authoring.contracts import (
    AuthoringStatus,
    CreatorDecision,
    PreviewBuild,
    ProofingProjection,
    PublicInputDescriptor,
    SimulationReport,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.project import load_blueprint
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    blueprint_bytes,
    canonical_json_bytes,
    project_bytes,
    project_semantic_bytes,
    preview_to_document,
    proofing_to_document,
    simulation_report_to_document,
    typed_value_to_document,
)
from lore2mud.authoring.simulation import load_simulation_request
from lore2mud.content import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "authoring"
CONTENT = ROOT / "examples" / "original_demo"


EXPECTED_ARTIFACT_SHA256 = {
    "blueprint": "4fd8707841ba8f20c713037b52f233f7c058e1f9df13bef8f05a7b1b67ee0e0c",
    "project": "2456b589cd6bc4fc8840cb1f654c729aeac30e38bb6ecbcedc551bff82535d2f",
    "project_semantic": "36576478fcbd1363ce60a664965737be484380f8701d062f4bafbfb75a33a8a8",
    "preview": "6167502a03657c0552c7b2b88d9b5cb7ca12e2e62f8f33a2d4c90c17027f3147",
    "report": "6edbac0c5ac5cc853bdef06722239b4574c53776c85de8317cbe9a2a0db21dcd",
    "proofing": "8ca23a49dd891646ec3286fdfcd2755e7ef142ef1e55f7f7ff74f04238b8bb05",
}

EXPECTED_RESULT_SHA256 = {
    "create_project": "0b5f91dbd1acd0c99655c300af97fa4bd346e6b16bf409692a251c30ab04f55e",
    "validate_project": "a55ab13d8bce390d82e01b326115802462a3da7b041eedeea1dc50bc415c226f",
    "build_preview": "dcb436fd4fc883c808d791ad14c4bce47401c5616fb5ba4c2f6570e40cbbd7f4",
    "simulate": "8f236d6cc09223077cc72af79cae79f700881f433ddd694ab15f028db2740f25",
    "replay": "d2bd074e2a4de5195d327c3ca8ae80c6b276a9bf15455f82d9d3d23678a6ea48",
    "proof": "22fd33e057a0fca6040b8c04dc1dccecde0d125e1191bd74ef37aa9a8a34fbca",
}

EXPECTED_RUNTIME_SHA256 = {
    "initial_view": "10229fd82cd6dc2763d0d3246b16917fb5b7ffad2d6147b3ac287773dce7360e",
    "turn_trace": "8983ccd102deacd6badd7c7009ff42596ba971f0ce19e298e00682ad0b794017",
    "save_v9": "19df21f81127c99b05ff35fce074e066e5da4a4bbd585c0c75cd50e2c8e02c56",
    "web_snapshot": "e62483aad9d282f2699d8c540cc0b8df8f56adc56dd3e545ca0fbaa05f085861",
    "web_trace": "363c3d688655998f53968dcf8028aeb440e5f0a2fb766733f45f904361424f8c",
}


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _typed_project_inputs() -> dict[str, tuple[object, ...]]:
    return {
        "public_inputs": (
            PublicInputDescriptor(
                artifact_id="public_fixture_brief",
                media_type="application/json",
                label="Public fixture brief",
            ),
        ),
        "creator_decisions": (
            CreatorDecision(
                decision_id="keep_opening_public",
                statement="Use only the original public fixture content.",
            ),
        ),
        "trace_records": (
            TraceRecord(
                trace_id="trace_public_opening",
                source_artifact_id="public_fixture_brief",
                target_artifact_id="public_fixture_project",
                decision_id="keep_opening_public",
            ),
        ),
        "workspace_metadata": (
            WorkspaceMetadataEntry(key="proofing_zoom", value="125"),
        ),
    }


@dataclass(frozen=True, slots=True)
class _OptionalCapabilitiesDocument:
    label: str
    legacy_optional: str | None
    capabilities: tuple[object, ...] | None


class V23LegacyCompatibilityTests(unittest.TestCase):
    def test_canonical_typed_serializer_omits_only_absent_capabilities(self) -> None:
        self.assertEqual(
            typed_value_to_document(
                _OptionalCapabilitiesDocument(
                    label="legacy",
                    legacy_optional=None,
                    capabilities=None,
                )
            ),
            {"label": "legacy", "legacy_optional": None},
        )
        self.assertEqual(
            typed_value_to_document(
                _OptionalCapabilitiesDocument(
                    label="capability",
                    legacy_optional=None,
                    capabilities=(),
                )
            ),
            {
                "label": "capability",
                "legacy_optional": None,
                "capabilities": [],
            },
        )

    def test_empty_requirements_keep_v2_2_artifacts_and_result_envelopes(self) -> None:
        sdk = AgentAuthoringSDK()
        blueprint = load_blueprint(FIXTURES / "blueprint.json")
        self.assertEqual(blueprint.capability_requirement_ids, ())
        project_result = sdk.create_project(
            project_id="public_fixture_project",
            blueprint=blueprint,
            content_root=CONTENT,
            **_typed_project_inputs(),
        )
        self.assertEqual(project_result.status, AuthoringStatus.SUCCESS)
        assert project_result.artifact is not None
        project = project_result.artifact
        self.assertEqual(_digest(blueprint_bytes(blueprint)), EXPECTED_ARTIFACT_SHA256["blueprint"])
        self.assertEqual(_digest(project_bytes(project)), EXPECTED_ARTIFACT_SHA256["project"])
        self.assertEqual(
            _digest(project_semantic_bytes(project)),
            EXPECTED_ARTIFACT_SHA256["project_semantic"],
        )

        validation_result = sdk.validate_project(project)
        preview_result = sdk.build_preview(project)
        request = load_simulation_request(FIXTURES / "simulation_request.json")
        report_result = sdk.simulate(project, request)
        assert preview_result.artifact is not None
        assert report_result.artifact is not None
        replay_result = sdk.replay(project, report_result.artifact)
        proof_result = sdk.proof(project)
        assert proof_result.artifact is not None

        self.assertIs(type(preview_result.artifact), PreviewBuild)
        self.assertIs(type(report_result.artifact), SimulationReport)
        self.assertIs(type(proof_result.artifact), ProofingProjection)
        self.assertEqual(
            _digest(canonical_json_bytes(preview_to_document(preview_result.artifact))),
            EXPECTED_ARTIFACT_SHA256["preview"],
        )
        self.assertEqual(
            _digest(canonical_json_bytes(simulation_report_to_document(report_result.artifact))),
            EXPECTED_ARTIFACT_SHA256["report"],
        )
        self.assertEqual(
            _digest(canonical_json_bytes(proofing_to_document(proof_result.artifact))),
            EXPECTED_ARTIFACT_SHA256["proofing"],
        )

        results = (
            project_result,
            validation_result,
            preview_result,
            report_result,
            replay_result,
            proof_result,
        )
        for result in results:
            with self.subTest(operation=result.operation):
                self.assertEqual(
                    _digest(canonical_json_bytes(authoring_result_to_document(result))),
                    EXPECTED_RESULT_SHA256[result.operation],
                )
        self.assertEqual(replay_result.artifact, report_result.artifact)

    def test_empty_requirements_keep_v2_2_runtime_and_web_bytes(self) -> None:
        pack = load_content_pack(CONTENT)
        session = GameSession.from_content_pack(
            pack,
            determinism=DeterminismContext(seed=7, clock=11),
        )
        self.assertEqual(
            _digest(canonical_json_bytes(typed_value_to_document(session.view()))),
            EXPECTED_RUNTIME_SHA256["initial_view"],
        )
        trace = [
            typed_value_to_document(session.submit(TakeIntent("item_spark_lantern"))),
            typed_value_to_document(session.submit(MoveIntent("east"))),
        ]
        self.assertEqual(
            _digest(canonical_json_bytes(trace)), EXPECTED_RUNTIME_SHA256["turn_trace"]
        )

        with tempfile.TemporaryDirectory() as directory:
            save_service = SaveLoadService(pack, Path(directory))
            save_session = GameSession.from_content_pack(
                pack,
                save_service,
                determinism=DeterminismContext(seed=7, clock=11),
            )
            self.assertEqual(
                save_session.submit(SaveIntent("baseline")).status.value,
                "accepted",
            )
            self.assertEqual(
                _digest(save_service.slot_path("baseline").read_bytes()),
                EXPECTED_RUNTIME_SHA256["save_v9"],
            )

        with tempfile.TemporaryDirectory() as directory:
            web = PlayerSession(
                pack,
                SaveLoadService(pack, Path(directory)),
                player_name="Simulator",
                determinism=DeterminismContext(seed=7, clock=11),
            )
            self.assertEqual(
                _digest(canonical_json_bytes(web.snapshot())),
                EXPECTED_RUNTIME_SHA256["web_snapshot"],
            )
            responses = [
                web.dispatch(
                    {"type": "take", "target": "item_spark_lantern", "quantity": 1}
                ),
                web.dispatch({"type": "move", "direction": "east"}),
            ]
            self.assertEqual(
                _digest(canonical_json_bytes(responses)),
                EXPECTED_RUNTIME_SHA256["web_trace"],
            )
            self.assertNotIn("capabilities", web.snapshot())


if __name__ == "__main__":
    unittest.main()
