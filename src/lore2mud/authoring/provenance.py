"""Public-safe provenance and rights contracts for traced novel adaptation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
import re
from typing import TypeVar, cast
import unicodedata

from lore2mud.authoring.serialization import (
    canonical_json_bytes,
    normalize_bounded_json_document,
    sha256_bytes,
)


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_COLLECTION = 4096
_MAX_TEXT = 512
_MAX_PRIVATE_ALIAS_REFINEMENT_ROUNDS = 64
_PRIVATE_ID_FRAGMENT_RE = re.compile(
    r"(?:private|novel|canon|chapter|excerpt|secret|diary|"
    r"file_?path|source_?(?:hash|path)|raw_?text)",
    re.IGNORECASE,
)
_PUBLIC_SAFE_SLASH_LABEL_RE = re.compile(
    r"^(?:fixture-extractor(?:/| / )v[0-9]{1,3}|"
    r"story(?:/| / )scene|hand(?:/| / )body)$",
)
_FORBIDDEN_CONTROL_RE = re.compile(
    "[\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0605\u061c\u06dd\u070f\u0890-\u0891\u08e2\u180e"
    "\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb"
    "]"
)
_CONFUSABLE_DELIMITER_NAME_RE = re.compile(r"(?:^|[ -])(?:COLON|SLASH|SOLIDUS)(?:$|[ -])")
_FULLWIDTH_OR_PRESENTATION_ASCII_RANGES = (
    range(0xFE10, 0xFE70),
    range(0xFF01, 0xFF5F),
)
_KNOWN_URI_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:file|data|mailto|javascript|urn|about|blob|"
    r"https?|ftp|ssh|tel)[\t ]*:[\t ]*",
    re.IGNORECASE,
)
_URI_SCHEME_PAYLOAD_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9+.-]*:[^\s]",
    re.IGNORECASE,
)
_PERCENT_ESCAPE_RE = re.compile(r"%[0-9A-Fa-f]{2}")
_OBFUSCATED_SHA256_RE = re.compile(
    r"(?:[0-9A-Fa-f][ \t:_-]*){64}",
)
_PRIVATE_FILENAME_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:private|novel|canon|chapter|excerpt|secret|diary)"
    r"[A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,16}(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_BARE_RELATIVE_PATH_RE = re.compile(
    r"^(?:\.{1,2}|~|\.[A-Za-z0-9][A-Za-z0-9_.-]{0,63}|"
    r"[A-Za-z0-9][A-Za-z0-9_.-]*\."
    r"(?=[A-Za-z0-9]{1,16}$)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{1,16})$"
)
_EnumT = TypeVar("_EnumT", bound=Enum)


class AdaptationMode(str, Enum):
    """The promotion mode for one adaptation record."""

    PROTOTYPE = "prototype"
    TRACED = "traced"
    SEALED = "sealed"


class SourceVisibility(str, Enum):
    """Whether a source reference may expose its public-safe label."""

    PUBLIC_SAFE = "public_safe"
    AUTHORIZED_PRIVATE = "authorized_private"


class RightsStatus(str, Enum):
    """An owner assertion recorded by the engine without making a rights decision."""

    AUTHORIZED = "authorized"
    REVIEW_REQUIRED = "review_required"
    RESTRICTED = "restricted"
    DENIED = "denied"


class CreatorDecisionKind(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    TRANSFORM = "transform"
    DISCLOSURE = "disclosure"
    ROUTING = "routing"


class TransformationKind(str, Enum):
    ADAPT = "adapt"
    BRANCH = "branch"
    COMPOSE = "compose"
    OMIT = "omit"
    SUMMARIZE = "summarize"


@dataclass(frozen=True, slots=True)
class SourceReference:
    """An opaque source reference with no path, excerpt, or source digest field."""

    source_id: str
    source_kind: str
    visibility: SourceVisibility
    public_label: str


@dataclass(frozen=True, slots=True)
class RightsAssertion:
    assertion_id: str
    source_id: str
    status: RightsStatus
    scope: str
    authority: str


@dataclass(frozen=True, slots=True)
class CreatorDecisionRecord:
    decision_id: str
    kind: CreatorDecisionKind
    approved: bool
    rationale: str
    source_ids: tuple[str, ...]
    rights_assertion_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectElement:
    """A stable, non-textual identifier for a material element in GameProject v1."""

    element_id: str
    element_kind: str


@dataclass(frozen=True, slots=True)
class TransformationRecord:
    transformation_id: str
    kind: TransformationKind
    source_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    output_project_element_ids: tuple[str, ...]
    depends_on_transformation_ids: tuple[str, ...] = ()
    deterministic: bool = True


@dataclass(frozen=True, slots=True)
class TraceBinding:
    """One complete source-to-project-to-package provenance chain."""

    binding_id: str
    source_id: str
    rights_assertion_id: str
    decision_id: str
    transformation_id: str
    project_element_id: str
    package_element_id: str


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    format_version: int
    manifest_id: str
    mode: AdaptationMode
    sources: tuple[SourceReference, ...]
    rights_assertions: tuple[RightsAssertion, ...]
    creator_decisions: tuple[CreatorDecisionRecord, ...]
    transformations: tuple[TransformationRecord, ...]
    project_elements: tuple[ProjectElement, ...]
    trace_bindings: tuple[TraceBinding, ...]


@dataclass(frozen=True, slots=True)
class PublicProvenanceAliases:
    """Deterministic public aliases for every private-source graph role."""

    source_ids: dict[str, str]
    assertion_ids: dict[str, str]
    decision_ids: dict[str, str]
    transformation_ids: dict[str, str]
    project_element_ids: dict[str, str]
    binding_ids: dict[str, str]
    package_element_ids: dict[str, str]

    @property
    def has_private_components(self) -> bool:
        return bool(self.source_ids)


class ProvenanceValidationError(ValueError):
    """Raised when a provenance manifest is not structurally or semantically safe."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def provenance_manifest_to_document(manifest: ProvenanceManifest) -> dict[str, object]:
    """Return the canonical public-safe document for a validated manifest."""
    if type(manifest) is not ProvenanceManifest:
        raise ProvenanceValidationError(("value must be a typed ProvenanceManifest v1",))
    return _provenance_manifest_to_document_unchecked(manifest)


def _provenance_manifest_to_document_unchecked(
    manifest: ProvenanceManifest,
) -> dict[str, object]:
    return {
        "format_version": manifest.format_version,
        "manifest_id": manifest.manifest_id,
        "mode": manifest.mode.value,
        "sources": [
            {
                "source_id": value.source_id,
                "source_kind": value.source_kind,
                "visibility": value.visibility.value,
                "public_label": value.public_label,
            }
            for value in sorted(manifest.sources, key=lambda item: item.source_id)
        ],
        "rights_assertions": [
            {
                "assertion_id": value.assertion_id,
                "source_id": value.source_id,
                "status": value.status.value,
                "scope": value.scope,
                "authority": value.authority,
            }
            for value in sorted(manifest.rights_assertions, key=lambda item: item.assertion_id)
        ],
        "creator_decisions": [
            {
                "decision_id": value.decision_id,
                "kind": value.kind.value,
                "approved": value.approved,
                "rationale": value.rationale,
                "source_ids": list(value.source_ids),
                "rights_assertion_ids": list(value.rights_assertion_ids),
            }
            for value in sorted(manifest.creator_decisions, key=lambda item: item.decision_id)
        ],
        "transformations": [
            {
                "transformation_id": value.transformation_id,
                "kind": value.kind.value,
                "source_ids": list(value.source_ids),
                "decision_ids": list(value.decision_ids),
                "output_project_element_ids": list(value.output_project_element_ids),
                "depends_on_transformation_ids": list(value.depends_on_transformation_ids),
                "deterministic": value.deterministic,
            }
            for value in sorted(manifest.transformations, key=lambda item: item.transformation_id)
        ],
        "project_elements": [
            {"element_id": value.element_id, "element_kind": value.element_kind}
            for value in sorted(manifest.project_elements, key=lambda item: item.element_id)
        ],
        "trace_bindings": [
            {
                "binding_id": value.binding_id,
                "source_id": value.source_id,
                "rights_assertion_id": value.rights_assertion_id,
                "decision_id": value.decision_id,
                "transformation_id": value.transformation_id,
                "project_element_id": value.project_element_id,
                "package_element_id": value.package_element_id,
            }
            for value in sorted(manifest.trace_bindings, key=lambda item: item.binding_id)
        ],
    }


def public_provenance_manifest_to_document(
    manifest: ProvenanceManifest,
) -> dict[str, object]:
    """Return an anonymized audit projection for public or authorized-private sources."""
    normalized = validate_provenance_manifest(manifest)
    aliases = _build_public_provenance_aliases(normalized)

    def source_id(value: str) -> str:
        return aliases.source_ids.get(value, value)

    def assertion_id(value: str) -> str:
        return aliases.assertion_ids.get(value, value)

    def decision_id(value: str) -> str:
        return aliases.decision_ids.get(value, value)

    def transformation_id(value: str) -> str:
        return aliases.transformation_ids.get(value, value)

    def project_element_id(value: str) -> str:
        return aliases.project_element_ids.get(value, value)

    def binding_id(value: str) -> str:
        return aliases.binding_ids.get(value, value)

    def package_element_id(value: str) -> str:
        return aliases.package_element_ids.get(value, value)

    return {
        "format_version": normalized.format_version,
        "manifest_id": (
            "provenance_public_projection"
            if aliases.has_private_components
            else normalized.manifest_id
        ),
        "mode": normalized.mode.value,
        "sources": [
            {
                "source_id": source_id(value.source_id),
                "source_kind": (
                    "authorized_source"
                    if value.source_id in aliases.source_ids
                    else value.source_kind
                ),
                "visibility": (
                    SourceVisibility.PUBLIC_SAFE.value
                    if value.source_id in aliases.source_ids
                    else value.visibility.value
                ),
                "public_label": (
                    "Authorized private source"
                    if value.source_id in aliases.source_ids
                    else value.public_label
                ),
            }
            for value in sorted(normalized.sources, key=lambda item: source_id(item.source_id))
        ],
        "rights_assertions": [
            {
                "assertion_id": assertion_id(value.assertion_id),
                "source_id": source_id(value.source_id),
                "status": value.status.value,
                "scope": (
                    "authorized adaptation scope"
                    if value.assertion_id in aliases.assertion_ids
                    else value.scope
                ),
                "authority": (
                    "owner authorization"
                    if value.assertion_id in aliases.assertion_ids
                    else value.authority
                ),
            }
            for value in sorted(
                normalized.rights_assertions,
                key=lambda item: assertion_id(item.assertion_id),
            )
        ],
        "creator_decisions": [
            {
                "decision_id": decision_id(value.decision_id),
                "kind": value.kind.value,
                "approved": value.approved,
                "rationale": (
                    "Creator-approved adaptation decision for an authorized source."
                    if value.decision_id in aliases.decision_ids
                    else value.rationale
                ),
                "source_ids": sorted(source_id(item) for item in value.source_ids),
                "rights_assertion_ids": sorted(
                    assertion_id(item) for item in value.rights_assertion_ids
                ),
            }
            for value in sorted(
                normalized.creator_decisions, key=lambda item: decision_id(item.decision_id)
            )
        ],
        "transformations": [
            {
                "transformation_id": transformation_id(value.transformation_id),
                "kind": value.kind.value,
                "source_ids": sorted(source_id(item) for item in value.source_ids),
                "decision_ids": sorted(decision_id(item) for item in value.decision_ids),
                "output_project_element_ids": sorted(
                    project_element_id(item) for item in value.output_project_element_ids
                ),
                "depends_on_transformation_ids": sorted(
                    transformation_id(item) for item in value.depends_on_transformation_ids
                ),
                "deterministic": value.deterministic,
            }
            for value in sorted(
                normalized.transformations, key=lambda item: transformation_id(item.transformation_id)
            )
        ],
        "project_elements": [
            {"element_id": project_element_id(value.element_id), "element_kind": value.element_kind}
            for value in sorted(
                normalized.project_elements, key=lambda item: project_element_id(item.element_id)
            )
        ],
        "trace_bindings": [
            {
                "binding_id": binding_id(value.binding_id),
                "source_id": source_id(value.source_id),
                "rights_assertion_id": assertion_id(value.rights_assertion_id),
                "decision_id": decision_id(value.decision_id),
                "transformation_id": transformation_id(value.transformation_id),
                "project_element_id": project_element_id(value.project_element_id),
                "package_element_id": package_element_id(value.package_element_id),
            }
            for value in sorted(
                normalized.trace_bindings, key=lambda item: binding_id(item.binding_id)
            )
        ],
    }


def public_provenance_manifest(manifest: ProvenanceManifest) -> ProvenanceManifest:
    """Return a validated typed manifest with private identities anonymized."""
    return load_provenance_manifest_document(public_provenance_manifest_to_document(manifest))


def _aliases(
    prefix: str,
    private_ids: set[str],
    role_keys: dict[str, bytes],
    values: Iterable[object],
    identifier_attribute: str,
) -> dict[str, str]:
    if not private_ids:
        return {}
    used = {
        identifier
        for value in values
        for identifier in (getattr(value, identifier_attribute, None),)
        if isinstance(identifier, str) and identifier not in private_ids
    }
    aliases: dict[str, str] = {}
    counter = 1
    ordered_ids = sorted(private_ids, key=lambda identifier: role_keys[identifier])
    for identifier in ordered_ids:
        alias = f"{prefix}_{counter:04d}"
        while alias in used:
            counter += 1
            alias = f"{prefix}_{counter:04d}"
        aliases[identifier] = alias
        used.add(alias)
        counter += 1
    return aliases


def public_provenance_aliases(manifest: ProvenanceManifest) -> PublicProvenanceAliases:
    """Return deterministic aliases for every role connected to a private source."""
    return _build_public_provenance_aliases(validate_provenance_manifest(manifest))


def _build_public_provenance_aliases(
    normalized: ProvenanceManifest,
) -> PublicProvenanceAliases:
    private_source_nodes = {
        ("source", item.source_id)
        for item in normalized.sources
        if item.visibility is SourceVisibility.AUTHORIZED_PRIVATE
    }
    if not private_source_nodes:
        return PublicProvenanceAliases({}, {}, {}, {}, {}, {}, {})

    source_by_id = {item.source_id: item for item in normalized.sources}
    assertion_by_id = {item.assertion_id: item for item in normalized.rights_assertions}
    decision_by_id = {item.decision_id: item for item in normalized.creator_decisions}
    transformation_by_id = {
        item.transformation_id: item for item in normalized.transformations
    }
    project_element_by_id = {item.element_id: item for item in normalized.project_elements}
    binding_by_id = {item.binding_id: item for item in normalized.trace_bindings}
    package_ids = {item.package_element_id for item in normalized.trace_bindings}
    nodes = {
        *( ("source", identifier) for identifier in source_by_id ),
        *( ("assertion", identifier) for identifier in assertion_by_id ),
        *( ("decision", identifier) for identifier in decision_by_id ),
        *( ("transformation", identifier) for identifier in transformation_by_id ),
        *( ("project_element", identifier) for identifier in project_element_by_id ),
        *( ("binding", identifier) for identifier in binding_by_id ),
        *( ("package_element", identifier) for identifier in package_ids ),
    }
    adjacency: dict[tuple[str, str], list[tuple[str, tuple[str, str]]]] = {
        node: [] for node in nodes
    }

    def add_edge(
        left: tuple[str, str],
        right: tuple[str, str],
        relationship: str,
    ) -> None:
        adjacency[left].append((f"{relationship}:out", right))
        adjacency[right].append((f"{relationship}:in", left))

    for assertion in normalized.rights_assertions:
        add_edge(
            ("assertion", assertion.assertion_id),
            ("source", assertion.source_id),
            "assertion_source",
        )
    for decision in normalized.creator_decisions:
        decision_node = ("decision", decision.decision_id)
        for source_id in decision.source_ids:
            add_edge(decision_node, ("source", source_id), "decision_source")
        for assertion_id in decision.rights_assertion_ids:
            add_edge(decision_node, ("assertion", assertion_id), "decision_assertion")
    for transformation in normalized.transformations:
        transformation_node = ("transformation", transformation.transformation_id)
        for source_id in transformation.source_ids:
            add_edge(transformation_node, ("source", source_id), "transformation_source")
        for decision_id in transformation.decision_ids:
            add_edge(
                transformation_node,
                ("decision", decision_id),
                "transformation_decision",
            )
        for project_element_id in transformation.output_project_element_ids:
            add_edge(
                transformation_node,
                ("project_element", project_element_id),
                "transformation_output",
            )
        for dependency_id in transformation.depends_on_transformation_ids:
            add_edge(
                transformation_node,
                ("transformation", dependency_id),
                "transformation_dependency",
            )
    for binding in normalized.trace_bindings:
        binding_node = ("binding", binding.binding_id)
        add_edge(binding_node, ("source", binding.source_id), "binding_source")
        add_edge(
            binding_node,
            ("assertion", binding.rights_assertion_id),
            "binding_assertion",
        )
        add_edge(binding_node, ("decision", binding.decision_id), "binding_decision")
        add_edge(
            binding_node,
            ("transformation", binding.transformation_id),
            "binding_transformation",
        )
        add_edge(
            binding_node,
            ("project_element", binding.project_element_id),
            "binding_project_element",
        )
        add_edge(
            binding_node,
            ("package_element", binding.package_element_id),
            "binding_package_element",
        )

    connected_nodes: set[tuple[str, str]] = set()
    pending = sorted(private_source_nodes)
    while pending:
        node = pending.pop()
        if node in connected_nodes:
            continue
        connected_nodes.add(node)
        pending.extend(neighbor for _, neighbor in adjacency[node] if neighbor not in connected_nodes)

    def static_signature(node: tuple[str, str]) -> dict[str, object]:
        node_kind, identifier = node
        if node_kind == "source":
            return {
                "node_kind": node_kind,
                "source_kind": "authorized_source",
                "visibility": SourceVisibility.PUBLIC_SAFE.value,
                "public_label": "Authorized private source",
            }
        if node_kind == "assertion":
            assertion = assertion_by_id[identifier]
            return {
                "node_kind": node_kind,
                "status": assertion.status.value,
                "scope": "authorized adaptation scope",
                "authority": "owner authorization",
            }
        if node_kind == "decision":
            decision = decision_by_id[identifier]
            return {
                "node_kind": node_kind,
                "kind": decision.kind.value,
                "approved": decision.approved,
                "rationale": "Creator-approved adaptation decision for an authorized source.",
            }
        if node_kind == "transformation":
            transformation = transformation_by_id[identifier]
            return {
                "node_kind": node_kind,
                "kind": transformation.kind.value,
                "deterministic": transformation.deterministic,
            }
        if node_kind == "project_element":
            return {
                "node_kind": node_kind,
                "element_kind": project_element_by_id[identifier].element_kind,
            }
        return {"node_kind": node_kind}

    def rank(signatures: dict[tuple[str, str], bytes]) -> dict[tuple[str, str], int]:
        ranks = {
            signature: index
            for index, signature in enumerate(sorted(set(signatures.values())))
        }
        return {node: ranks[signature] for node, signature in signatures.items()}

    colors = rank(
        {
            node: canonical_json_bytes(static_signature(node))
            for node in connected_nodes
        }
    )
    for _ in range(_MAX_PRIVATE_ALIAS_REFINEMENT_ROUNDS):
        refined = rank(
            {
                node: canonical_json_bytes(
                    {
                        "self": colors[node],
                        "signature": static_signature(node),
                        "neighbors": [
                            {"relationship": relationship, "color": color}
                            for relationship, color in sorted(
                                (relationship, colors[neighbor])
                                for relationship, neighbor in adjacency[node]
                            )
                        ],
                    }
                )
                for node in connected_nodes
            }
        )
        if len(set(refined.values())) == len(set(colors.values())):
            colors = refined
            break
        colors = refined
    else:
        raise ProvenanceValidationError(
            ("private provenance graph exceeds the public alias refinement limit",)
        )

    role_ids: dict[str, set[str]] = {
        role: {identifier for node_role, identifier in connected_nodes if node_role == role}
        for role in (
            "source",
            "assertion",
            "decision",
            "transformation",
            "project_element",
            "binding",
            "package_element",
        )
    }
    for role, identifiers in role_ids.items():
        role_colors = [colors[(role, identifier)] for identifier in identifiers]
        if len(set(role_colors)) != len(role_colors):
            raise ProvenanceValidationError(
                ("private provenance graph has ambiguous public aliases",)
            )

    def role_keys(role: str) -> dict[str, bytes]:
        return {
            identifier: canonical_json_bytes({"color": colors[(role, identifier)]})
            for identifier in role_ids[role]
        }

    return PublicProvenanceAliases(
        source_ids=_aliases(
            "source_ref", role_ids["source"], role_keys("source"), normalized.sources, "source_id"
        ),
        assertion_ids=_aliases(
            "rights_ref",
            role_ids["assertion"],
            role_keys("assertion"),
            normalized.rights_assertions,
            "assertion_id",
        ),
        decision_ids=_aliases(
            "decision_ref",
            role_ids["decision"],
            role_keys("decision"),
            normalized.creator_decisions,
            "decision_id",
        ),
        transformation_ids=_aliases(
            "transformation_ref",
            role_ids["transformation"],
            role_keys("transformation"),
            normalized.transformations,
            "transformation_id",
        ),
        project_element_ids=_aliases(
            "project_element_ref",
            role_ids["project_element"],
            role_keys("project_element"),
            normalized.project_elements,
            "element_id",
        ),
        binding_ids=_aliases(
            "binding_ref",
            role_ids["binding"],
            role_keys("binding"),
            normalized.trace_bindings,
            "binding_id",
        ),
        package_element_ids=_aliases(
            "package_ref",
            role_ids["package_element"],
            role_keys("package_element"),
            normalized.trace_bindings,
            "package_element_id",
        ),
    )


def public_provenance_decision_aliases(
    manifest: ProvenanceManifest,
) -> dict[str, str]:
    """Return the deterministic public aliases for private-source decisions."""
    return public_provenance_aliases(manifest).decision_ids


def provenance_manifest_bytes(manifest: ProvenanceManifest) -> bytes:
    return canonical_json_bytes(provenance_manifest_to_document(manifest))


def provenance_manifest_sha256(manifest: ProvenanceManifest) -> str:
    return sha256_bytes(provenance_manifest_bytes(manifest))


def public_provenance_manifest_bytes(manifest: ProvenanceManifest) -> bytes:
    return canonical_json_bytes(public_provenance_manifest_to_document(manifest))


def public_provenance_manifest_sha256(manifest: ProvenanceManifest) -> str:
    return sha256_bytes(public_provenance_manifest_bytes(manifest))


def validate_provenance_manifest(manifest: ProvenanceManifest) -> ProvenanceManifest:
    """Normalize a typed manifest through the same bounded JSON boundary as transport."""
    if type(manifest) is not ProvenanceManifest:
        raise ProvenanceValidationError(("value must be a typed ProvenanceManifest v1",))
    try:
        document = _provenance_manifest_to_document_unchecked(manifest)
        normalized = normalize_bounded_json_document(document)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProvenanceValidationError(
            ("typed provenance manifest could not be normalized",)
        ) from exc
    return load_provenance_manifest_document(normalized)


def load_provenance_manifest_document(document: object) -> ProvenanceManifest:
    issues: list[str] = []
    data = _mapping(document, "manifest", issues)
    _keys(
        data,
        {
            "format_version",
            "manifest_id",
            "mode",
            "sources",
            "rights_assertions",
            "creator_decisions",
            "transformations",
            "project_elements",
            "trace_bindings",
        },
        "manifest",
        issues,
    )
    format_version = _integer(data.get("format_version"), "format_version", issues)
    if format_version != 1:
        issues.append("format_version must be 1")
    manifest_id = _stable_id(data.get("manifest_id"), "manifest_id", issues)
    mode = _enum(AdaptationMode, data.get("mode"), "mode", issues, AdaptationMode.PROTOTYPE)
    sources = _load_sources(data.get("sources"), issues)
    assertions = _load_assertions(data.get("rights_assertions"), issues)
    decisions = _load_decisions(data.get("creator_decisions"), issues)
    transformations = _load_transformations(data.get("transformations"), issues)
    project_elements = _load_project_elements(data.get("project_elements"), issues)
    bindings = _load_bindings(data.get("trace_bindings"), issues)

    manifest = ProvenanceManifest(
        format_version=1,
        manifest_id=manifest_id,
        mode=mode,
        sources=sources,
        rights_assertions=assertions,
        creator_decisions=decisions,
        transformations=transformations,
        project_elements=project_elements,
        trace_bindings=bindings,
    )
    _validate_references(manifest, issues)
    if issues:
        raise ProvenanceValidationError(issues)
    return manifest


def _load_sources(value: object, issues: list[str]) -> tuple[SourceReference, ...]:
    entries: list[SourceReference] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "sources", issues)):
        location = f"sources[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {"source_id", "source_kind", "visibility", "public_label"},
            location,
            issues,
        )
        source_id = _stable_id(data.get("source_id"), f"{location}.source_id", issues)
        _duplicate(source_id, seen, f"{location}.source_id", issues)
        visibility = _enum(
            SourceVisibility,
            data.get("visibility"),
            f"{location}.visibility",
            issues,
            SourceVisibility.PUBLIC_SAFE,
        )
        entries.append(
            SourceReference(
                source_id=source_id,
                source_kind=_safe_text(data.get("source_kind"), f"{location}.source_kind", issues),
                visibility=visibility,
                public_label=_safe_text(
                    data.get("public_label"), f"{location}.public_label", issues
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.source_id))


def _load_assertions(value: object, issues: list[str]) -> tuple[RightsAssertion, ...]:
    entries: list[RightsAssertion] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "rights_assertions", issues)):
        location = f"rights_assertions[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {"assertion_id", "source_id", "status", "scope", "authority"},
            location,
            issues,
        )
        assertion_id = _stable_id(data.get("assertion_id"), f"{location}.assertion_id", issues)
        _duplicate(assertion_id, seen, f"{location}.assertion_id", issues)
        entries.append(
            RightsAssertion(
                assertion_id=assertion_id,
                source_id=_stable_id(data.get("source_id"), f"{location}.source_id", issues),
                status=_enum(
                    RightsStatus,
                    data.get("status"),
                    f"{location}.status",
                    issues,
                    RightsStatus.REVIEW_REQUIRED,
                ),
                scope=_safe_text(data.get("scope"), f"{location}.scope", issues),
                authority=_safe_text(data.get("authority"), f"{location}.authority", issues),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.assertion_id))


def _load_decisions(
    value: object,
    issues: list[str],
) -> tuple[CreatorDecisionRecord, ...]:
    entries: list[CreatorDecisionRecord] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "creator_decisions", issues)):
        location = f"creator_decisions[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {
                "decision_id",
                "kind",
                "approved",
                "rationale",
                "source_ids",
                "rights_assertion_ids",
            },
            location,
            issues,
        )
        decision_id = _stable_id(data.get("decision_id"), f"{location}.decision_id", issues)
        _duplicate(decision_id, seen, f"{location}.decision_id", issues)
        entries.append(
            CreatorDecisionRecord(
                decision_id=decision_id,
                kind=_enum(
                    CreatorDecisionKind,
                    data.get("kind"),
                    f"{location}.kind",
                    issues,
                    CreatorDecisionKind.TRANSFORM,
                ),
                approved=_boolean(data.get("approved"), f"{location}.approved", issues),
                rationale=_safe_text(data.get("rationale"), f"{location}.rationale", issues),
                source_ids=_stable_id_set(data.get("source_ids"), f"{location}.source_ids", issues),
                rights_assertion_ids=_stable_id_set(
                    data.get("rights_assertion_ids"),
                    f"{location}.rights_assertion_ids",
                    issues,
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.decision_id))


def _load_transformations(
    value: object,
    issues: list[str],
) -> tuple[TransformationRecord, ...]:
    entries: list[TransformationRecord] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "transformations", issues)):
        location = f"transformations[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {
                "transformation_id",
                "kind",
                "source_ids",
                "decision_ids",
                "output_project_element_ids",
                "depends_on_transformation_ids",
                "deterministic",
            },
            location,
            issues,
        )
        transformation_id = _stable_id(
            data.get("transformation_id"), f"{location}.transformation_id", issues
        )
        _duplicate(transformation_id, seen, f"{location}.transformation_id", issues)
        entries.append(
            TransformationRecord(
                transformation_id=transformation_id,
                kind=_enum(
                    TransformationKind,
                    data.get("kind"),
                    f"{location}.kind",
                    issues,
                    TransformationKind.ADAPT,
                ),
                source_ids=_stable_id_set(data.get("source_ids"), f"{location}.source_ids", issues),
                decision_ids=_stable_id_set(
                    data.get("decision_ids"), f"{location}.decision_ids", issues
                ),
                output_project_element_ids=_stable_id_set(
                    data.get("output_project_element_ids"),
                    f"{location}.output_project_element_ids",
                    issues,
                ),
                depends_on_transformation_ids=_stable_id_set(
                    data.get("depends_on_transformation_ids"),
                    f"{location}.depends_on_transformation_ids",
                    issues,
                ),
                deterministic=_boolean(
                    data.get("deterministic"), f"{location}.deterministic", issues
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.transformation_id))


def _load_project_elements(
    value: object,
    issues: list[str],
) -> tuple[ProjectElement, ...]:
    entries: list[ProjectElement] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "project_elements", issues)):
        location = f"project_elements[{index}]"
        data = _mapping(raw, location, issues)
        _keys(data, {"element_id", "element_kind"}, location, issues)
        element_id = _stable_id(data.get("element_id"), f"{location}.element_id", issues)
        _duplicate(element_id, seen, f"{location}.element_id", issues)
        entries.append(
            ProjectElement(
                element_id=element_id,
                element_kind=_safe_text(
                    data.get("element_kind"), f"{location}.element_kind", issues
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.element_id))


def _load_bindings(value: object, issues: list[str]) -> tuple[TraceBinding, ...]:
    entries: list[TraceBinding] = []
    seen: set[str] = set()
    for index, raw in enumerate(_bounded_list(value, "trace_bindings", issues)):
        location = f"trace_bindings[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {
                "binding_id",
                "source_id",
                "rights_assertion_id",
                "decision_id",
                "transformation_id",
                "project_element_id",
                "package_element_id",
            },
            location,
            issues,
        )
        binding_id = _stable_id(data.get("binding_id"), f"{location}.binding_id", issues)
        _duplicate(binding_id, seen, f"{location}.binding_id", issues)
        entries.append(
            TraceBinding(
                binding_id=binding_id,
                source_id=_stable_id(data.get("source_id"), f"{location}.source_id", issues),
                rights_assertion_id=_stable_id(
                    data.get("rights_assertion_id"),
                    f"{location}.rights_assertion_id",
                    issues,
                ),
                decision_id=_stable_id(data.get("decision_id"), f"{location}.decision_id", issues),
                transformation_id=_stable_id(
                    data.get("transformation_id"),
                    f"{location}.transformation_id",
                    issues,
                ),
                project_element_id=_stable_id(
                    data.get("project_element_id"),
                    f"{location}.project_element_id",
                    issues,
                ),
                package_element_id=_stable_id(
                    data.get("package_element_id"),
                    f"{location}.package_element_id",
                    issues,
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.binding_id))


def _validate_references(manifest: ProvenanceManifest, issues: list[str]) -> None:
    sources = {item.source_id: item for item in manifest.sources}
    assertions = {item.assertion_id: item for item in manifest.rights_assertions}
    decisions = {item.decision_id: item for item in manifest.creator_decisions}
    transformations = {item.transformation_id: item for item in manifest.transformations}
    elements = {item.element_id for item in manifest.project_elements}

    for assertion in manifest.rights_assertions:
        if assertion.source_id not in sources:
            issues.append("rights assertion references an unknown source")
    for decision in manifest.creator_decisions:
        if not decision.source_ids:
            issues.append("creator decision must reference at least one source")
        if not decision.rights_assertion_ids:
            issues.append("creator decision must reference at least one rights assertion")
        if any(source_id not in sources for source_id in decision.source_ids):
            issues.append("creator decision references an unknown source")
        if any(assertion_id not in assertions for assertion_id in decision.rights_assertion_ids):
            issues.append("creator decision references an unknown rights assertion")
        for assertion_id in decision.rights_assertion_ids:
            assertion = assertions.get(assertion_id)
            if assertion is not None and assertion.source_id not in decision.source_ids:
                issues.append("creator decision rights do not cover its source set")
    for transformation in manifest.transformations:
        if not transformation.source_ids:
            issues.append("transformation must reference at least one source")
        if not transformation.decision_ids:
            issues.append("transformation must reference at least one creator decision")
        if not transformation.output_project_element_ids:
            issues.append("transformation must output at least one project element")
        if any(source_id not in sources for source_id in transformation.source_ids):
            issues.append("transformation references an unknown source")
        if any(decision_id not in decisions for decision_id in transformation.decision_ids):
            issues.append("transformation references an unknown creator decision")
        if any(
            element_id not in elements for element_id in transformation.output_project_element_ids
        ):
            issues.append("transformation references an unknown project element")
        if any(
            dependency_id not in transformations
            for dependency_id in transformation.depends_on_transformation_ids
        ):
            issues.append("transformation references an unknown dependency")
    _reject_transformation_cycles(transformations, issues)

    bound_elements: set[str] = set()
    bound_packages: set[str] = set()
    transformation_outputs: set[str] = set()
    for transformation in manifest.transformations:
        for element_id in transformation.output_project_element_ids:
            if element_id in transformation_outputs:
                issues.append("project element has more than one transformation output")
            transformation_outputs.add(element_id)
    for binding in manifest.trace_bindings:
        assertion = assertions.get(binding.rights_assertion_id)
        decision = decisions.get(binding.decision_id)
        transformation = transformations.get(binding.transformation_id)
        if binding.source_id not in sources:
            issues.append("trace binding references an unknown source")
        if assertion is None:
            issues.append("trace binding references an unknown rights assertion")
        elif assertion.source_id != binding.source_id:
            issues.append("trace binding rights assertion does not match its source")
        if decision is None:
            issues.append("trace binding references an unknown creator decision")
        elif (
            binding.source_id not in decision.source_ids
            or binding.rights_assertion_id not in decision.rights_assertion_ids
        ):
            issues.append("trace binding creator decision does not cover its source and rights")
        if transformation is None:
            issues.append("trace binding references an unknown transformation")
        elif (
            binding.source_id not in transformation.source_ids
            or binding.decision_id not in transformation.decision_ids
            or binding.project_element_id not in transformation.output_project_element_ids
        ):
            issues.append("trace binding transformation does not cover the complete chain")
        if binding.project_element_id not in elements:
            issues.append("trace binding references an unknown project element")
        if binding.project_element_id in bound_elements:
            issues.append("project element has more than one trace binding")
        if binding.package_element_id in bound_packages:
            issues.append("package element has more than one trace binding")
        bound_elements.add(binding.project_element_id)
        bound_packages.add(binding.package_element_id)

    if manifest.mode is not AdaptationMode.PROTOTYPE and set(elements) != bound_elements:
        issues.append("every project element must have one complete trace binding")
    if manifest.mode is not AdaptationMode.PROTOTYPE and not manifest.trace_bindings:
        issues.append("traced and sealed manifests require trace bindings")
    if manifest.mode is not AdaptationMode.PROTOTYPE:
        for transformation in manifest.transformations:
            related_bindings = [
                binding
                for binding in manifest.trace_bindings
                if binding.transformation_id == transformation.transformation_id
            ]
            if {binding.source_id for binding in related_bindings} != set(
                transformation.source_ids
            ):
                issues.append("transformation sources are not completely trace-bound")
            if {binding.decision_id for binding in related_bindings} != set(
                transformation.decision_ids
            ):
                issues.append("transformation decisions are not completely trace-bound")
            for decision_id in transformation.decision_ids:
                decision = decisions.get(decision_id)
                if decision is None:
                    continue
                decision_bindings = [
                    binding for binding in related_bindings if binding.decision_id == decision_id
                ]
                if {binding.source_id for binding in decision_bindings} != set(
                    decision.source_ids
                ) or {binding.rights_assertion_id for binding in decision_bindings} != set(
                    decision.rights_assertion_ids
                ):
                    issues.append("creator decision rights are not completely trace-bound")
    for binding in manifest.trace_bindings:
        assertion = assertions.get(binding.rights_assertion_id)
        if assertion is not None and manifest.mode is not AdaptationMode.PROTOTYPE:
            if assertion.status is RightsStatus.DENIED:
                issues.append("traced content cannot use denied rights")
            if (
                manifest.mode is AdaptationMode.SEALED
                and assertion.status is not RightsStatus.AUTHORIZED
            ):
                issues.append("sealed content requires authorized rights")

    if manifest.mode is AdaptationMode.TRACED and any(
        assertion.status is RightsStatus.DENIED for assertion in manifest.rights_assertions
    ):
        issues.append("traced content cannot contain denied rights")
    if manifest.mode is AdaptationMode.SEALED:
        if any(
            assertion.status is not RightsStatus.AUTHORIZED
            for assertion in manifest.rights_assertions
        ):
            issues.append("sealed content requires authorized rights")
        if any(not decision.approved for decision in manifest.creator_decisions):
            issues.append("sealed content requires approved creator decisions")
        if any(not transformation.deterministic for transformation in manifest.transformations):
            issues.append("sealed content requires deterministic transformations")


def _reject_transformation_cycles(
    transformations: dict[str, TransformationRecord],
    issues: list[str],
) -> None:
    """Detect dependency cycles without recursing through untrusted graph depth."""
    visited: set[str] = set()
    for identifier in sorted(transformations):
        if identifier in visited:
            continue
        active: set[str] = set()
        stack: list[tuple[str, bool]] = [(identifier, False)]
        while stack:
            current, completed = stack.pop()
            if current in visited:
                continue
            if completed:
                active.remove(current)
                visited.add(current)
                continue
            if current in active:
                issues.append("transformation dependencies contain a cycle")
                return
            active.add(current)
            stack.append((current, True))
            for dependency in reversed(transformations[current].depends_on_transformation_ids):
                if dependency not in transformations or dependency in visited:
                    continue
                if dependency in active:
                    issues.append("transformation dependencies contain a cycle")
                    return
                stack.append((dependency, False))


def _mapping(value: object, location: str, issues: list[str]) -> dict[str, object]:
    if type(value) is not dict:
        issues.append(f"{location} must be an object")
        return {}
    if not all(type(key) is str for key in value):
        issues.append(f"{location} keys must be strings")
        return {}
    return cast(dict[str, object], value)


def _keys(
    data: dict[str, object],
    expected: set[str],
    location: str,
    issues: list[str],
) -> None:
    if set(data) != expected:
        issues.append(f"{location} fields are invalid")


def _bounded_list(value: object, location: str, issues: list[str]) -> list[object]:
    if type(value) is not list:
        issues.append(f"{location} must be an array")
        return []
    values = cast(list[object], value)
    if len(values) > _MAX_COLLECTION:
        issues.append(f"{location} exceeds {_MAX_COLLECTION} entries")
        return values[:_MAX_COLLECTION]
    return values


def _stable_id(value: object, location: str, issues: list[str]) -> str:
    if type(value) is not str or _STABLE_ID_RE.fullmatch(value) is None:
        issues.append(f"{location} must be a stable ID")
        return "invalid_id"
    if not is_opaque_public_id(value):
        issues.append(f"{location} must be an opaque public-safe ID")
        return "invalid_id"
    return value


def _stable_id_set(value: object, location: str, issues: list[str]) -> tuple[str, ...]:
    values = _bounded_list(value, location, issues)
    identifiers = [
        _stable_id(item, f"{location}[{index}]", issues) for index, item in enumerate(values)
    ]
    if len(set(identifiers)) != len(identifiers):
        issues.append(f"{location} contains duplicate IDs")
    return tuple(sorted(set(identifiers)))


def _safe_text(value: object, location: str, issues: list[str]) -> str:
    if type(value) is not str or not value.strip():
        issues.append(f"{location} must be non-blank text")
        return "invalid"
    if len(value) > _MAX_TEXT:
        issues.append(f"{location} exceeds the public-safe text limit")
        return "invalid"
    if any(ord(character) < 32 for character in value) or not is_public_safe_text(value):
        issues.append(f"{location} is not public-safe")
        return "invalid"
    return value.strip()


def is_opaque_public_id(value: object) -> bool:
    if type(value) is not str or _STABLE_ID_RE.fullmatch(value) is None:
        return False
    return _PRIVATE_ID_FRAGMENT_RE.search(value) is None


def is_public_safe_text(value: object) -> bool:
    if type(value) is not str:
        return False
    if _FORBIDDEN_CONTROL_RE.search(value) or any(
        unicodedata.category(character) in {"Cc", "Cf"} for character in value
    ):
        return False
    if _contains_confusable_public_delimiter(value):
        return False
    candidate = value.strip()
    if (
        not candidate
        or _KNOWN_URI_RE.search(candidate)
        or _URI_SCHEME_PAYLOAD_RE.search(candidate)
        or _PERCENT_ESCAPE_RE.search(candidate)
        or _OBFUSCATED_SHA256_RE.search(candidate)
        or _PRIVATE_FILENAME_RE.search(candidate)
        or _BARE_RELATIVE_PATH_RE.fullmatch(candidate)
        or "\\" in candidate
    ):
        return False
    return "/" not in candidate or (
        candidate == value and _PUBLIC_SAFE_SLASH_LABEL_RE.fullmatch(candidate) is not None
    )


def _contains_confusable_public_delimiter(value: str) -> bool:
    for character in value:
        if ord(character) <= 0x7F:
            continue
        normalized = unicodedata.normalize("NFKC", character)
        if normalized in {":", "/", "\\"}:
            return True
        if _CONFUSABLE_DELIMITER_NAME_RE.search(unicodedata.name(character, "")):
            return True
    normalized_value = unicodedata.normalize("NFKC", value)
    return any(
        ord(character) in character_range
        for character in value
        for character_range in _FULLWIDTH_OR_PRESENTATION_ASCII_RANGES
    ) and (
        _KNOWN_URI_RE.search(normalized_value) is not None
        or _URI_SCHEME_PAYLOAD_RE.search(normalized_value) is not None
        or "\\" in normalized_value
    )


def _integer(value: object, location: str, issues: list[str]) -> int:
    if type(value) is not int:
        issues.append(f"{location} must be an integer")
        return 0
    return value


def _boolean(value: object, location: str, issues: list[str]) -> bool:
    if type(value) is not bool:
        issues.append(f"{location} must be a boolean")
        return False
    return value


def _enum(
    enum_type: type[_EnumT],
    value: object,
    location: str,
    issues: list[str],
    fallback: _EnumT,
) -> _EnumT:
    if type(value) is not str:
        issues.append(f"{location} must be a supported value")
        return fallback
    try:
        return enum_type(value)
    except ValueError:
        issues.append(f"{location} must be a supported value")
        return fallback


def _duplicate(value: str, seen: set[str], location: str, issues: list[str]) -> None:
    if value in seen:
        issues.append(f"{location} is duplicated")
    seen.add(value)
