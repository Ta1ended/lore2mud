"""Public wrapper-shape tests for the V2-3 authoring capability lane."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import cast
import unittest

from lore2mud.application import MoveIntent
from lore2mud.authoring.contracts import (
    CAPABILITY_PREVIEW_IDENTITY_SCOPE,
    CAPABILITY_REPORT_IDENTITY_SCOPE,
    AuthoringStatus,
    CapabilityAuthoringResult,
    CapabilityPreview,
    CapabilityProofingProjection,
    CapabilitySimulationCheckpoint,
    CapabilitySimulationReport,
    CapabilitySimulationRequest,
    CapabilitySimulationTurn,
    PreviewBuild,
    ProofingProjection,
    SimulationOutcome,
    SimulationReport,
)
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    capability_preview_to_document,
    capability_proofing_to_document,
    capability_simulation_report_to_document,
    capability_simulation_request_to_document,
)
from lore2mud.capabilities.contracts import (
    CapabilityIntent,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    ResolvedCapability,
    ResolvedCapabilityPlan,
)
from lore2mud.capabilities.semver import SemanticVersion
from lore2mud.capabilities.serialization import canonical_json_object


SHA256 = "1" * 64


def _base_preview() -> PreviewBuild:
    return PreviewBuild(
        format_version=1,
        preview_id="preview_public",
        project_id="project_public",
        blueprint_sha256=SHA256,
        project_sha256=SHA256,
        engine_version="0.0.0",
        content_files=(),
        fingerprint=SHA256,
    )


def _base_report() -> SimulationReport:
    return SimulationReport(
        format_version=1,
        project_id="project_public",
        blueprint_sha256=SHA256,
        project_sha256=SHA256,
        preview_fingerprint=SHA256,
        request_sha256=SHA256,
        engine_version="0.0.0",
        seed=7,
        clock=11,
        player_name="Simulator",
        initial_state_sha256=SHA256,
        final_state_sha256=SHA256,
        initial_view_sha256=SHA256,
        final_view_sha256=SHA256,
        turns=(),
        condition_results=(),
        outcome=SimulationOutcome.UNDETERMINED,
        witness_trace=(),
        replay_verified=True,
        checkpoints=(),
        fingerprint=SHA256,
    )


def _base_proofing() -> ProofingProjection:
    return ProofingProjection(
        format_version=1,
        project_id="project_public",
        preview_fingerprint=SHA256,
        nodes=(),
        edges=(),
        admissible_intents=(),
    )


class AuthoringCapabilityContractTests(unittest.TestCase):
    def test_public_wrapper_field_order_is_frozen(self) -> None:
        expected = {
            CapabilitySimulationRequest: (
                "format_version",
                "seed",
                "clock",
                "player_name",
                "steps",
                "conditions",
                "checkpoint_after_steps",
            ),
            CapabilityPreview: (
                "format_version",
                "base_preview",
                "resolved_plan",
                "plan_sha256",
                "initial_states",
                "initial_state_sha256",
                "engine_version",
                "fingerprint",
                "kind",
                "sealed",
                "distributable",
                "release_evidence",
                "identity_scope",
            ),
            CapabilitySimulationTurn: (
                "index",
                "step",
                "status",
                "rejection_code",
                "event_sha256",
                "view_sha256",
                "capability_state_sha256",
                "event_sequence_after",
            ),
            CapabilitySimulationCheckpoint: (
                "after_step",
                "checkpoint_sha256",
                "restored_state_sha256",
                "restored_view_sha256",
                "restored_event_sequence",
                "equivalent",
            ),
            CapabilitySimulationReport: (
                "format_version",
                "project_id",
                "base_report",
                "request_sha256",
                "capability_preview_fingerprint",
                "plan_sha256",
                "initial_capability_state_sha256",
                "final_capability_state_sha256",
                "turns",
                "witness_trace",
                "capability_event_sha256",
                "capability_view_sha256",
                "replay_verified",
                "checkpoints",
                "fingerprint",
                "identity_scope",
            ),
            CapabilityProofingProjection: (
                "format_version",
                "project_id",
                "capability_preview_fingerprint",
                "base_proofing",
                "capability_views",
                "fingerprint",
                "diagnostics",
            ),
            CapabilityAuthoringResult: (
                "format_version",
                "operation",
                "status",
                "artifact",
                "diagnostics",
                "exit_code",
                "kind",
            ),
        }
        for contract, names in expected.items():
            with self.subTest(contract=contract.__name__):
                self.assertEqual(tuple(field.name for field in fields(contract)), names)

    def test_request_and_result_defaults_are_bounded_and_frozen(self) -> None:
        request = CapabilitySimulationRequest(
            format_version=1,
            seed=7,
            clock=11,
            player_name="Simulator",
            steps=(),
        )
        result = CapabilityAuthoringResult[object](
            format_version=1,
            operation="simulate",
            status=AuthoringStatus.SUCCESS,
            artifact=object(),
            diagnostics=(),
            exit_code=0,
        )

        self.assertEqual(request.conditions, ())
        self.assertEqual(request.checkpoint_after_steps, ())
        self.assertEqual(result.kind, "capability_authoring_result")
        self.assertTrue(result.ok)
        with self.assertRaises(FrozenInstanceError):
            request.seed = 8  # type: ignore[misc]

    def test_identity_scope_constants_are_explicit(self) -> None:
        self.assertEqual(
            CAPABILITY_PREVIEW_IDENTITY_SCOPE,
            "capability_preview_reproducibility_only",
        )
        self.assertEqual(
            CAPABILITY_REPORT_IDENTITY_SCOPE,
            "capability_simulation_reproducibility_only",
        )

    def test_wrapper_serializers_use_the_core_hook_and_preserve_base_artifacts(
        self,
    ) -> None:
        version = SemanticVersion.parse("1.0.0")
        state = CapabilityStateEntry(
            capability_id="reference_counter",
            version=version,
            namespace="reference_counter",
            state=canonical_json_object({"count": 0}),
        )
        plan = ResolvedCapabilityPlan(
            format_version=1,
            requirement_ids=("reference_counter",),
            capabilities=(
                ResolvedCapability(
                    capability_id="reference_counter",
                    version=version,
                    safety_level=CapabilitySafetyLevel.L1,
                    state_namespace="reference_counter",
                    descriptor_sha256=SHA256,
                ),
            ),
            dependency_edges=(),
            migrations=(),
            initial_states=(state,),
            catalog_sha256=SHA256,
            fingerprint=SHA256,
        )
        capability_step = CapabilityIntent(
            capability_id="reference_counter",
            action_id="increment",
            parameters=canonical_json_object({"amount": 2}),
        )
        capability_view = CapabilityPlayerViewEntry(
            capability_id="reference_counter",
            version=version,
            view=canonical_json_object({"count": 2}),
            admissible_intents=(capability_step,),
        )
        request = CapabilitySimulationRequest(
            format_version=1,
            seed=7,
            clock=11,
            player_name="Simulator",
            steps=(MoveIntent("east"), capability_step),
        )
        preview = CapabilityPreview(
            format_version=1,
            base_preview=_base_preview(),
            resolved_plan=plan,
            plan_sha256=SHA256,
            initial_states=(state,),
            initial_state_sha256=SHA256,
            engine_version="0.0.0",
            fingerprint=SHA256,
        )
        turns = (
            CapabilitySimulationTurn(
                index=0,
                step=MoveIntent("east"),
                status="accepted",
                rejection_code=None,
                event_sha256=SHA256,
                view_sha256=SHA256,
                capability_state_sha256=SHA256,
                event_sequence_after=1,
            ),
            CapabilitySimulationTurn(
                index=1,
                step=capability_step,
                status="accepted",
                rejection_code=None,
                event_sha256=SHA256,
                view_sha256=SHA256,
                capability_state_sha256=SHA256,
                event_sequence_after=2,
            ),
        )
        report = CapabilitySimulationReport(
            format_version=1,
            project_id="project_public",
            base_report=_base_report(),
            request_sha256=SHA256,
            capability_preview_fingerprint=SHA256,
            plan_sha256=SHA256,
            initial_capability_state_sha256=SHA256,
            final_capability_state_sha256=SHA256,
            turns=turns,
            witness_trace=turns,
            capability_event_sha256=SHA256,
            capability_view_sha256=SHA256,
            replay_verified=True,
            checkpoints=(
                CapabilitySimulationCheckpoint(
                    after_step=2,
                    checkpoint_sha256=SHA256,
                    restored_state_sha256=SHA256,
                    restored_view_sha256=SHA256,
                    restored_event_sequence=2,
                    equivalent=True,
                ),
            ),
            fingerprint=SHA256,
        )
        proofing = CapabilityProofingProjection(
            format_version=1,
            project_id="project_public",
            capability_preview_fingerprint=SHA256,
            base_proofing=_base_proofing(),
            capability_views=(capability_view,),
            fingerprint=SHA256,
        )
        result = CapabilityAuthoringResult[object](
            format_version=1,
            operation="build_preview",
            status=AuthoringStatus.SUCCESS,
            artifact=preview,
            diagnostics=(),
            exit_code=0,
        )

        request_document = capability_simulation_request_to_document(request)
        preview_document = capability_preview_to_document(preview)
        preview_without_fingerprint = capability_preview_to_document(
            preview, include_fingerprint=False
        )
        report_document = capability_simulation_report_to_document(report)
        proofing_document = capability_proofing_to_document(proofing)
        result_document = authoring_result_to_document(result)

        self.assertEqual(
            request_document["steps"],
            [
                {"type": "move", "direction": "east"},
                {
                    "capability_id": "reference_counter",
                    "action_id": "increment",
                    "parameters": {"amount": 2},
                },
            ],
        )
        resolved_plan_document = cast(
            dict[str, object], preview_document["resolved_plan"]
        )
        self.assertEqual(
            resolved_plan_document["requirement_ids"], ["reference_counter"]
        )
        self.assertEqual(
            preview_document["initial_states"],
            [
                {
                    "capability_id": "reference_counter",
                    "version": "1.0.0",
                    "namespace": "reference_counter",
                    "state": {"count": 0},
                }
            ],
        )
        base_preview_document = cast(
            dict[str, object], preview_document["base_preview"]
        )
        self.assertEqual(base_preview_document["kind"], "preview")
        self.assertNotIn("fingerprint", preview_without_fingerprint)
        turn_documents = cast(
            list[dict[str, object]], report_document["turns"]
        )
        self.assertEqual(
            turn_documents[1]["step"],
            {
                "capability_id": "reference_counter",
                "action_id": "increment",
                "parameters": {"amount": 2},
            },
        )
        base_report_document = cast(
            dict[str, object], report_document["base_report"]
        )
        self.assertEqual(
            base_report_document["identity_scope"],
            "simulation_reproducibility_only",
        )
        self.assertEqual(
            proofing_document["capability_views"],
            [
                {
                    "capability_id": "reference_counter",
                    "version": "1.0.0",
                    "view": {"count": 2},
                    "admissible_intents": [
                        {
                            "capability_id": "reference_counter",
                            "action_id": "increment",
                            "parameters": {"amount": 2},
                        }
                    ],
                }
            ],
        )
        self.assertEqual(result_document["kind"], "capability_authoring_result")
        self.assertEqual(result_document["artifact"], preview_document)
        self.assertNotIn("canonical_bytes", str(result_document))


if __name__ == "__main__":
    unittest.main()
