"""Read-only, player-safe V2-2 and V2-3 proofing projections."""

from __future__ import annotations

from collections.abc import Iterator

from lore2mud.application.contracts import DeterminismContext, GameIntent, GameView
from lore2mud.application.session import GameSession
from lore2mud.authoring.contracts import (
    AdmissibleIntentDescriptor,
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CapabilityAuthoringResult,
    CapabilityPreview,
    CapabilityProofingProjection,
    DiagnosticSeverity,
    GameProject,
    IntentFieldDescriptor,
    PreviewBuild,
    ProofingEdge,
    ProofingNode,
    ProofingProjection,
)
from lore2mud.authoring.preview import (
    PreviewValidationError,
    build_preview,
    materialized_preview_pack,
)
from lore2mud.authoring.serialization import (
    capability_proofing_to_document,
    canonical_json_bytes,
    fingerprint_document,
    game_intent_to_document,
    sha256_bytes,
)
from lore2mud.capabilities.catalog import CapabilityCatalogError
from lore2mud.capabilities.reference import engine_capability_catalog
from lore2mud.capabilities.runtime import CapabilityRuntimeError, CapabilityRuntimeHost
from lore2mud.content.loader import ContentValidationError


MAX_ADMISSIBLE_INTENTS = 1024
MAX_PROOFING_NODES = 4096
MAX_PROOFING_EDGES = 8192
MAX_PROOFING_TEXT = 4096


class ProofingProjectionTooLarge(ValueError):
    pass


ProofingResult = (
    AuthoringResult[ProofingProjection]
    | CapabilityAuthoringResult[CapabilityProofingProjection]
)


def build_proofing_projection(
    project: GameProject,
) -> ProofingResult:
    """Build a projection from public project data and one fresh safe initial view."""
    preview_result = build_preview(project)
    if not preview_result.ok:
        if isinstance(preview_result, CapabilityAuthoringResult):
            return _capability_rejected("proof", preview_result.diagnostics)
        return _rejected("proof", preview_result.diagnostics)
    preview = preview_result.artifact
    assert preview is not None
    if type(preview) is CapabilityPreview:
        return _build_capability_proofing_projection(project, preview)
    assert type(preview) is PreviewBuild
    try:
        with materialized_preview_pack(preview) as pack:
            default = project.blueprint.default_determinism
            session = GameSession.from_content_pack(
                pack,
                player_name="Proofing Player",
                determinism=DeterminismContext(default.seed, default.clock),
            )
            projection = projection_from_view(project, preview, session.view())
    except ProofingProjectionTooLarge:
        return _rejected(
            "proof",
            (
                AuthoringDiagnostic(
                    stage=AuthoringStage.PROOFING,
                    code="proofing_projection_too_large",
                    severity=DiagnosticSeverity.ERROR,
                    artifact_id=project.project_id,
                    json_pointer="/",
                    source_span=None,
                    message="The bounded proofing projection limit was exceeded.",
                    remediation="Reduce public preview entities or admissible actions and retry.",
                ),
            ),
        )
    except (PreviewValidationError, ContentValidationError, OSError):
        return _rejected(
            "proof",
            (
                AuthoringDiagnostic(
                    stage=AuthoringStage.PROOFING,
                    code="proofing_preview_invalid",
                    severity=DiagnosticSeverity.ERROR,
                    artifact_id=project.project_id,
                    json_pointer="/content_files",
                    source_span=None,
                    message="The preview could not be projected in an isolated session.",
                    remediation="Rebuild the preview from valid public-safe V1 content.",
                ),
            ),
        )
    return AuthoringResult(
        format_version=1,
        operation="proof",
        status=AuthoringStatus.SUCCESS,
        artifact=projection,
        diagnostics=(),
        exit_code=0,
    )


def _build_capability_proofing_projection(
    project: GameProject,
    preview: CapabilityPreview,
) -> CapabilityAuthoringResult[CapabilityProofingProjection]:
    """Project only the capability entries already admitted into GameView."""
    try:
        with materialized_preview_pack(preview) as pack:
            default = project.blueprint.default_determinism
            catalog = engine_capability_catalog()
            host = CapabilityRuntimeHost(
                preview.resolved_plan,
                catalog.implementation_registry,
                states=preview.initial_states,
            )
            session = GameSession.from_content_pack(
                pack,
                player_name="Proofing Player",
                determinism=DeterminismContext(default.seed, default.clock),
                capability_host=host,
            )
            view = session.view()
            base_proofing = projection_from_view(project, preview.base_preview, view)
            capability_views = view.capabilities
            if capability_views is None:
                raise CapabilityRuntimeError("capability player view is unavailable")
    except ProofingProjectionTooLarge:
        return _capability_rejected(
            "proof",
            (_projection_too_large_diagnostic(project),),
        )
    except (
        CapabilityCatalogError,
        CapabilityRuntimeError,
        PreviewValidationError,
        ContentValidationError,
        OSError,
    ):
        return _capability_rejected(
            "proof",
            (_capability_projection_invalid_diagnostic(project),),
        )

    without_fingerprint = CapabilityProofingProjection(
        format_version=1,
        project_id=project.project_id,
        capability_preview_fingerprint=preview.fingerprint,
        base_proofing=base_proofing,
        capability_views=capability_views,
        fingerprint="",
        diagnostics=(),
    )
    projection = CapabilityProofingProjection(
        format_version=without_fingerprint.format_version,
        project_id=without_fingerprint.project_id,
        capability_preview_fingerprint=without_fingerprint.capability_preview_fingerprint,
        base_proofing=without_fingerprint.base_proofing,
        capability_views=without_fingerprint.capability_views,
        fingerprint=fingerprint_document(
            capability_proofing_to_document(without_fingerprint)
        ),
        diagnostics=without_fingerprint.diagnostics,
    )
    return _capability_success("proof", projection)


def projection_from_view(
    project: GameProject, preview: PreviewBuild, view: GameView
) -> ProofingProjection:
    """Project stable public relationships without consulting authoritative World."""
    nodes: dict[str, ProofingNode] = {}
    edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, kind: str, label: str) -> str:
        if any(
            not value or len(value) > MAX_PROOFING_TEXT
            for value in (node_id, kind, label)
        ):
            raise ProofingProjectionTooLarge
        if node_id not in nodes and len(nodes) >= MAX_PROOFING_NODES:
            raise ProofingProjectionTooLarge
        nodes[node_id] = ProofingNode(node_id=node_id, kind=kind, label=label)
        return node_id

    def add_edge(source_id: str, target_id: str, kind: str) -> None:
        if any(
            not value or len(value) > MAX_PROOFING_TEXT
            for value in (source_id, target_id, kind)
        ):
            raise ProofingProjectionTooLarge
        edge = (source_id, target_id, kind)
        if edge not in edges and len(edges) >= MAX_PROOFING_EDGES:
            raise ProofingProjectionTooLarge
        edges.add(edge)

    project_node = add_node(
        f"project:{project.project_id}", "project", project.blueprint.title
    )
    blueprint_node = add_node(
        f"blueprint:{project.blueprint.blueprint_id}",
        "blueprint",
        project.blueprint.title,
    )
    add_edge(blueprint_node, project_node, "blueprint_to_project")
    public_trace_nodes = {
        project.project_id: project_node,
        project.blueprint.blueprint_id: blueprint_node,
    }
    for item in project.public_inputs:
        input_node = add_node(
            f"input:{item.artifact_id}", "public_input", item.label
        )
        public_trace_nodes[item.artifact_id] = input_node
        add_edge(input_node, project_node, "input_to_project")
    for trace in project.trace_records:
        source = public_trace_nodes.get(trace.source_artifact_id)
        target = public_trace_nodes.get(trace.target_artifact_id)
        if source is not None and target is not None:
            add_edge(source, target, "trace")

    pack_node = add_node(f"pack:{view.pack.id}", "pack", view.pack.name)
    player_node = add_node(f"player:{view.player.id}", "player", view.player.name)
    room_node = add_node(f"room:{view.room.id}", "room", view.room.name)
    add_edge(project_node, pack_node, "preview_runtime")
    add_edge(player_node, room_node, "located_in")

    for exit_view in view.room.exits:
        target = add_node(
            f"room:{exit_view.target_room_id}", "room", exit_view.target_room_name
        )
        add_edge(room_node, target, "visible_exit")
    for item in view.room.items:
        item_node = add_node(f"item:{item.id}", "room_item", item.name)
        add_edge(room_node, item_node, "contains")
    for item in view.inventory:
        item_node = add_node(f"item:{item.id}", "inventory_item", item.name)
        add_edge(player_node, item_node, "carries")
    for monster in view.room.monsters:
        monster_node = add_node(f"monster:{monster.id}", "monster", monster.name)
        add_edge(room_node, monster_node, "visible_actor")
    for character in view.room.characters:
        character_node = add_node(
            f"character:{character.id}", "character", character.name
        )
        add_edge(room_node, character_node, "visible_actor")
    for quest in view.quests:
        quest_node = add_node(f"quest:{quest.id}", "quest", quest.name)
        add_edge(player_node, quest_node, "visible_quest")
    for scene in view.campaign.scenes:
        scene_node = add_node(f"scene:{scene.id}", "scene", scene.name)
        add_edge(pack_node, scene_node, "visible_scene")
    for interactable in view.campaign.interactables:
        interactable_node = add_node(
            f"interactable:{interactable.id}", "interactable", interactable.name
        )
        add_edge(room_node, interactable_node, "visible_interactable")
    for entry in view.campaign.objectives:
        objective_node = add_node(
            f"objective:{entry.id}", "objective", entry.title
        )
        add_edge(player_node, objective_node, "visible_objective")
    for entry in view.campaign.knowledge:
        knowledge_node = add_node(
            f"knowledge:{entry.id}", "knowledge", entry.title
        )
        add_edge(player_node, knowledge_node, "visible_knowledge")
    if view.dialogue is not None:
        dialogue_node = add_node(
            f"dialogue:{view.dialogue.dialogue_id}",
            "dialogue",
            view.dialogue.character_name,
        )
        add_edge(player_node, dialogue_node, "active_dialogue")
    if view.shop is not None:
        shop_node = add_node(f"shop:{view.shop.id}", "shop", view.shop.name)
        add_edge(room_node, shop_node, "visible_shop")

    descriptors = admissible_intent_descriptors(view)
    if len(nodes) > MAX_PROOFING_NODES or len(edges) > MAX_PROOFING_EDGES:
        raise ProofingProjectionTooLarge
    return ProofingProjection(
        format_version=1,
        project_id=project.project_id,
        preview_fingerprint=preview.fingerprint,
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
        edges=tuple(
            ProofingEdge(source_id=source, target_id=target, kind=kind)
            for source, target, kind in sorted(edges)
        ),
        admissible_intents=descriptors,
        diagnostics=(),
    )


def admissible_intent_descriptors(
    view: GameView,
) -> tuple[AdmissibleIntentDescriptor, ...]:
    """Flatten only typed intents already present in the player-safe GameView."""
    documents: dict[bytes, tuple[GameIntent, dict[str, object]]] = {}
    for intent in _embedded_intents(view):
        document = game_intent_to_document(intent)
        payload = canonical_json_bytes(document)
        if payload not in documents and len(documents) >= MAX_ADMISSIBLE_INTENTS:
            raise ProofingProjectionTooLarge
        documents[payload] = (intent, document)
    return tuple(
        AdmissibleIntentDescriptor(
            descriptor_id=f"intent_{sha256_bytes(payload)[:24]}",
            intent=intent,
            fields=tuple(
                IntentFieldDescriptor(name, _scalar(document[name]))
                for name in sorted(document)
                if name != "type"
            ),
        )
        for payload, (intent, document) in sorted(documents.items())
    )


def _embedded_intents(view: GameView) -> Iterator[GameIntent]:
    if view.player.recover is not None:
        yield view.player.recover
    for exit_view in view.room.exits:
        if exit_view.move is not None:
            yield exit_view.move
    for item in view.room.items:
        yield from item.actions
    for item in view.inventory:
        yield from item.actions
    for monster in view.room.monsters:
        if monster.attack_intent is not None:
            yield monster.attack_intent
    for character in view.room.characters:
        if character.talk is not None:
            yield character.talk
    for equipped in (view.equipment.hand, view.equipment.body):
        if equipped is not None and equipped.unequip is not None:
            yield equipped.unequip
    for action in view.campaign.actions:
        yield action.intent
    if view.dialogue is not None:
        for option in view.dialogue.options:
            yield option.intent
        yield view.dialogue.end
    if view.shop is not None:
        for listing in view.shop.catalog:
            yield from listing.actions


def _scalar(value: object) -> str | int | bool | None:
    if value is None or type(value) in {str, int, bool}:
        return value  # type: ignore[return-value]
    raise TypeError("admissible intent fields must be scalar")


def _rejected(
    operation: str, diagnostics: tuple[AuthoringDiagnostic, ...]
) -> AuthoringResult[ProofingProjection]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=diagnostics,
        exit_code=1,
    )


def _capability_success(
    operation: str,
    artifact: CapabilityProofingProjection,
) -> CapabilityAuthoringResult[CapabilityProofingProjection]:
    return CapabilityAuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.SUCCESS,
        artifact=artifact,
        diagnostics=(),
        exit_code=0,
    )


def _capability_rejected(
    operation: str,
    diagnostics: tuple[AuthoringDiagnostic, ...],
) -> CapabilityAuthoringResult[CapabilityProofingProjection]:
    return CapabilityAuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=diagnostics,
        exit_code=1,
    )


def _projection_too_large_diagnostic(project: GameProject) -> AuthoringDiagnostic:
    return AuthoringDiagnostic(
        stage=AuthoringStage.PROOFING,
        code="proofing_projection_too_large",
        severity=DiagnosticSeverity.ERROR,
        artifact_id=project.project_id,
        json_pointer="/",
        source_span=None,
        message="The bounded proofing projection limit was exceeded.",
        remediation="Reduce public preview entities or admissible actions and retry.",
    )


def _capability_projection_invalid_diagnostic(
    project: GameProject,
) -> AuthoringDiagnostic:
    return AuthoringDiagnostic(
        stage=AuthoringStage.PROOFING,
        code="proofing_preview_invalid",
        severity=DiagnosticSeverity.ERROR,
        artifact_id=project.project_id,
        json_pointer="/content_files",
        source_span=None,
        message="The capability preview could not be projected in an isolated session.",
        remediation="Rebuild the preview from valid public-safe capability inputs.",
    )
