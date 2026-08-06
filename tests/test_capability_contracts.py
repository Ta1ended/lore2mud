from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest

from lore2mud.capabilities import (
    INT64_MAX,
    CanonicalJsonObject,
    CapabilityActionDescriptor,
    CapabilityCatalog,
    CapabilityCatalogError,
    CapabilityCheckpoint,
    CapabilityDescriptor,
    CapabilityDiagnosticCode,
    CapabilityEffectResult,
    CapabilityImplementationBinding,
    CapabilityImplementationContract,
    CapabilityImplementationRegistry,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    ResolvedCapabilityPlan,
    SemanticVersion,
    SemanticVersionError,
    VersionRequirement,
    canonical_json_bytes,
    canonical_json_object,
    capability_value_to_document,
    compare_precedence,
    parse_canonical_json_bytes,
    parse_canonical_json_object,
    random_state_from_canonical_json,
    random_state_to_canonical_json,
    sha256_bytes,
    validate_json_schema,
    validate_capability_descriptor,
)
from lore2mud.capabilities.serialization import (
    CapabilitySchemaError,
    CapabilitySerializationError,
)


EMPTY_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "additionalProperties": False,
        "required": [],
        "properties": {},
    }
)
EMPTY_OBJECT = canonical_json_object({})


class StubImplementation:
    def __init__(self, contract: CapabilityImplementationContract) -> None:
        self._contract = contract

    @property
    def contract(self) -> CapabilityImplementationContract:
        return self._contract

    def apply(self, intent, state, context):  # type: ignore[no-untyped-def]
        return CapabilityEffectResult(state.state)

    def observe(self, observation, state, context):  # type: ignore[no-untyped-def]
        return CapabilityEffectResult(state.state)

    def project(self, state, context):  # type: ignore[no-untyped-def]
        return CapabilityPlayerViewEntry(
            state.capability_id,
            state.version,
            EMPTY_OBJECT,
        )

    def evaluate_predicate(self, predicate_id, state, context):  # type: ignore[no-untyped-def]
        return True

    def migrate(self, migration_id, state, context):  # type: ignore[no-untyped-def]
        return state


def descriptor(
    capability_id: str,
    version: str,
    *,
    namespace: str | None = None,
    initial_state: CanonicalJsonObject = EMPTY_OBJECT,
    state_schema: CanonicalJsonObject = EMPTY_SCHEMA,
    actions: tuple[CapabilityActionDescriptor, ...] = (),
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        format_version=1,
        capability_id=capability_id,
        version=SemanticVersion.parse(version),
        safety_level=CapabilitySafetyLevel.L1,
        state_namespace=namespace or capability_id,
        initial_state=initial_state,
        state_schema=state_schema,
        actions=actions,
        observers=(),
        predicates=(),
        effects=(),
        events=(),
        player_view_schema=EMPTY_SCHEMA,
    )


def binding(
    value: CapabilityDescriptor,
    *,
    action_ids: tuple[str, ...] | None = None,
) -> CapabilityImplementationBinding:
    contract = CapabilityImplementationContract(
        capability_id=value.capability_id,
        version=value.version,
        action_ids=(
            tuple(action.action_id for action in value.actions)
            if action_ids is None
            else action_ids
        ),
        observer_ids=tuple(observer.observer_id for observer in value.observers),
        predicate_ids=tuple(predicate.predicate_id for predicate in value.predicates),
        effect_ids=tuple(effect.effect_id for effect in value.effects),
        event_ids=tuple(event.event_id for event in value.events),
        migration_ids=tuple(migration.migration_id for migration in value.migrations),
    )
    return CapabilityImplementationBinding(value, StubImplementation(contract))


class SemanticVersionTests(unittest.TestCase):
    def test_semver_precedence_and_build_metadata(self) -> None:
        ordered = (
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        )
        parsed = tuple(SemanticVersion.parse(value) for value in ordered)
        for lower, higher in zip(parsed, parsed[1:], strict=False):
            self.assertLess(lower, higher)
        one = SemanticVersion.parse("1.0.0+one")
        two = SemanticVersion.parse("1.0.0+two")
        self.assertEqual(compare_precedence(one, two), 0)
        self.assertNotEqual(one, two)
        self.assertEqual(str(SemanticVersion.parse("1.0.0+001")), "1.0.0+001")

    def test_semver_rejects_noncanonical_and_unbounded_tokens(self) -> None:
        invalid = (
            "01.0.0",
            "1.00.0",
            "1.0.00",
            f"{INT64_MAX + 1}.0.0",
            "1.0.0-01",
            "1.0.0-",
            "1.0.0+",
            "1.0.0-alpha..one",
            "1.0.0-测试",
            "v1.0.0",
            "1.0",
            " 1.0.0",
            "1.0.0+" + "a" * 123,
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(SemanticVersionError):
                SemanticVersion.parse(value)

    def test_version_requirement_is_exact_or_canonical_bounded(self) -> None:
        exact = VersionRequirement.parse("1.2.3")
        self.assertTrue(exact.matches(SemanticVersion.parse("1.2.3+build.1")))
        self.assertFalse(exact.matches(SemanticVersion.parse("1.2.4")))

        bounded = VersionRequirement.parse(">=1.0.0,<2.0.0")
        self.assertTrue(bounded.matches(SemanticVersion.parse("1.9.9")))
        self.assertFalse(bounded.matches(SemanticVersion.parse("2.0.0")))
        self.assertFalse(bounded.matches(SemanticVersion.parse("1.5.0-alpha")))

        prerelease = VersionRequirement.parse(">=2.0.0-alpha.1,<2.0.0")
        self.assertTrue(prerelease.allows_prerelease)
        self.assertTrue(prerelease.matches(SemanticVersion.parse("2.0.0-beta.1")))

        for value in (">=1.0.0", "<2.0.0,>=1.0.0", ">=1.0.0, <2.0.0", "1.*"):
            with self.subTest(value=value), self.assertRaises(SemanticVersionError):
                VersionRequirement.parse(value)
        with self.assertRaises(SemanticVersionError):
            VersionRequirement.parse("1.0.0+" + "a" * 250)


class CapabilitySerializationTests(unittest.TestCase):
    def test_canonical_json_is_stable_human_readable_utf8(self) -> None:
        value = canonical_json_object({"z": 2, "a": {"name": "公开", "ok": True}})
        self.assertEqual(
            value.canonical_bytes,
            b'{\n  "a": {\n    "name": "\xe5\x85\xac\xe5\xbc\x80",\n    "ok": true\n  },\n  "z": 2\n}\n',
        )
        self.assertEqual(parse_canonical_json_object(value)["z"], 2)
        self.assertEqual(sha256_bytes(value.canonical_bytes), sha256_bytes(value.canonical_bytes))

    def test_parser_rejects_noncanonical_bytes_and_non_objects(self) -> None:
        for payload in (b'{"a":1}\n', b"{}\r\n", b"{}", b"[]\n"):
            with self.subTest(payload=payload):
                if payload == b"[]\n":
                    parsed = parse_canonical_json_bytes(payload)
                    self.assertEqual(parsed, [])
                    with self.assertRaises(CapabilitySerializationError):
                        parse_canonical_json_object(CanonicalJsonObject(payload))
                else:
                    with self.assertRaises(CapabilitySerializationError):
                        parse_canonical_json_bytes(payload)

    def test_schema_subset_validates_bounds_and_closed_objects(self) -> None:
        schema = canonical_json_object(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["count"],
                "properties": {
                    "count": {"type": "integer", "minimum": 0, "maximum": 1000}
                },
            }
        )
        validate_json_schema({"count": 10}, schema)
        for value in ({"count": -1}, {"count": 1001}, {"count": 1, "hidden": True}):
            with self.subTest(value=value), self.assertRaises(CapabilitySchemaError):
                validate_json_schema(value, schema)

    def test_contract_conversion_decodes_canonical_bytes(self) -> None:
        state = CapabilityStateEntry(
            "counter",
            SemanticVersion.parse("1.0.0"),
            "counter",
            canonical_json_object({"count": 0}),
        )
        document = capability_value_to_document(state)
        self.assertEqual(
            document,
            {
                "capability_id": "counter",
                "namespace": "counter",
                "state": {"count": 0},
                "version": "1.0.0",
            },
        )
        canonical_json_bytes(document)

    def test_canonical_object_property_bound_matches_public_schema(self) -> None:
        with self.assertRaises(CapabilitySerializationError):
            canonical_json_object({f"field_{index}": index for index in range(4097)})

    def test_random_state_round_trip_uses_canonical_hex_for_gauss_cache(self) -> None:
        generator = random.Random(7)
        generator.gauss(0.0, 1.0)
        state = generator.getstate()

        encoded = random_state_to_canonical_json(state)
        document = parse_canonical_json_object(encoded)

        self.assertEqual(document["algorithm"], "python_random_mt19937")
        self.assertEqual(document["format_version"], 1)
        self.assertEqual(document["version"], 3)
        self.assertEqual(len(document["state"]), 625)  # type: ignore[arg-type]
        self.assertEqual(document["gauss_next"], state[2].hex())
        self.assertEqual(random_state_from_canonical_json(encoded), state)

    def test_random_state_decoder_rejects_tampered_payloads(self) -> None:
        document = parse_canonical_json_object(
            random_state_to_canonical_json(random.Random(7).getstate())
        )
        state_values = list(document["state"])  # type: ignore[arg-type]
        invalid_documents: list[dict[str, object]] = []

        for field_name, value in (
            ("algorithm", "other"),
            ("format_version", 2),
            ("version", 2),
            ("gauss_next", "0x1p+0"),
            ("gauss_next", "inf"),
        ):
            changed = dict(document)
            changed[field_name] = value
            invalid_documents.append(changed)

        missing = dict(document)
        del missing["algorithm"]
        invalid_documents.append(missing)

        extra = dict(document)
        extra["implementation"] = "hidden"
        invalid_documents.append(extra)

        for index, value in ((0, -1), (0, 2**32), (624, -1), (624, 625)):
            changed = dict(document)
            changed_state = list(state_values)
            changed_state[index] = value
            changed["state"] = changed_state
            invalid_documents.append(changed)

        shortened = dict(document)
        shortened["state"] = state_values[:-1]
        invalid_documents.append(shortened)

        for invalid in invalid_documents:
            with self.subTest(invalid=invalid), self.assertRaises(CapabilitySerializationError):
                random_state_from_canonical_json(canonical_json_object(invalid))

    def test_checkpoint_appends_rng_state_with_compatibility_sentinel(self) -> None:
        self.assertEqual(fields(CapabilityCheckpoint)[-1].name, "rng_state")
        plan = ResolvedCapabilityPlan(
            format_version=1,
            requirement_ids=(),
            capabilities=(),
            dependency_edges=(),
            migrations=(),
            initial_states=(),
            catalog_sha256="0" * 64,
            fingerprint="1" * 64,
        )
        checkpoint = CapabilityCheckpoint(
            format_version=1,
            plan=plan,
            plan_sha256="2" * 64,
            save_document=EMPTY_OBJECT,
            save_sha256="3" * 64,
            states=(),
            state_sha256="4" * 64,
            seed=7,
            clock=9,
            event_sequence=11,
            view_sha256="5" * 64,
            fingerprint="6" * 64,
        )

        self.assertIsNone(checkpoint.rng_state)
        document = capability_value_to_document(checkpoint)
        self.assertEqual(tuple(document)[-1], "rng_state")  # type: ignore[arg-type]
        self.assertIsNone(document["rng_state"])  # type: ignore[index]


class CapabilityCatalogTests(unittest.TestCase):
    def test_catalog_and_registry_are_frozen_sorted_and_permutation_independent(self) -> None:
        alpha = descriptor("alpha", "1.0.0")
        beta = descriptor("beta", "2.0.0")
        first = CapabilityCatalog.from_bindings((binding(beta), binding(alpha)))
        second = CapabilityCatalog.from_bindings((binding(alpha), binding(beta)))

        self.assertEqual(tuple(item.capability_id for item in first.descriptors), ("alpha", "beta"))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.descriptors, second.descriptors)
        with self.assertRaises(FrozenInstanceError):
            first.descriptors = ()  # type: ignore[misc]

    def test_equal_precedence_builds_are_rejected(self) -> None:
        one = descriptor("counter", "1.0.0+one")
        two = descriptor("counter", "1.0.0+two")
        with self.assertRaises(CapabilityCatalogError) as caught:
            CapabilityImplementationRegistry((binding(one), binding(two)))
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_CATALOG_DUPLICATE,
            {diagnostic.code for diagnostic in caught.exception.diagnostics},
        )

    def test_missing_or_mismatched_implementation_is_rejected(self) -> None:
        action = CapabilityActionDescriptor("increment", EMPTY_SCHEMA)
        value = descriptor("counter", "1.0.0", actions=(action,))
        with self.assertRaises(CapabilityCatalogError) as missing:
            CapabilityCatalog((value,))
        self.assertEqual(
            missing.exception.diagnostics[0].code,
            CapabilityDiagnosticCode.CAPABILITY_IMPLEMENTATION_MISSING,
        )

        with self.assertRaises(CapabilityCatalogError) as mismatch:
            CapabilityImplementationRegistry((binding(value, action_ids=()),))
        self.assertIn("action IDs do not match", str(mismatch.exception))

    def test_invalid_initial_state_is_rejected_without_jsonschema_dependency(self) -> None:
        state_schema = canonical_json_object(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["count"],
                "properties": {
                    "count": {"type": "integer", "minimum": 0, "maximum": 10}
                },
            }
        )
        value = descriptor(
            "counter",
            "1.0.0",
            state_schema=state_schema,
            initial_state=canonical_json_object({"count": 11}),
        )
        with self.assertRaises(CapabilityCatalogError) as caught:
            CapabilityCatalog.from_bindings((binding(value),))
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_STATE_INVALID,
            {diagnostic.code for diagnostic in caught.exception.diagnostics},
        )

    def test_descriptor_and_catalog_member_bounds_match_public_schema(self) -> None:
        action = CapabilityActionDescriptor("increment", EMPTY_SCHEMA)
        unbounded = replace(
            descriptor("counter", "1.0.0"),
            actions=(action,) * 257,
        )
        diagnostics = validate_capability_descriptor(unbounded)
        self.assertTrue(any("actions exceeds descriptor bounds" in item.message for item in diagnostics))

        bindings = tuple(
            binding(descriptor(f"capability_{index}", "1.0.0"))
            for index in range(257)
        )
        with self.assertRaises(CapabilityCatalogError) as caught:
            CapabilityCatalog.from_bindings(bindings)
        self.assertTrue(
            any("catalog exceeds descriptor bounds" in item.message for item in caught.exception.diagnostics)
        )


if __name__ == "__main__":
    unittest.main()
