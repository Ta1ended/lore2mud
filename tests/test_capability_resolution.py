from __future__ import annotations

import unittest

from lore2mud.capabilities import (
    CapabilityCatalog,
    CapabilityConflictDescriptor,
    CapabilityDependencyDescriptor,
    CapabilityDescriptor,
    CapabilityDiagnosticCode,
    CapabilityEffectResult,
    CapabilityImplementationBinding,
    CapabilityImplementationContract,
    CapabilityMigrationDescriptor,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateVersion,
    SemanticVersion,
    VersionRequirement,
    canonical_json_bytes,
    canonical_json_object,
    capability_value_to_document,
    resolve_capabilities,
    sha256_bytes,
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
    dependencies: tuple[CapabilityDependencyDescriptor, ...] = (),
    conflicts: tuple[CapabilityConflictDescriptor, ...] = (),
    namespace: str | None = None,
    safety: CapabilitySafetyLevel = CapabilitySafetyLevel.L1,
    migrations: tuple[CapabilityMigrationDescriptor, ...] = (),
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        format_version=1,
        capability_id=capability_id,
        version=SemanticVersion.parse(version),
        safety_level=safety,
        state_namespace=namespace or capability_id,
        initial_state=EMPTY_OBJECT,
        state_schema=EMPTY_SCHEMA,
        actions=(),
        observers=(),
        predicates=(),
        effects=(),
        events=(),
        player_view_schema=EMPTY_SCHEMA,
        dependencies=dependencies,
        conflicts=conflicts,
        migrations=migrations,
    )


def binding(value: CapabilityDescriptor) -> CapabilityImplementationBinding:
    contract = CapabilityImplementationContract(
        capability_id=value.capability_id,
        version=value.version,
        migration_ids=tuple(migration.migration_id for migration in value.migrations),
    )
    return CapabilityImplementationBinding(value, StubImplementation(contract))


def catalog(*descriptors: CapabilityDescriptor) -> CapabilityCatalog:
    return CapabilityCatalog.from_bindings(tuple(binding(value) for value in descriptors))


def dependency(capability_id: str, requirement: str) -> CapabilityDependencyDescriptor:
    return CapabilityDependencyDescriptor(capability_id, VersionRequirement.parse(requirement))


class CapabilityResolutionTests(unittest.TestCase):
    def test_empty_requirements_produce_a_stable_empty_plan(self) -> None:
        result = resolve_capabilities(CapabilityCatalog.from_bindings(()), ())
        self.assertTrue(result.ok)
        assert result.plan is not None
        self.assertEqual(result.plan.capabilities, ())
        self.assertEqual(result.plan.initial_states, ())
        self.assertEqual(len(result.plan.fingerprint), 64)

    def test_resolution_is_permutation_independent_and_dependency_first(self) -> None:
        library = descriptor("library", "1.2.0")
        app = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("library", ">=1.0.0,<2.0.0"),),
        )
        guard = descriptor("guard", "1.0.0")

        first = resolve_capabilities(catalog(app, library, guard), ("guard", "app"))
        second = resolve_capabilities(catalog(guard, library, app), ("app", "guard"))
        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(first.plan, second.plan)
        assert first.plan is not None
        self.assertEqual(
            tuple(item.capability_id for item in first.plan.capabilities),
            ("guard", "library", "app"),
        )
        self.assertEqual(first.plan.requirement_ids, ("app", "guard"))

    def test_global_backtracking_avoids_greedy_dead_end(self) -> None:
        library_one = descriptor("library", "1.0.0")
        library_two = descriptor("library", "2.0.0")
        app_one = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("library", "1.0.0"),),
        )
        app_two = descriptor(
            "app",
            "2.0.0",
            dependencies=(dependency("library", "2.0.0"),),
        )
        guard = descriptor(
            "guard",
            "1.0.0",
            dependencies=(dependency("library", "1.0.0"),),
        )
        result = resolve_capabilities(
            catalog(library_two, app_two, guard, app_one, library_one),
            ("app", "guard"),
        )
        self.assertTrue(result.ok, result.diagnostics)
        assert result.plan is not None
        selected = {item.capability_id: str(item.version) for item in result.plan.capabilities}
        self.assertEqual(selected, {"app": "1.0.0", "guard": "1.0.0", "library": "1.0.0"})

    def test_complete_solution_is_lexicographically_maximal_by_sorted_id(self) -> None:
        library_one = descriptor("library", "1.0.0")
        library_two = descriptor("library", "2.0.0")
        app_one = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("library", "2.0.0"),),
        )
        app_two = descriptor(
            "app",
            "2.0.0",
            dependencies=(dependency("library", "1.0.0"),),
        )
        result = resolve_capabilities(
            catalog(app_one, library_two, app_two, library_one),
            ("app",),
        )
        self.assertTrue(result.ok)
        assert result.plan is not None
        selected = {item.capability_id: str(item.version) for item in result.plan.capabilities}
        self.assertEqual(selected["app"], "2.0.0")
        self.assertEqual(selected["library"], "1.0.0")

    def test_root_prerelease_is_excluded_but_explicit_dependency_can_select_it(self) -> None:
        preview = descriptor("preview", "2.0.0-alpha.1")
        stable = descriptor("preview", "1.0.0")
        root_result = resolve_capabilities(catalog(preview, stable), ("preview",))
        self.assertTrue(root_result.ok)
        assert root_result.plan is not None
        self.assertEqual(str(root_result.plan.capabilities[0].version), "1.0.0")

        app = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("preview", "2.0.0-alpha.1"),),
        )
        dependency_result = resolve_capabilities(catalog(stable, app, preview), ("app",))
        self.assertTrue(dependency_result.ok, dependency_result.diagnostics)
        assert dependency_result.plan is not None
        selected = {
            item.capability_id: str(item.version)
            for item in dependency_result.plan.capabilities
        }
        self.assertEqual(selected["preview"], "2.0.0-alpha.1")

    def test_nonexplicit_dependency_range_does_not_select_prerelease(self) -> None:
        preview = descriptor("preview", "2.0.0-alpha.1")
        stable = descriptor("preview", "1.0.0")
        app = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("preview", ">=1.0.0,<3.0.0"),),
        )
        result = resolve_capabilities(catalog(preview, app, stable), ("app",))
        self.assertTrue(result.ok)
        assert result.plan is not None
        selected = {item.capability_id: str(item.version) for item in result.plan.capabilities}
        self.assertEqual(selected["preview"], "1.0.0")

    def test_one_explicit_dependency_can_enable_a_compatible_prerelease_intersection(self) -> None:
        preview = descriptor("preview", "2.0.0-alpha.1")
        app = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("preview", "2.0.0-alpha.1"),),
        )
        guard = descriptor(
            "guard",
            "1.0.0",
            dependencies=(dependency("preview", ">=1.0.0,<3.0.0"),),
        )
        result = resolve_capabilities(catalog(guard, preview, app), ("app", "guard"))
        self.assertTrue(result.ok, result.diagnostics)
        assert result.plan is not None
        selected = {item.capability_id: str(item.version) for item in result.plan.capabilities}
        self.assertEqual(selected["preview"], "2.0.0-alpha.1")

    def test_unknown_and_unsatisfied_requirements_have_stable_diagnostics(self) -> None:
        known = descriptor("known", "1.0.0")
        unknown = resolve_capabilities(catalog(known), ("missing",))
        self.assertEqual(
            unknown.diagnostics[0].code,
            CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND,
        )

        app = descriptor(
            "app",
            "1.0.0",
            dependencies=(dependency("known", "2.0.0"),),
        )
        unsatisfied = resolve_capabilities(catalog(app, known), ("app",))
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_VERSION_UNSATISFIED,
            {diagnostic.code for diagnostic in unsatisfied.diagnostics},
        )

    def test_cycle_conflict_namespace_and_safety_are_rejected(self) -> None:
        cycle_a = descriptor(
            "cycle_a",
            "1.0.0",
            dependencies=(dependency("cycle_b", "1.0.0"),),
        )
        cycle_b = descriptor(
            "cycle_b",
            "1.0.0",
            dependencies=(dependency("cycle_a", "1.0.0"),),
        )
        cycle = resolve_capabilities(catalog(cycle_b, cycle_a), ("cycle_a",))
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_DEPENDENCY_CYCLE,
            {diagnostic.code for diagnostic in cycle.diagnostics},
        )

        conflict_a = descriptor(
            "conflict_a",
            "1.0.0",
            conflicts=(CapabilityConflictDescriptor("conflict_b"),),
        )
        conflict_b = descriptor("conflict_b", "1.0.0")
        conflict = resolve_capabilities(
            catalog(conflict_b, conflict_a),
            ("conflict_a", "conflict_b"),
        )
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_CONFLICT,
            {diagnostic.code for diagnostic in conflict.diagnostics},
        )

        namespace_a = descriptor("namespace_a", "1.0.0", namespace="shared")
        namespace_b = descriptor("namespace_b", "1.0.0", namespace="shared_extra")
        namespace = resolve_capabilities(
            catalog(namespace_a, namespace_b),
            ("namespace_b", "namespace_a"),
        )
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_NAMESPACE_OVERLAP,
            {diagnostic.code for diagnostic in namespace.diagnostics},
        )

        denied = descriptor("denied", "1.0.0", safety=CapabilitySafetyLevel.L2)
        safety = resolve_capabilities(catalog(denied), ("denied",))
        self.assertEqual(
            safety.diagnostics[0].code,
            CapabilityDiagnosticCode.CAPABILITY_SAFETY_DENIED,
        )

    def test_migration_path_is_ordered_or_rejected_before_plan_creation(self) -> None:
        version_one = descriptor("counter", "1.0.0")
        version_two_value = SemanticVersion.parse("2.0.0")
        version_two = descriptor(
            "counter",
            "2.0.0",
            migrations=(
                CapabilityMigrationDescriptor(
                    "counter_v1_to_v2",
                    SemanticVersion.parse("1.0.0"),
                    version_two_value,
                ),
            ),
        )
        value_catalog = catalog(version_two, version_one)
        migrated = resolve_capabilities(
            value_catalog,
            ("counter",),
            current_versions=(
                CapabilityStateVersion("counter", SemanticVersion.parse("1.0.0")),
            ),
        )
        self.assertTrue(migrated.ok, migrated.diagnostics)
        assert migrated.plan is not None
        self.assertEqual(
            tuple(step.migration_id for step in migrated.plan.migrations),
            ("counter_v1_to_v2",),
        )

        unavailable = resolve_capabilities(
            value_catalog,
            ("counter",),
            current_versions=(
                CapabilityStateVersion("counter", SemanticVersion.parse("0.5.0")),
            ),
        )
        self.assertIn(
            CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
            {diagnostic.code for diagnostic in unavailable.diagnostics},
        )

    def test_multistep_migration_path_is_deterministic(self) -> None:
        version_one_value = SemanticVersion.parse("1.0.0")
        version_two_value = SemanticVersion.parse("2.0.0")
        version_three_value = SemanticVersion.parse("3.0.0")
        version_one = descriptor("counter", "1.0.0")
        version_two = descriptor(
            "counter",
            "2.0.0",
            migrations=(
                CapabilityMigrationDescriptor(
                    "counter_v1_to_v2",
                    version_one_value,
                    version_two_value,
                ),
            ),
        )
        version_three = descriptor(
            "counter",
            "3.0.0",
            migrations=(
                CapabilityMigrationDescriptor(
                    "counter_v2_to_v3",
                    version_two_value,
                    version_three_value,
                ),
            ),
        )
        result = resolve_capabilities(
            catalog(version_two, version_one, version_three),
            ("counter",),
            current_versions=(CapabilityStateVersion("counter", version_one_value),),
        )
        self.assertTrue(result.ok, result.diagnostics)
        assert result.plan is not None
        self.assertEqual(
            tuple(step.migration_id for step in result.plan.migrations),
            ("counter_v1_to_v2", "counter_v2_to_v3"),
        )

    def test_plan_fingerprint_omits_its_own_field(self) -> None:
        result = resolve_capabilities(catalog(descriptor("counter", "1.0.0")), ("counter",))
        self.assertTrue(result.ok)
        assert result.plan is not None
        document = capability_value_to_document(result.plan)
        assert isinstance(document, dict)
        fingerprint = document.pop("fingerprint")
        self.assertEqual(fingerprint, sha256_bytes(canonical_json_bytes(document)))

    def test_requirement_and_registration_order_do_not_change_diagnostics(self) -> None:
        first = descriptor(
            "first",
            "1.0.0",
            conflicts=(CapabilityConflictDescriptor("second"),),
        )
        second = descriptor("second", "1.0.0")
        forward = resolve_capabilities(catalog(first, second), ("first", "second"))
        reverse = resolve_capabilities(catalog(second, first), ("second", "first"))
        self.assertEqual(forward.diagnostics, reverse.diagnostics)


if __name__ == "__main__":
    unittest.main()
