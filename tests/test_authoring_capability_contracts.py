"""Public wrapper-shape tests for the V2-3 authoring capability lane."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import unittest

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


if __name__ == "__main__":
    unittest.main()
