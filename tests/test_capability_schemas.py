"""Frozen V2-3 capability schema, fixture, and typed-parity tests.

Covers registration of every new capability schema, validation of every public
synthetic fixture, typed core/authoring serialization parity, negative bounds
and closed-union rejection, stable typed-core rejection parity, and protection
of every legacy Schema file on this branch.
"""

from __future__ import annotations

from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import random
import subprocess
from typing import Any
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from lore2mud.application import MoveIntent
from lore2mud.authoring.contracts import (
    AuthoringStatus,
    CanonicalContentFile,
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
from lore2mud.capabilities import (
    CanonicalJsonObject,
    CapabilityActionDescriptor,
    CapabilityCatalog,
    CapabilityCheckpoint,
    CapabilityDescriptor,
    CapabilityDiagnosticCode,
    CapabilityEffectDescriptor,
    CapabilityEventData,
    CapabilityEventDescriptor,
    CapabilityIntent,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    ResolvedCapability,
    ResolvedCapabilityPlan,
    SemanticVersion,
    SemanticVersionError,
    VersionRequirement,
    canonical_json_bytes,
    capability_value_to_document,
    random_state_to_canonical_json,
)
from lore2mud.capabilities.catalog import validate_capability_descriptor
from lore2mud.capabilities.serialization import CapabilitySerializationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "capabilities"
SHA256 = "1" * 64

NEW_SCHEMA_FILES = (
    "capability_descriptor.schema.json",
    "capability_catalog.schema.json",
    "resolved_capability_plan.schema.json",
    "capability_intent.schema.json",
    "capability_event_data.schema.json",
    "capability_player_view_entry.schema.json",
    "capability_preview.schema.json",
    "capability_checkpoint.schema.json",
    "capability_simulation_request.schema.json",
    "capability_simulation_report.schema.json",
    "capability_proofing_projection.schema.json",
    "capability_authoring_result.schema.json",
)

INVALID_SEMVERS = (
    "1.2",
    "v1.2.3",
    "01.2.3",
    "1.2.3-",
    "1.2.3+",
    "1.2.3.4",
    "1.2.3-alpha..1",
    "1.2.3-01",
)
VALID_SEMVERS = (
    "0.0.0",
    "1.2.3",
    "1.2.3-alpha.1",
    "1.2.3+build.5",
    "1.0.0-rc.1+build.2",
)
INVALID_REQUIREMENTS = (
    ">=1.0.0",
    "1.2.3,2.0.0",
    ">=1.0.0,<2.0.0 ",
    "=>1.0.0,<2.0.0",
    ">=1.0.0,<=2.0.0+build",
    "=1.2.3",
)
VALID_REQUIREMENTS = (
    "1.2.3",
    ">=1.0.0,<2.0.0",
    ">1.0.0,<=2.0.0",
    ">=1.0.0-alpha,<2.0.0",
)
FORBIDDEN_FIELDS = (
    "implementation",
    "module",
    "imports",
    "path",
    "process",
    "network",
    "code",
    "handler",
)


def _schema_registry() -> tuple[dict[str, Any], Registry]:
    schemas = {
        document["$id"]: document
        for path in (ROOT / "schemas").glob("*.schema.json")
        for document in [json.loads(path.read_text("utf-8"))]
        if "$id" in document
    }
    registry = Registry().with_resources(
        (uri, Resource.from_contents(document))
        for uri, document in schemas.items()
    )
    return schemas, registry


def _canonical(document: object) -> CanonicalJsonObject:
    return CanonicalJsonObject(canonical_json_bytes(document))


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def _schema_name_for_fixture(name: str) -> str:
    return name.replace(".json", ".schema.json")


def _typed_descriptor(
    *, format_version: int = 1, capability_id: str = "reference_counter"
) -> CapabilityDescriptor:
    empty_schema = _canonical(
        {"type": "object", "additionalProperties": False, "properties": {}}
    )
    counter_schema = _canonical(
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["count"],
            "properties": {"count": {"type": "integer", "minimum": 0}},
        }
    )
    return CapabilityDescriptor(
        format_version=format_version,
        capability_id=capability_id,
        version=SemanticVersion.parse("1.0.0"),
        safety_level=CapabilitySafetyLevel.L0,
        state_namespace="lore2mud.reference_counter",
        initial_state=_canonical({"count": 0}),
        state_schema=counter_schema,
        actions=(
            CapabilityActionDescriptor(
                action_id="increment",
                parameters_schema=empty_schema,
                predicate_ids=(),
                effect_ids=("increment_count",),
                event_ids=("counter_incremented",),
            ),
        ),
        observers=(),
        predicates=(),
        effects=(
            CapabilityEffectDescriptor(
                effect_id="increment_count", payload_schema=empty_schema
            ),
        ),
        events=(
            CapabilityEventDescriptor(
                event_id="counter_incremented", payload_schema=empty_schema
            ),
        ),
        player_view_schema=counter_schema,
        dependencies=(),
        conflicts=(),
        migrations=(),
    )


def _typed_state_entry() -> CapabilityStateEntry:
    return CapabilityStateEntry(
        capability_id="reference_counter",
        version=SemanticVersion.parse("1.0.0"),
        namespace="lore2mud.reference_counter",
        state=_canonical({"count": 0}),
    )


def _typed_plan() -> ResolvedCapabilityPlan:
    return ResolvedCapabilityPlan(
        format_version=1,
        requirement_ids=("reference_counter",),
        capabilities=(
            ResolvedCapability(
                capability_id="reference_counter",
                version=SemanticVersion.parse("1.0.0"),
                safety_level=CapabilitySafetyLevel.L0,
                state_namespace="lore2mud.reference_counter",
                descriptor_sha256=SHA256,
            ),
        ),
        dependency_edges=(),
        migrations=(),
        initial_states=(_typed_state_entry(),),
        catalog_sha256=SHA256,
        fingerprint=SHA256,
    )


def _typed_capability_intent() -> CapabilityIntent:
    return CapabilityIntent(
        capability_id="reference_counter",
        action_id="increment",
        parameters=_canonical({}),
    )


def _typed_base_preview() -> PreviewBuild:
    content_files = tuple(
        CanonicalContentFile(name=name, sha256=SHA256, canonical_json=b"{}")
        for name in (
            "pack.json",
            "rooms.json",
            "items.json",
            "monsters.json",
            "characters.json",
            "quests.json",
            "dialogues.json",
            "shops.json",
        )
    )
    return PreviewBuild(
        format_version=1,
        preview_id="preview_public",
        project_id="project_public",
        blueprint_sha256=SHA256,
        project_sha256=SHA256,
        engine_version="0.0.0",
        content_files=content_files,
        fingerprint=SHA256,
    )


def _typed_base_report() -> SimulationReport:
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


def _typed_capability_turns() -> tuple[CapabilitySimulationTurn, ...]:
    return (
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
            step=_typed_capability_intent(),
            status="accepted",
            rejection_code=None,
            event_sha256=SHA256,
            view_sha256=SHA256,
            capability_state_sha256=SHA256,
            event_sequence_after=2,
        ),
    )


class CapabilitySchemaRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas, cls.registry = _schema_registry()

    def test_all_new_schemas_are_registered_and_frozen(self) -> None:
        for name in NEW_SCHEMA_FILES:
            with self.subTest(schema=name):
                schema = self.schemas[
                    f"https://github.com/lore2mud/lore2mud/schemas/{name}"
                ]
                Draft202012Validator.check_schema(schema)
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertEqual(schema["type"], "object")
                self.assertIs(schema["additionalProperties"], False)

    def test_new_schema_ids_match_file_names(self) -> None:
        for name in NEW_SCHEMA_FILES:
            with self.subTest(schema=name):
                document = json.loads((SCHEMAS_DIR / name).read_text("utf-8"))
                self.assertEqual(
                    document["$id"],
                    f"https://github.com/lore2mud/lore2mud/schemas/{name}",
                )

    def test_legacy_schema_ids_still_register(self) -> None:
        for name in (
            "authoring_result.schema.json",
            "preview_build.schema.json",
            "simulation_request.schema.json",
            "simulation_report.schema.json",
            "proofing_projection.schema.json",
            "authoring_diagnostic.schema.json",
            "admissible_intent_descriptor.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertIn(
                    f"https://github.com/lore2mud/lore2mud/schemas/{name}",
                    self.schemas,
                )


class CapabilityFixtureValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas, cls.registry = _schema_registry()

    def test_every_fixture_validates_against_its_schema(self) -> None:
        fixtures = sorted(FIXTURES.glob("*.json"))
        self.assertEqual(len(fixtures), len(NEW_SCHEMA_FILES))
        for fixture in fixtures:
            schema_name = _schema_name_for_fixture(fixture.name)
            with self.subTest(fixture=fixture.name):
                validator = Draft202012Validator(
                    self.schemas[
                        f"https://github.com/lore2mud/lore2mud/schemas/{schema_name}"
                    ],
                    registry=self.registry,
                )
                validator.validate(_load_fixture(fixture.name))

    def test_fixture_set_covers_every_new_schema(self) -> None:
        fixture_names = {path.name for path in FIXTURES.glob("*.json")}
        for name in NEW_SCHEMA_FILES:
            with self.subTest(schema=name):
                self.assertIn(name.replace(".schema.json", ".json"), fixture_names)


class CapabilityTypedSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas, cls.registry = _schema_registry()

    def _validator(self, name: str) -> Draft202012Validator:
        schema = self.schemas[
            f"https://github.com/lore2mud/lore2mud/schemas/{name}"
        ]
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, registry=self.registry)

    def test_typed_core_values_serialize_and_validate(self) -> None:
        cases = (
            ("capability_descriptor.schema.json", _typed_descriptor()),
            ("resolved_capability_plan.schema.json", _typed_plan()),
            ("capability_intent.schema.json", _typed_capability_intent()),
            (
                "capability_event_data.schema.json",
                CapabilityEventData(
                    capability_id="reference_counter",
                    event_id="counter_incremented",
                    payload=_canonical({"new_count": 1}),
                ),
            ),
            (
                "capability_player_view_entry.schema.json",
                CapabilityPlayerViewEntry(
                    capability_id="reference_counter",
                    version=SemanticVersion.parse("1.0.0"),
                    view=_canonical({"count": 1}),
                    admissible_intents=(_typed_capability_intent(),),
                ),
            ),
            (
                "capability_checkpoint.schema.json",
                CapabilityCheckpoint(
                    format_version=1,
                    plan=_typed_plan(),
                    plan_sha256=SHA256,
                    save_document=_canonical({"player_name": "Simulator"}),
                    save_sha256=SHA256,
                    states=(_typed_state_entry(),),
                    state_sha256=SHA256,
                    seed=7,
                    clock=11,
                    event_sequence=2,
                    view_sha256=SHA256,
                    fingerprint=SHA256,
                    rng_state=random_state_to_canonical_json(
                        random.Random(7).getstate()
                    ),
                ),
            ),
        )
        for schema_name, value in cases:
            with self.subTest(schema=schema_name):
                document = capability_value_to_document(value)
                self._validator(schema_name).validate(document)

    def test_typed_authoring_values_serialize_and_validate(self) -> None:
        preview = CapabilityPreview(
            format_version=1,
            base_preview=_typed_base_preview(),
            resolved_plan=_typed_plan(),
            plan_sha256=SHA256,
            initial_states=(_typed_state_entry(),),
            initial_state_sha256=SHA256,
            engine_version="0.0.0",
            fingerprint=SHA256,
        )
        request = CapabilitySimulationRequest(
            format_version=1,
            seed=7,
            clock=11,
            player_name="Simulator",
            steps=(MoveIntent("east"), _typed_capability_intent()),
            conditions=(),
            checkpoint_after_steps=(2,),
        )
        turns = _typed_capability_turns()
        report = CapabilitySimulationReport(
            format_version=1,
            project_id="project_public",
            base_report=_typed_base_report(),
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
            base_proofing=ProofingProjection(
                format_version=1,
                project_id="project_public",
                preview_fingerprint=SHA256,
                nodes=(),
                edges=(),
                admissible_intents=(),
            ),
            capability_views=(
                CapabilityPlayerViewEntry(
                    capability_id="reference_counter",
                    version=SemanticVersion.parse("1.0.0"),
                    view=_canonical({"count": 1}),
                    admissible_intents=(),
                ),
            ),
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

        cases = (
            (
                "capability_simulation_request.schema.json",
                capability_simulation_request_to_document(request),
            ),
            (
                "capability_preview.schema.json",
                capability_preview_to_document(preview),
            ),
            (
                "capability_simulation_report.schema.json",
                capability_simulation_report_to_document(report),
            ),
            (
                "capability_proofing_projection.schema.json",
                capability_proofing_to_document(proofing),
            ),
            (
                "capability_authoring_result.schema.json",
                authoring_result_to_document(result),
            ),
        )
        for schema_name, document in cases:
            with self.subTest(schema=schema_name):
                self._validator(schema_name).validate(document)

    def test_catalog_public_schema_rejects_engine_registry_fields(self) -> None:
        catalog = CapabilityCatalog(())
        document = capability_value_to_document(catalog)
        assert isinstance(document, dict)
        self.assertIn("implementation_registry", document)

        with self.assertRaises(ValidationError):
            self._validator("capability_catalog.schema.json").validate(document)


class CapabilityNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas, cls.registry = _schema_registry()

    def _validator(self, name: str) -> Draft202012Validator:
        schema = self.schemas[
            f"https://github.com/lore2mud/lore2mud/schemas/{name}"
        ]
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, registry=self.registry)

    def test_invalid_semver_is_rejected_by_schema_and_typed_core(self) -> None:
        validator = self._validator("capability_descriptor.schema.json")
        for value in INVALID_SEMVERS:
            with self.subTest(value=value):
                document = copy.deepcopy(_load_fixture("capability_descriptor.json"))
                document["version"] = value
                self.assertTrue(list(validator.iter_errors(document)))
                with self.assertRaises(SemanticVersionError):
                    SemanticVersion.parse(value)

    def test_valid_semver_is_accepted_by_schema_and_typed_core(self) -> None:
        validator = self._validator("capability_descriptor.schema.json")
        for value in VALID_SEMVERS:
            with self.subTest(value=value):
                document = copy.deepcopy(_load_fixture("capability_descriptor.json"))
                document["version"] = value
                validator.validate(document)
                self.assertEqual(str(SemanticVersion.parse(value)), value)

    def test_invalid_version_requirement_is_rejected_by_schema_and_typed_core(
        self,
    ) -> None:
        validator = self._validator("capability_descriptor.schema.json")
        for value in INVALID_REQUIREMENTS:
            with self.subTest(value=value):
                document = copy.deepcopy(_load_fixture("capability_descriptor.json"))
                document["dependencies"] = [
                    {"capability_id": "other_capability", "requirement": value}
                ]
                self.assertTrue(list(validator.iter_errors(document)))
                with self.assertRaises(SemanticVersionError):
                    VersionRequirement.parse(value)

    def test_valid_version_requirement_is_accepted_by_schema_and_typed_core(
        self,
    ) -> None:
        validator = self._validator("capability_descriptor.schema.json")
        for value in VALID_REQUIREMENTS:
            with self.subTest(value=value):
                document = copy.deepcopy(_load_fixture("capability_descriptor.json"))
                document["dependencies"] = [
                    {"capability_id": "other_capability", "requirement": value}
                ]
                validator.validate(document)
                self.assertEqual(str(VersionRequirement.parse(value)), value)

    def test_unknown_and_forbidden_fields_are_rejected(self) -> None:
        for name in NEW_SCHEMA_FILES:
            validator = self._validator(name)
            fixture_name = name.replace(".schema.json", ".json")
            for field in FORBIDDEN_FIELDS:
                with self.subTest(schema=name, field=field):
                    document = copy.deepcopy(_load_fixture(fixture_name))
                    document[field] = {"example": True}
                    self.assertTrue(list(validator.iter_errors(document)))

    def test_array_and_string_and_integer_bounds_are_rejected(self) -> None:
        descriptor = copy.deepcopy(_load_fixture("capability_descriptor.json"))
        descriptor["actions"] = [descriptor["actions"][0]] * 257
        self.assertTrue(
            list(
                self._validator("capability_descriptor.schema.json").iter_errors(
                    descriptor
                )
            )
        )

        catalog = copy.deepcopy(_load_fixture("capability_catalog.json"))
        catalog["descriptors"] = [catalog["descriptors"][0]] * 257
        self.assertTrue(
            list(self._validator("capability_catalog.schema.json").iter_errors(catalog))
        )

        plan = copy.deepcopy(_load_fixture("resolved_capability_plan.json"))
        plan["capabilities"] = plan["capabilities"] * 4097
        self.assertTrue(
            list(
                self._validator("resolved_capability_plan.schema.json").iter_errors(
                    plan
                )
            )
        )

        request = copy.deepcopy(_load_fixture("capability_simulation_request.json"))
        request["steps"] = request["steps"] * 513
        self.assertTrue(
            list(
                self._validator(
                    "capability_simulation_request.schema.json"
                ).iter_errors(request)
            )
        )
        request = copy.deepcopy(_load_fixture("capability_simulation_request.json"))
        request["player_name"] = "x" * 129
        self.assertTrue(
            list(
                self._validator(
                    "capability_simulation_request.schema.json"
                ).iter_errors(request)
            )
        )

        checkpoint = copy.deepcopy(_load_fixture("capability_checkpoint.json"))
        checkpoint["event_sequence"] = -1
        self.assertTrue(
            list(
                self._validator("capability_checkpoint.schema.json").iter_errors(
                    checkpoint
                )
            )
        )

    def test_int64_bounds_parity_with_canonical_serializer(self) -> None:
        for value in (2**63, -(2**63) - 1):
            with self.subTest(value=str(value)):
                with self.assertRaises(CapabilitySerializationError):
                    canonical_json_bytes({"seed": value})
                request = copy.deepcopy(
                    _load_fixture("capability_simulation_request.json")
                )
                request["seed"] = value
                self.assertTrue(
                    list(
                        self._validator(
                            "capability_simulation_request.schema.json"
                        ).iter_errors(request)
                    )
                )

    def test_checkpoint_rng_state_is_required_and_matches_core_encoding(self) -> None:
        validator = self._validator("capability_checkpoint.schema.json")
        checkpoint = copy.deepcopy(_load_fixture("capability_checkpoint.json"))
        expected = capability_value_to_document(
            random_state_to_canonical_json(random.Random(7).getstate())
        )

        self.assertEqual(checkpoint["rng_state"], expected)
        validator.validate(checkpoint)

        missing = copy.deepcopy(checkpoint)
        del missing["rng_state"]
        null_sentinel = copy.deepcopy(checkpoint)
        null_sentinel["rng_state"] = None
        for document in (missing, null_sentinel):
            with self.subTest(document=document):
                self.assertTrue(list(validator.iter_errors(document)))

    def test_checkpoint_rng_state_schema_rejects_identity_and_bounds_tampering(
        self,
    ) -> None:
        validator = self._validator("capability_checkpoint.schema.json")
        checkpoint = copy.deepcopy(_load_fixture("capability_checkpoint.json"))
        rng_state = copy.deepcopy(checkpoint["rng_state"])
        assert isinstance(rng_state, dict)
        state = list(rng_state["state"])
        invalid_states: list[Any] = []

        for field_name, value in (
            ("algorithm", "other"),
            ("format_version", 2),
            ("version", 2),
            ("gauss_next", "0x1p+0"),
            ("gauss_next", "inf"),
        ):
            changed = copy.deepcopy(rng_state)
            changed[field_name] = value
            invalid_states.append(changed)

        for index, value in ((0, -1), (0, 2**32), (624, -1), (624, 625)):
            changed = copy.deepcopy(rng_state)
            changed_state = list(state)
            changed_state[index] = value
            changed["state"] = changed_state
            invalid_states.append(changed)

        for changed_state in (state[:-1], state + [0]):
            changed = copy.deepcopy(rng_state)
            changed["state"] = changed_state
            invalid_states.append(changed)

        extra = copy.deepcopy(rng_state)
        extra["implementation"] = "hidden"
        invalid_states.append(extra)

        for invalid in invalid_states:
            with self.subTest(invalid=invalid):
                document = copy.deepcopy(checkpoint)
                document["rng_state"] = invalid
                self.assertTrue(list(validator.iter_errors(document)))

    def test_closed_step_union_rejects_unknown_and_ambiguous_steps(self) -> None:
        validator = self._validator("capability_simulation_request.schema.json")
        for step in (
            {"type": "teleport"},
            {"capability_id": "reference_counter"},
            {"type": "move", "direction": "east", "extra": 1},
            {
                "type": "move",
                "direction": "east",
                "capability_id": "reference_counter",
                "action_id": "increment",
                "parameters": {},
            },
        ):
            with self.subTest(step=step):
                document = copy.deepcopy(
                    _load_fixture("capability_simulation_request.json")
                )
                document["steps"] = [step]
                self.assertTrue(list(validator.iter_errors(document)))

    def test_duplicate_items_are_rejected(self) -> None:
        plan = copy.deepcopy(_load_fixture("resolved_capability_plan.json"))
        plan["requirement_ids"] = ["reference_counter", "reference_counter"]
        self.assertTrue(
            list(
                self._validator("resolved_capability_plan.schema.json").iter_errors(
                    plan
                )
            )
        )

        request = copy.deepcopy(_load_fixture("capability_simulation_request.json"))
        request["checkpoint_after_steps"] = [2, 2]
        self.assertTrue(
            list(
                self._validator(
                    "capability_simulation_request.schema.json"
                ).iter_errors(request)
            )
        )

    def test_descriptor_validation_parity_with_typed_core(self) -> None:
        validator = self._validator("capability_descriptor.schema.json")

        bad_format = copy.deepcopy(_load_fixture("capability_descriptor.json"))
        bad_format["format_version"] = 2
        self.assertTrue(list(validator.iter_errors(bad_format)))
        diagnostics = validate_capability_descriptor(_typed_descriptor(format_version=2))
        self.assertTrue(
            any(
                item.code is CapabilityDiagnosticCode.CAPABILITY_DESCRIPTOR_INVALID
                for item in diagnostics
            )
        )

        bad_id = copy.deepcopy(_load_fixture("capability_descriptor.json"))
        bad_id["capability_id"] = "bad-id"
        self.assertTrue(list(validator.iter_errors(bad_id)))
        diagnostics = validate_capability_descriptor(
            _typed_descriptor(capability_id="bad-id")
        )
        self.assertTrue(diagnostics)

        duplicate_actions = replace(
            _typed_descriptor(),
            actions=(
                _typed_descriptor().actions[0],
                _typed_descriptor().actions[0],
            ),
        )
        diagnostics = validate_capability_descriptor(duplicate_actions)
        self.assertTrue(
            any("duplicate action IDs" in item.message for item in diagnostics)
        )


class CapabilitySchemaProtectionTests(unittest.TestCase):
    def test_legacy_schema_files_are_unchanged(self) -> None:
        legacy = sorted(
            name
            for name in os.listdir(SCHEMAS_DIR)
            if name.endswith(".schema.json") and name not in NEW_SCHEMA_FILES
        )
        self.assertGreater(len(legacy), 0)
        for name in legacy:
            with self.subTest(schema=name):
                result = subprocess.run(
                    ["git", "diff", "--quiet", "HEAD", "--", f"schemas/{name}"],
                    cwd=ROOT,
                    capture_output=True,
                )
                self.assertEqual(
                    result.returncode, 0, f"legacy schema changed on this branch: {name}"
                )

    def test_git_status_does_not_modify_protected_runtime_core_paths(self) -> None:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        protected_paths = {
            "src/lore2mud/engine/world.py",
            "src/lore2mud/engine/save.py",
            "pipeline/forge.py",
        }
        for line in result.stdout.splitlines():
            path = line[3:].strip()
            self.assertNotIn(
                path,
                protected_paths,
                f"V2-3 must not modify protected runtime core path: {path}",
            )


if __name__ == "__main__":
    unittest.main()
