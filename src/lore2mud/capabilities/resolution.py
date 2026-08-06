"""Deterministic global capability dependency and version resolution."""

from __future__ import annotations

from collections import deque
from dataclasses import replace

from lore2mud.capabilities.catalog import (
    CapabilityCatalog,
    descriptor_fingerprint,
    is_stable_id,
    sort_capability_diagnostics,
)
from lore2mud.capabilities.contracts import (
    CapabilityDependencyEdge,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityDiagnosticCode,
    CapabilityMigrationDescriptor,
    CapabilityMigrationStep,
    CapabilityResolutionResult,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    CapabilityStateVersion,
    ResolvedCapability,
    ResolvedCapabilityPlan,
)
from lore2mud.capabilities.semver import SemanticVersion, VersionRequirement, compare_precedence
from lore2mud.capabilities.serialization import (
    canonical_json_bytes,
    capability_value_to_document,
    sha256_bytes,
)


_MAX_ROOT_REQUIREMENTS = 4096


def resolve_capabilities(
    catalog: CapabilityCatalog,
    requirement_ids: tuple[str, ...],
    *,
    current_versions: tuple[CapabilityStateVersion, ...] = (),
) -> CapabilityResolutionResult:
    """Resolve a deterministic, globally maximal, dependency-first capability plan."""
    input_diagnostics = _validate_resolution_inputs(catalog, requirement_ids, current_versions)
    if input_diagnostics:
        return CapabilityResolutionResult(None, input_diagnostics)

    roots = frozenset(requirement_ids)
    constraints: dict[str, tuple[VersionRequirement, ...]] = {
        capability_id: () for capability_id in sorted(roots)
    }
    valid_solutions: list[
        tuple[dict[str, CapabilityDescriptor], tuple[CapabilityMigrationStep, ...], tuple[str, ...]]
    ] = []
    invalid_solutions: list[
        tuple[dict[str, CapabilityDescriptor], tuple[CapabilityDiagnostic, ...]]
    ] = []
    failures: list[CapabilityDiagnostic] = []

    def search(
        selected: dict[str, CapabilityDescriptor],
        active_constraints: dict[str, tuple[VersionRequirement, ...]],
    ) -> None:
        unselected_ids = sorted(set(active_constraints).difference(selected))
        if not unselected_ids:
            diagnostics, migrations, ordered_ids = _validate_complete_solution(
                catalog,
                selected,
                current_versions,
            )
            if diagnostics:
                invalid_solutions.append((selected.copy(), diagnostics))
            else:
                valid_solutions.append((selected.copy(), migrations, ordered_ids))
            return

        capability_id = unselected_ids[0]
        candidates = _matching_candidates(
            catalog,
            capability_id,
            active_constraints[capability_id],
            is_root=capability_id in roots,
        )
        if not candidates:
            code = (
                CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND
                if not catalog.versions(capability_id)
                else CapabilityDiagnosticCode.CAPABILITY_VERSION_UNSATISFIED
            )
            failures.append(
                CapabilityDiagnostic(
                    code=code,
                    capability_id=capability_id,
                    requirement=_requirement_summary(active_constraints[capability_id]),
                    message=(
                        f"no catalog entry exists for capability {capability_id}"
                        if code is CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND
                        else f"no version of {capability_id} satisfies every active requirement"
                    ),
                )
            )
            return

        for candidate in candidates:
            conflict = _partial_conflict(candidate, selected)
            if conflict is not None:
                failures.append(conflict)
                continue
            next_selected = dict(selected)
            next_selected[capability_id] = candidate
            next_constraints = dict(active_constraints)
            compatible = True
            for dependency in sorted(
                candidate.dependencies,
                key=lambda value: (value.capability_id, str(value.requirement)),
            ):
                existing = next_constraints.get(dependency.capability_id, ())
                next_constraints[dependency.capability_id] = existing + (dependency.requirement,)
                selected_dependency = next_selected.get(dependency.capability_id)
                if selected_dependency is not None and not _matches_constraints(
                    selected_dependency.version,
                    next_constraints[dependency.capability_id],
                    is_root=dependency.capability_id in roots,
                ):
                    failures.append(
                        CapabilityDiagnostic(
                            code=CapabilityDiagnosticCode.CAPABILITY_VERSION_UNSATISFIED,
                            capability_id=dependency.capability_id,
                            requirement=_requirement_summary(
                                next_constraints[dependency.capability_id]
                            ),
                            related_capability_ids=(candidate.capability_id,),
                            message=(
                                f"selected {dependency.capability_id}@"
                                f"{selected_dependency.version} does not satisfy "
                                f"dependency from {candidate.capability_id}"
                            ),
                        )
                    )
                    compatible = False
                    break
            if compatible:
                search(next_selected, next_constraints)

    search({}, constraints)
    if valid_solutions:
        selection, migrations, ordered_ids = _maximal_solution(valid_solutions)
        return CapabilityResolutionResult(
            _build_plan(catalog, roots, selection, migrations, ordered_ids),
            (),
        )
    if invalid_solutions:
        selection, diagnostics = _maximal_invalid_solution(invalid_solutions)
        del selection
        return CapabilityResolutionResult(None, diagnostics)
    return CapabilityResolutionResult(None, _deduplicate_diagnostics(failures))


def _validate_resolution_inputs(
    catalog: CapabilityCatalog,
    requirement_ids: tuple[str, ...],
    current_versions: tuple[CapabilityStateVersion, ...],
) -> tuple[CapabilityDiagnostic, ...]:
    diagnostics: list[CapabilityDiagnostic] = []
    if not isinstance(catalog, CapabilityCatalog):
        return (
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_DESCRIPTOR_INVALID,
                message="resolver requires a validated CapabilityCatalog",
            ),
        )
    if type(requirement_ids) is not tuple or len(requirement_ids) > _MAX_ROOT_REQUIREMENTS:
        diagnostics.append(
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND,
                message="capability requirement IDs must be a bounded tuple",
            )
        )
    else:
        seen_requirements: set[str] = set()
        for index, capability_id in enumerate(requirement_ids):
            if not is_stable_id(capability_id):
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND,
                        capability_id=capability_id if type(capability_id) is str else None,
                        json_pointer=f"/capability_requirement_ids/{index}",
                        message="root capability requirement is not a stable ID",
                    )
                )
            elif capability_id in seen_requirements:
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_DESCRIPTOR_INVALID,
                        capability_id=capability_id,
                        json_pointer=f"/capability_requirement_ids/{index}",
                        message="root capability requirements must be unique",
                    )
                )
            else:
                seen_requirements.add(capability_id)
                if not catalog.versions(capability_id):
                    diagnostics.append(
                        CapabilityDiagnostic(
                            code=CapabilityDiagnosticCode.CAPABILITY_NOT_FOUND,
                            capability_id=capability_id,
                            json_pointer=f"/capability_requirement_ids/{index}",
                            message=f"capability {capability_id} is not in the engine catalog",
                        )
                    )
    if type(current_versions) is not tuple:
        diagnostics.append(
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
                message="current capability versions must be tuple-backed",
            )
        )
    else:
        seen_current: set[str] = set()
        for current in current_versions:
            if not isinstance(current, CapabilityStateVersion) or not is_stable_id(
                getattr(current, "capability_id", None)
            ):
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
                        message="current capability version entry is invalid",
                    )
                )
                continue
            if current.capability_id in seen_current:
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
                        capability_id=current.capability_id,
                        message="current capability versions contain a duplicate ID",
                    )
                )
            seen_current.add(current.capability_id)
    return _deduplicate_diagnostics(diagnostics)


def _matching_candidates(
    catalog: CapabilityCatalog,
    capability_id: str,
    constraints: tuple[VersionRequirement, ...],
    *,
    is_root: bool,
) -> tuple[CapabilityDescriptor, ...]:
    return tuple(
        descriptor
        for descriptor in catalog.versions(capability_id)
        if _matches_constraints(descriptor.version, constraints, is_root=is_root)
    )


def _matches_constraints(
    version: SemanticVersion,
    constraints: tuple[VersionRequirement, ...],
    *,
    is_root: bool,
) -> bool:
    if version.is_prerelease:
        if is_root:
            return False
        prerelease_allowed = any(requirement.allows_prerelease for requirement in constraints)
        if not prerelease_allowed:
            return False
    else:
        prerelease_allowed = False
    return all(
        requirement.matches(version, include_prerelease=prerelease_allowed)
        for requirement in constraints
    )


def _partial_conflict(
    candidate: CapabilityDescriptor,
    selected: dict[str, CapabilityDescriptor],
) -> CapabilityDiagnostic | None:
    for other_id in sorted(selected):
        other = selected[other_id]
        if _declares_conflict(candidate, other) or _declares_conflict(other, candidate):
            return CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_CONFLICT,
                capability_id=candidate.capability_id,
                related_capability_ids=(other.capability_id,),
                message=(
                    f"capability {candidate.capability_id}@{candidate.version} conflicts with "
                    f"{other.capability_id}@{other.version}"
                ),
            )
    return None


def _declares_conflict(
    source: CapabilityDescriptor,
    target: CapabilityDescriptor,
) -> bool:
    for conflict in source.conflicts:
        if conflict.capability_id != target.capability_id:
            continue
        if conflict.requirement is None or conflict.requirement.matches(
            target.version,
            include_prerelease=True,
        ):
            return True
    return False


def _validate_complete_solution(
    catalog: CapabilityCatalog,
    selected: dict[str, CapabilityDescriptor],
    current_versions: tuple[CapabilityStateVersion, ...],
) -> tuple[
    tuple[CapabilityDiagnostic, ...],
    tuple[CapabilityMigrationStep, ...],
    tuple[str, ...],
]:
    diagnostics: list[CapabilityDiagnostic] = []
    for capability_id in sorted(selected):
        descriptor = selected[capability_id]
        if descriptor.safety_level in {CapabilitySafetyLevel.L2, CapabilitySafetyLevel.L3}:
            diagnostics.append(
                CapabilityDiagnostic(
                    code=CapabilityDiagnosticCode.CAPABILITY_SAFETY_DENIED,
                    capability_id=capability_id,
                    message=(
                        f"capability {capability_id}@{descriptor.version} uses denied "
                        f"safety level {descriptor.safety_level.value}"
                    ),
                )
            )
        for dependency in descriptor.dependencies:
            target = selected.get(dependency.capability_id)
            if target is None or not dependency.requirement.matches(
                target.version,
                include_prerelease=dependency.requirement.allows_prerelease,
            ):
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_VERSION_UNSATISFIED,
                        capability_id=dependency.capability_id,
                        requirement=str(dependency.requirement),
                        related_capability_ids=(capability_id,),
                        message=f"dependency required by {capability_id} is unsatisfied",
                    )
                )
        for other_id in sorted(selected):
            if other_id <= capability_id:
                continue
            other = selected[other_id]
            if _declares_conflict(descriptor, other) or _declares_conflict(other, descriptor):
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_CONFLICT,
                        capability_id=capability_id,
                        related_capability_ids=(other_id,),
                        message=f"selected capabilities {capability_id} and {other_id} conflict",
                    )
                )
    diagnostics.extend(_namespace_diagnostics(selected))
    ordered_ids, cycle = _topological_order(selected)
    if cycle:
        diagnostics.append(
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_DEPENDENCY_CYCLE,
                capability_id=cycle[0] if cycle else None,
                related_capability_ids=cycle,
                message="selected capability dependencies contain a cycle",
            )
        )
        ordered_ids = tuple(sorted(selected))
    migrations, migration_diagnostics = _resolve_migrations(
        catalog,
        selected,
        current_versions,
        ordered_ids,
    )
    diagnostics.extend(migration_diagnostics)
    return _deduplicate_diagnostics(diagnostics), migrations, ordered_ids


def _namespace_diagnostics(
    selected: dict[str, CapabilityDescriptor],
) -> tuple[CapabilityDiagnostic, ...]:
    diagnostics: list[CapabilityDiagnostic] = []
    ordered = [selected[capability_id] for capability_id in sorted(selected)]
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            left_namespace = left.state_namespace
            right_namespace = right.state_namespace
            if (
                left_namespace == right_namespace
                or left_namespace.startswith(right_namespace + ".")
                or right_namespace.startswith(left_namespace + ".")
            ):
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_NAMESPACE_OVERLAP,
                        capability_id=left.capability_id,
                        related_capability_ids=(right.capability_id,),
                        message=(
                            f"state namespaces {left_namespace!r} and "
                            f"{right_namespace!r} overlap"
                        ),
                    )
                )
    return tuple(diagnostics)


def _topological_order(
    selected: dict[str, CapabilityDescriptor],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    dependencies: dict[str, set[str]] = {
        capability_id: {
            dependency.capability_id
            for dependency in descriptor.dependencies
            if dependency.capability_id in selected
        }
        for capability_id, descriptor in selected.items()
    }
    dependents: dict[str, set[str]] = {capability_id: set() for capability_id in selected}
    for dependent_id, dependency_ids in dependencies.items():
        for dependency_id in dependency_ids:
            dependents[dependency_id].add(dependent_id)
    ready = sorted(
        (capability_id for capability_id, values in dependencies.items() if not values),
        key=lambda capability_id: (capability_id, str(selected[capability_id].version)),
    )
    ordered: list[str] = []
    while ready:
        capability_id = ready.pop(0)
        ordered.append(capability_id)
        for dependent_id in sorted(dependents[capability_id]):
            dependencies[dependent_id].discard(capability_id)
            if not dependencies[dependent_id] and dependent_id not in ordered and dependent_id not in ready:
                ready.append(dependent_id)
                ready.sort(key=lambda value: (value, str(selected[value].version)))
    if len(ordered) != len(selected):
        cycle = tuple(sorted(set(selected).difference(ordered)))
        return tuple(ordered), cycle
    return tuple(ordered), ()


def _resolve_migrations(
    catalog: CapabilityCatalog,
    selected: dict[str, CapabilityDescriptor],
    current_versions: tuple[CapabilityStateVersion, ...],
    ordered_ids: tuple[str, ...],
) -> tuple[tuple[CapabilityMigrationStep, ...], tuple[CapabilityDiagnostic, ...]]:
    diagnostics: list[CapabilityDiagnostic] = []
    steps_by_id: dict[str, tuple[CapabilityMigrationStep, ...]] = {}
    for current in sorted(current_versions, key=lambda value: value.capability_id):
        target = selected.get(current.capability_id)
        if target is None:
            diagnostics.append(
                CapabilityDiagnostic(
                    code=CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
                    capability_id=current.capability_id,
                    message="current capability state is not present in the resolved plan",
                )
            )
            continue
        if current.version == target.version:
            steps_by_id[current.capability_id] = ()
            continue
        path = _migration_path(
            catalog,
            current.capability_id,
            current.version,
            target.version,
        )
        if path is None:
            diagnostics.append(
                CapabilityDiagnostic(
                    code=CapabilityDiagnosticCode.CAPABILITY_MIGRATION_UNAVAILABLE,
                    capability_id=current.capability_id,
                    requirement=f"{current.version}->{target.version}",
                    message=(
                        f"no engine-shipped migration path exists for {current.capability_id} "
                        f"from {current.version} to {target.version}"
                    ),
                )
            )
            continue
        steps_by_id[current.capability_id] = tuple(
            CapabilityMigrationStep(
                capability_id=current.capability_id,
                from_version=migration.from_version,
                to_version=migration.to_version,
                migration_id=migration.migration_id,
            )
            for migration in path
        )
    ordered_steps = tuple(
        step
        for capability_id in ordered_ids
        for step in steps_by_id.get(capability_id, ())
    )
    return ordered_steps, _deduplicate_diagnostics(diagnostics)


def _migration_path(
    catalog: CapabilityCatalog,
    capability_id: str,
    source: SemanticVersion,
    target: SemanticVersion,
) -> tuple[CapabilityMigrationDescriptor, ...] | None:
    edges = sorted(
        (
            migration
            for descriptor in catalog.versions(capability_id)
            for migration in descriptor.migrations
        ),
        key=lambda value: (
            str(value.from_version),
            str(value.to_version),
            value.migration_id,
        ),
    )
    queue: deque[tuple[SemanticVersion, tuple[CapabilityMigrationDescriptor, ...]]] = deque(
        ((source, ()),)
    )
    visited: set[SemanticVersion] = {source}
    while queue:
        version, path = queue.popleft()
        for migration in edges:
            if migration.from_version != version:
                continue
            next_path = path + (migration,)
            if migration.to_version == target:
                return next_path
            if migration.to_version not in visited:
                visited.add(migration.to_version)
                queue.append((migration.to_version, next_path))
    return None


def _build_plan(
    catalog: CapabilityCatalog,
    roots: frozenset[str],
    selected: dict[str, CapabilityDescriptor],
    migrations: tuple[CapabilityMigrationStep, ...],
    ordered_ids: tuple[str, ...],
) -> ResolvedCapabilityPlan:
    capabilities = tuple(
        ResolvedCapability(
            capability_id=capability_id,
            version=selected[capability_id].version,
            safety_level=selected[capability_id].safety_level,
            state_namespace=selected[capability_id].state_namespace,
            descriptor_sha256=descriptor_fingerprint(selected[capability_id]),
        )
        for capability_id in ordered_ids
    )
    dependency_edges = tuple(
        sorted(
            (
                CapabilityDependencyEdge(
                    dependent_capability_id=descriptor.capability_id,
                    dependency_capability_id=dependency.capability_id,
                    requirement=dependency.requirement,
                )
                for descriptor in selected.values()
                for dependency in descriptor.dependencies
            ),
            key=lambda value: (
                value.dependency_capability_id,
                value.dependent_capability_id,
                str(value.requirement),
            ),
        )
    )
    initial_states = tuple(
        CapabilityStateEntry(
            capability_id=capability_id,
            version=selected[capability_id].version,
            namespace=selected[capability_id].state_namespace,
            state=selected[capability_id].initial_state,
        )
        for capability_id in ordered_ids
    )
    provisional = ResolvedCapabilityPlan(
        format_version=1,
        requirement_ids=tuple(sorted(roots)),
        capabilities=capabilities,
        dependency_edges=dependency_edges,
        migrations=migrations,
        initial_states=initial_states,
        catalog_sha256=catalog.fingerprint,
        fingerprint="",
    )
    document = capability_value_to_document(provisional)
    assert isinstance(document, dict)
    del document["fingerprint"]
    fingerprint = sha256_bytes(canonical_json_bytes(document))
    return replace(provisional, fingerprint=fingerprint)


def _maximal_solution(
    solutions: list[
        tuple[dict[str, CapabilityDescriptor], tuple[CapabilityMigrationStep, ...], tuple[str, ...]]
    ],
) -> tuple[dict[str, CapabilityDescriptor], tuple[CapabilityMigrationStep, ...], tuple[str, ...]]:
    best = solutions[0]
    for candidate in solutions[1:]:
        if _compare_selections(candidate[0], best[0]) > 0:
            best = candidate
    return best


def _maximal_invalid_solution(
    solutions: list[tuple[dict[str, CapabilityDescriptor], tuple[CapabilityDiagnostic, ...]]],
) -> tuple[dict[str, CapabilityDescriptor], tuple[CapabilityDiagnostic, ...]]:
    best = solutions[0]
    for candidate in solutions[1:]:
        if _compare_selections(candidate[0], best[0]) > 0:
            best = candidate
    return best


def _compare_selections(
    left: dict[str, CapabilityDescriptor],
    right: dict[str, CapabilityDescriptor],
) -> int:
    for capability_id in sorted(set(left).union(right)):
        left_descriptor = left.get(capability_id)
        right_descriptor = right.get(capability_id)
        if left_descriptor is None:
            return -1
        if right_descriptor is None:
            return 1
        comparison = compare_precedence(left_descriptor.version, right_descriptor.version)
        if comparison:
            return comparison
    return 0


def _requirement_summary(requirements: tuple[VersionRequirement, ...]) -> str | None:
    if not requirements:
        return None
    return " & ".join(sorted(str(requirement) for requirement in requirements))


def _deduplicate_diagnostics(
    diagnostics: list[CapabilityDiagnostic] | tuple[CapabilityDiagnostic, ...],
) -> tuple[CapabilityDiagnostic, ...]:
    unique: dict[
        tuple[str, str | None, str | None, str, tuple[str, ...], str],
        CapabilityDiagnostic,
    ] = {}
    for diagnostic in diagnostics:
        key = (
            diagnostic.code.value,
            diagnostic.capability_id,
            diagnostic.requirement,
            diagnostic.json_pointer,
            diagnostic.related_capability_ids,
            diagnostic.message,
        )
        unique[key] = diagnostic
    return sort_capability_diagnostics(tuple(unique.values()))
