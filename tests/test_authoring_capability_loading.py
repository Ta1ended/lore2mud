"""Typed loader coverage for V2-3 capability simulation artifacts."""

from __future__ import annotations

from dataclasses import replace
import unittest

from lore2mud import __version__
from lore2mud.application import MoveIntent
from lore2mud.authoring.contracts import (
    CapabilitySimulationCheckpoint,
    CapabilitySimulationReport,
    CapabilitySimulationRequest,
    CapabilitySimulationTurn,
    SimulationOutcome,
    SimulationReport,
)
from lore2mud.authoring.serialization import (
    capability_simulation_report_to_document,
    capability_simulation_request_to_document,
    fingerprint_document,
    simulation_report_to_document,
)
from lore2mud.authoring.simulation import (
    SimulationValidationError,
    load_simulation_report_document,
    load_simulation_request_document,
    validate_simulation_report,
)
from lore2mud.capabilities.contracts import CapabilityIntent
from lore2mud.capabilities.serialization import canonical_json_object


SHA256 = "1" * 64


def _base_report(*, turns=()) -> SimulationReport:
    report = SimulationReport(
        format_version=1,
        project_id="project_public",
        blueprint_sha256=SHA256,
        project_sha256=SHA256,
        preview_fingerprint=SHA256,
        request_sha256=SHA256,
        engine_version=__version__,
        seed=7,
        clock=11,
        player_name="Simulator",
        initial_state_sha256=SHA256,
        final_state_sha256=SHA256,
        initial_view_sha256=SHA256,
        final_view_sha256=SHA256,
        turns=turns,
        condition_results=(),
        outcome=SimulationOutcome.UNDETERMINED,
        witness_trace=turns,
        replay_verified=True,
        checkpoints=(),
        fingerprint="",
    )
    return replace(
        report,
        fingerprint=fingerprint_document(
            simulation_report_to_document(report, include_fingerprint=False)
        ),
    )


def _capability_report() -> CapabilitySimulationReport:
    step = CapabilityIntent(
        capability_id="reference_counter",
        action_id="increment",
        parameters=canonical_json_object({"amount": 2}),
    )
    turns = (
        CapabilitySimulationTurn(
            index=0,
            step=step,
            status="accepted",
            rejection_code=None,
            event_sha256=SHA256,
            view_sha256=SHA256,
            capability_state_sha256=SHA256,
            event_sequence_after=1,
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
                after_step=1,
                checkpoint_sha256=SHA256,
                restored_state_sha256=SHA256,
                restored_view_sha256=SHA256,
                restored_event_sequence=1,
                equivalent=True,
            ),
        ),
        fingerprint="",
    )
    return replace(
        report,
        fingerprint=fingerprint_document(
            capability_simulation_report_to_document(
                report, include_fingerprint=False
            )
        ),
    )


class AuthoringCapabilityLoadingTests(unittest.TestCase):
    def test_capability_request_loader_round_trips_mixed_steps(self) -> None:
        capability_step = CapabilityIntent(
            capability_id="reference_counter",
            action_id="increment",
            parameters=canonical_json_object({"amount": 2}),
        )
        request = CapabilitySimulationRequest(
            format_version=1,
            seed=7,
            clock=11,
            player_name="Simulator",
            steps=(MoveIntent("east"), capability_step),
            checkpoint_after_steps=(0, 2),
        )

        loaded = load_simulation_request_document(
            capability_simulation_request_to_document(request)
        )

        self.assertEqual(loaded, request)

    def test_capability_report_loader_dispatches_and_round_trips(self) -> None:
        report = _capability_report()

        loaded = load_simulation_report_document(
            capability_simulation_report_to_document(report)
        )

        self.assertEqual(loaded, report)
        self.assertEqual(validate_simulation_report(report), report)

    def test_capability_report_loader_rejects_tampered_outer_fingerprint(self) -> None:
        document = capability_simulation_report_to_document(_capability_report())
        document["fingerprint"] = "0" * 64

        with self.assertRaisesRegex(SimulationValidationError, "fingerprint"):
            load_simulation_report_document(document)

    def test_capability_report_loader_rejects_nonlegacy_base_subsequence(self) -> None:
        report = _capability_report()
        document = capability_simulation_report_to_document(report)
        base_document = simulation_report_to_document(report.base_report)
        base_document["turns"] = [
            {
                "index": 1,
                "intent": {"type": "move", "direction": "west"},
                "status": "accepted",
                "rejection_code": None,
                "event_types": [],
                "view_sha256": SHA256,
            }
        ]
        base_document["witness_trace"] = list(base_document["turns"])
        base_document["fingerprint"] = fingerprint_document(
            {key: value for key, value in base_document.items() if key != "fingerprint"}
        )
        document["base_report"] = base_document
        document["fingerprint"] = fingerprint_document(
            {key: value for key, value in document.items() if key != "fingerprint"}
        )

        with self.assertRaisesRegex(SimulationValidationError, "legacy subsequence"):
            load_simulation_report_document(document)


if __name__ == "__main__":
    unittest.main()
