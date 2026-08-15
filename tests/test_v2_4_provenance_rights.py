"""V2-4A public-safe provenance, sealing, identity, and anchor contracts."""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud.application import (
    AttackIntent,
    BuyIntent,
    ChooseDialogueIntent,
    EquipIntent,
    MoveIntent,
    TakeIntent,
    TalkIntent,
)
from lore2mud._bounded_json import (
    BoundedJsonError,
    DEFAULT_JSON_READ_LIMITS,
    JsonReadErrorCode,
    parse_bounded_json,
)
from lore2mud.authoring import AuthoringWebTransport
from lore2mud.authoring.anchors import (
    AnchorKind,
    AnchorMigration,
    AnchorValidationError,
    StoryAnchor,
    anchor_migration_to_document,
    story_anchor_to_document,
    validate_anchor_migrations,
)
from lore2mud.authoring.contracts import (
    AuthoringStatus,
    ConditionOutcome,
    CreatorDecision,
    PlayLength,
    PublicInputDescriptor,
    SimulationCondition,
    SimulationConditionKind,
    SimulationOutcome,
    SimulationReport,
    SimulationRequest,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.packages import (
    GamePackageV2,
    PackageElement,
    PackageValidationError,
    SealMode,
    SealRequest,
    canonical_evidence_manifest_bytes,
    canonical_game_package_bytes,
    game_package_candidate_id,
    game_package_sha256,
    game_package_to_document,
    load_game_package_document,
    load_seal_candidate_document,
    load_seal_request_document,
    reseal_game_package,
    seal_request_to_document,
)
from lore2mud.authoring.project import create_game_project, load_blueprint
from lore2mud.authoring.provenance import (
    AdaptationMode,
    CreatorDecisionKind,
    CreatorDecisionRecord,
    ProjectElement,
    ProvenanceManifest,
    ProvenanceValidationError,
    RightsAssertion,
    RightsStatus,
    SourceReference,
    SourceVisibility,
    TraceBinding,
    TransformationKind,
    TransformationRecord,
    load_provenance_manifest_document,
    provenance_manifest_to_document,
    public_provenance_manifest_to_document,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    canonical_json_bytes,
    diagnostic_to_document,
    sha256_bytes,
)
from lore2mud.authoring.service import AuthoringService
from lore2mud.web.app import AuthoringWebTransport as WebAuthoringTransport


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "examples" / "original_demo"
BLUEPRINT = ROOT / "tests" / "fixtures" / "authoring" / "blueprint.json"


def _schema_registry() -> tuple[dict[str, object], Registry]:
    schemas = {
        document["$id"]: document
        for path in (ROOT / "schemas").glob("*.schema.json")
        for document in [json.loads(path.read_text(encoding="utf-8"))]
        if "$id" in document
    }
    registry = Registry().with_resources(
        (uri, Resource.from_contents(document)) for uri, document in schemas.items()
    )
    return schemas, registry


class V2_4Fixture(unittest.TestCase):
    _short_simulation_report: SimulationReport

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        fixture = cls()
        result = AuthoringService().simulate(
            fixture.project(),
            SimulationRequest(
                format_version=1,
                seed=20260807,
                clock=1930,
                player_name="Public Arc Player",
                intents=(),
                checkpoint_after_steps=(0,),
            ),
        )
        if not result.ok or type(result.artifact) is not SimulationReport:
            raise AssertionError("public-safe simulation fixture must be replay-verifiable")
        cls._short_simulation_report = result.artifact

    def project(
        self,
        project_id: str = "public_signal_project",
        *,
        include_project_trace: bool = True,
        trace_source_id: str = "source_public_arc",
        trace_decision_id: str = "decision_public_arc",
        trace_element_ids: tuple[str, ...] = (
            "element_opening",
            "element_signal",
            "element_choice",
            "element_resolution",
        ),
    ):
        blueprint = load_blueprint(BLUEPRINT)
        blueprint = replace(
            blueprint,
            title="Public Signal Arc",
            play_length=PlayLength(30, 45, 60),
        )
        return create_game_project(
            project_id=project_id,
            blueprint=blueprint,
            content_root=CONTENT,
            public_inputs=(
                PublicInputDescriptor(
                    "public_arc_brief",
                    "application/json",
                    "Public synthetic story arc",
                ),
            ),
            creator_decisions=(
                (
                    CreatorDecision(
                        trace_decision_id,
                        "Include the public synthetic arc.",
                    ),
                )
                if include_project_trace
                else ()
            ),
            trace_records=(
                tuple(
                    TraceRecord(
                        f"trace_{suffix}",
                        trace_source_id,
                        element_id,
                        trace_decision_id,
                    )
                    for suffix, element_id in zip(
                        ("opening", "signal", "choice", "resolution"),
                        trace_element_ids,
                        strict=True,
                    )
                )
                if include_project_trace
                else ()
            ),
        )

    def provenance(self) -> ProvenanceManifest:
        sources = (
            SourceReference(
                "source_public_arc",
                "synthetic_story",
                SourceVisibility.PUBLIC_SAFE,
                "Public synthetic story arc",
            ),
        )
        rights = (
            RightsAssertion(
                "rights_public_arc",
                "source_public_arc",
                RightsStatus.AUTHORIZED,
                "public adaptation",
                "fixture_owner",
            ),
        )
        decisions = (
            CreatorDecisionRecord(
                "decision_public_arc",
                CreatorDecisionKind.INCLUDE,
                True,
                "Include the public synthetic arc.",
                ("source_public_arc",),
                ("rights_public_arc",),
            ),
        )
        elements = tuple(
            ProjectElement(element_id, "story_element")
            for element_id in (
                "element_opening",
                "element_signal",
                "element_choice",
                "element_resolution",
            )
        )
        transformations = tuple(
            TransformationRecord(
                transformation_id=f"transform_{suffix}",
                kind=TransformationKind.ADAPT,
                source_ids=("source_public_arc",),
                decision_ids=("decision_public_arc",),
                output_project_element_ids=(element_id,),
                depends_on_transformation_ids=((f"transform_{previous}",) if previous else ()),
            )
            for suffix, element_id, previous in (
                ("opening", "element_opening", ""),
                ("signal", "element_signal", "opening"),
                ("choice", "element_choice", "signal"),
                ("resolution", "element_resolution", "choice"),
            )
        )
        bindings = tuple(
            TraceBinding(
                f"binding_{suffix}",
                "source_public_arc",
                "rights_public_arc",
                "decision_public_arc",
                f"transform_{suffix}",
                element_id,
                f"package_{suffix}",
            )
            for suffix, element_id in (
                ("opening", "element_opening"),
                ("signal", "element_signal"),
                ("choice", "element_choice"),
                ("resolution", "element_resolution"),
            )
        )
        return ProvenanceManifest(
            format_version=1,
            manifest_id="public_signal_provenance",
            mode=AdaptationMode.SEALED,
            sources=sources,
            rights_assertions=rights,
            creator_decisions=decisions,
            transformations=transformations,
            project_elements=elements,
            trace_bindings=bindings,
        )

    def request(self) -> SealRequest:
        elements = tuple(
            PackageElement(
                package_element_id=f"package_{suffix}",
                project_element_id=f"element_{suffix}",
                element_kind="story_element",
                data={
                    "arc_step": suffix,
                    "player_safe": True,
                },
            )
            for suffix in ("opening", "signal", "choice", "resolution")
        )
        anchors = tuple(
            StoryAnchor(
                anchor_id=f"anchor_{kind.value}_{suffix}",
                kind=kind,
                project_element_id=f"element_{suffix}",
                package_element_id=f"package_{suffix}",
            )
            for kind, suffix in (
                (AnchorKind.STORY, "opening"),
                (AnchorKind.SCENE, "choice"),
                (AnchorKind.RESUME, "resolution"),
            )
        )
        return SealRequest(
            project=self.project(),
            provenance=self.provenance(),
            elements=elements,
            anchors=anchors,
            simulation_reports=(self._short_simulation_report,),
            seal_mode=SealMode.INITIAL,
        )

    def private_alias_request(self) -> SealRequest:
        """A public-safe synthetic private source whose internal IDs must not escape."""
        marker = "unpublishedtitle"
        base = self.request()
        suffixes = ("opening", "signal", "choice", "resolution")
        source_id = f"{marker}_source"
        rights_id = f"{marker}_rights"
        decision_id = f"{marker}_decision"
        transformation_ids = {
            f"transform_{suffix}": f"{marker}_transformation_{suffix}"
            for suffix in suffixes
        }
        project_element_ids = {
            f"element_{suffix}": f"{marker}_project_element_{suffix}"
            for suffix in suffixes
        }
        binding_ids = {
            f"binding_{suffix}": f"{marker}_binding_{suffix}" for suffix in suffixes
        }
        package_element_ids = {
            f"package_{suffix}": f"{marker}_package_element_{suffix}"
            for suffix in suffixes
        }
        provenance = replace(
            base.provenance,
            manifest_id=f"{marker}_manifest",
            sources=(
                replace(
                    base.provenance.sources[0],
                    source_id=source_id,
                    visibility=SourceVisibility.AUTHORIZED_PRIVATE,
                    public_label="Owner-controlled material",
                ),
            ),
            rights_assertions=(
                replace(
                    base.provenance.rights_assertions[0],
                    assertion_id=rights_id,
                    source_id=source_id,
                    scope=f"{marker} adaptation scope",
                    authority=f"{marker} authorization record",
                ),
            ),
            creator_decisions=(
                replace(
                    base.provenance.creator_decisions[0],
                    decision_id=decision_id,
                    rationale=f"{marker} creator rationale",
                    source_ids=(source_id,),
                    rights_assertion_ids=(rights_id,),
                ),
            ),
            transformations=tuple(
                replace(
                    transformation,
                    transformation_id=transformation_ids[transformation.transformation_id],
                    source_ids=(source_id,),
                    decision_ids=(decision_id,),
                    output_project_element_ids=tuple(
                        project_element_ids[item]
                        for item in transformation.output_project_element_ids
                    ),
                    depends_on_transformation_ids=tuple(
                        transformation_ids[item]
                        for item in transformation.depends_on_transformation_ids
                    ),
                )
                for transformation in base.provenance.transformations
            ),
            project_elements=tuple(
                replace(element, element_id=project_element_ids[element.element_id])
                for element in base.provenance.project_elements
            ),
            trace_bindings=tuple(
                replace(
                    binding,
                    binding_id=binding_ids[binding.binding_id],
                    source_id=source_id,
                    rights_assertion_id=rights_id,
                    decision_id=decision_id,
                    transformation_id=transformation_ids[binding.transformation_id],
                    project_element_id=project_element_ids[binding.project_element_id],
                    package_element_id=package_element_ids[binding.package_element_id],
                )
                for binding in base.provenance.trace_bindings
            ),
        )
        project = self.project(
            trace_source_id=source_id,
            trace_decision_id=decision_id,
            trace_element_ids=tuple(
                project_element_ids[f"element_{suffix}"] for suffix in suffixes
            ),
        )
        simulation = AuthoringService().simulate(
            project,
            SimulationRequest(
                format_version=1,
                seed=20260807,
                clock=1930,
                player_name="Public Arc Player",
                intents=(),
                checkpoint_after_steps=(0,),
            ),
        )
        if not simulation.ok or type(simulation.artifact) is not SimulationReport:
            raise AssertionError("private alias fixture must be replay-verifiable")
        return SealRequest(
            project=project,
            provenance=provenance,
            elements=tuple(
                replace(
                    element,
                    package_element_id=package_element_ids[element.package_element_id],
                    project_element_id=project_element_ids[element.project_element_id],
                )
                for element in base.elements
            ),
            anchors=tuple(
                replace(
                    anchor,
                    project_element_id=project_element_ids[anchor.project_element_id],
                    package_element_id=package_element_ids[anchor.package_element_id],
                )
                for anchor in base.anchors
            ),
            simulation_reports=(simulation.artifact,),
            seal_mode=SealMode.INITIAL,
        )

    def sealed_package(self, request: SealRequest) -> GamePackageV2:
        result = AuthoringService().seal(request)
        self.assertTrue(result.ok)
        assert result.artifact is not None
        return result.artifact.package

    def story_arc_simulation_request(self) -> SimulationRequest:
        intents = (
            TakeIntent("item_crystal_blade"),
            EquipIntent("item_crystal_blade"),
            TakeIntent("item_bronze_scale_mail"),
            EquipIntent("item_bronze_scale_mail"),
            TakeIntent("item_linglu_pill", 2),
            MoveIntent("east"),
            TalkIntent("character_elder_chen"),
            ChooseDialogueIntent(4),
            ChooseDialogueIntent(2),
            BuyIntent("item_linglu_pill", 2),
            MoveIntent("east"),
            AttackIntent("monster_ash_mite"),
            AttackIntent("monster_ash_mite"),
            TakeIntent("item_ash_mite_gel"),
            MoveIntent("east"),
            AttackIntent("monster_spark_hound"),
            AttackIntent("monster_spark_hound"),
            MoveIntent("east"),
            MoveIntent("north"),
            AttackIntent("monster_mist_crawler"),
            AttackIntent("monster_mist_crawler"),
            TakeIntent("item_condensed_mist"),
            MoveIntent("south"),
            MoveIntent("east"),
            MoveIntent("east"),
            AttackIntent("monster_prism_sentinel"),
            AttackIntent("monster_prism_sentinel"),
            TakeIntent("item_beacon_core"),
            MoveIntent("east"),
            TalkIntent("character_beacon_echo"),
            ChooseDialogueIntent(1),
        )
        return SimulationRequest(
            format_version=1,
            seed=20260807,
            clock=1930,
            player_name="Public Arc Player",
            intents=intents,
            conditions=(
                SimulationCondition(
                    "quest_restore_beacon",
                    ConditionOutcome.WIN,
                    SimulationConditionKind.QUEST_COMPLETED,
                    True,
                ),
                SimulationCondition(
                    "player_alive",
                    ConditionOutcome.LOSS,
                    SimulationConditionKind.PLAYER_ALIVE,
                    False,
                ),
            ),
            checkpoint_after_steps=(0, 9, 17, 24, len(intents)),
        )

    def long_provenance(self, count: int = 1200) -> ProvenanceManifest:
        source_id = "source_long_arc"
        rights_id = "rights_long_arc"
        decision_id = "decision_long_arc"
        elements = tuple(
            ProjectElement(f"element_{index:04d}", "story_element") for index in range(count)
        )
        transformations = tuple(
            TransformationRecord(
                transformation_id=f"transform_{index:04d}",
                kind=TransformationKind.ADAPT,
                source_ids=(source_id,),
                decision_ids=(decision_id,),
                output_project_element_ids=(f"element_{index:04d}",),
                depends_on_transformation_ids=((f"transform_{index - 1:04d}",) if index else ()),
            )
            for index in range(count)
        )
        bindings = tuple(
            TraceBinding(
                binding_id=f"binding_{index:04d}",
                source_id=source_id,
                rights_assertion_id=rights_id,
                decision_id=decision_id,
                transformation_id=f"transform_{index:04d}",
                project_element_id=f"element_{index:04d}",
                package_element_id=f"package_{index:04d}",
            )
            for index in range(count)
        )
        return ProvenanceManifest(
            format_version=1,
            manifest_id="long_public_provenance",
            mode=AdaptationMode.SEALED,
            sources=(
                SourceReference(
                    source_id,
                    "synthetic_story",
                    SourceVisibility.PUBLIC_SAFE,
                    "Public synthetic long arc",
                ),
            ),
            rights_assertions=(
                RightsAssertion(
                    rights_id,
                    source_id,
                    RightsStatus.AUTHORIZED,
                    "public adaptation",
                    "fixture_owner",
                ),
            ),
            creator_decisions=(
                CreatorDecisionRecord(
                    decision_id,
                    CreatorDecisionKind.INCLUDE,
                    True,
                    "Include the public synthetic long arc.",
                    (source_id,),
                    (rights_id,),
                ),
            ),
            transformations=transformations,
            project_elements=elements,
            trace_bindings=bindings,
        )


class ProvenanceContractTests(V2_4Fixture):
    def test_schema_and_canonical_manifest_round_trip(self) -> None:
        schemas, registry = _schema_registry()
        validator = Draft202012Validator(
            schemas["https://github.com/lore2mud/lore2mud/schemas/provenance_manifest.schema.json"],
            registry=registry,
        )
        manifest = self.provenance()
        document = provenance_manifest_to_document(manifest)
        validator.validate(document)
        restored = load_provenance_manifest_document(document)
        self.assertEqual(
            canonical_json_bytes(provenance_manifest_to_document(restored)),
            canonical_json_bytes(provenance_manifest_to_document(manifest)),
        )

    def test_all_v2_4_schemas_accept_transport_and_identity_documents(self) -> None:
        schemas, registry = _schema_registry()
        request = self.request()
        result = AuthoringService().seal(request)
        self.assertTrue(result.ok)
        assert result.artifact is not None
        artifact_document = authoring_result_to_document(result)["artifact"]
        assert isinstance(artifact_document, dict)

        migration = AnchorMigration(
            "migration_schema_fixture",
            "anchor_schema_prior",
            ("anchor_schema_current",),
            "decision_public_arc",
        )
        anchor_request = {
            "previous_anchors": [
                story_anchor_to_document(
                    StoryAnchor(
                        "anchor_schema_prior",
                        AnchorKind.SCENE,
                        "element_choice",
                        "package_choice",
                    )
                )
            ],
            "current_anchors": [story_anchor_to_document(request.anchors[1])],
            "migrations": [anchor_migration_to_document(migration)],
        }
        documents = {
            "provenance_manifest.schema.json": provenance_manifest_to_document(request.provenance),
            "story_anchor.schema.json": story_anchor_to_document(request.anchors[0]),
            "anchor_migration.schema.json": anchor_migration_to_document(migration),
            "anchor_validation_request.schema.json": anchor_request,
            "anchor_migration_report.schema.json": artifact_document["anchor_migration_report"],
            "game_package_v2.schema.json": artifact_document["package"],
            "evidence_manifest.schema.json": artifact_document["evidence_manifest"],
            "seal_request.schema.json": seal_request_to_document(request),
            "seal_candidate.schema.json": artifact_document,
            "authoring_result.schema.json": authoring_result_to_document(result),
        }
        rejected = AuthoringService().validate_provenance_document({})
        documents["authoring_diagnostic.schema.json"] = diagnostic_to_document(
            rejected.diagnostics[0]
        )
        for name, document in documents.items():
            with self.subTest(schema=name):
                schema = schemas[f"https://github.com/lore2mud/lore2mud/schemas/{name}"]
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema, registry=registry).validate(document)

    def test_v2_4_schemas_reject_public_unsafe_text_and_recursive_data(self) -> None:
        schemas, registry = _schema_registry()
        request = self.request()
        sealed = AuthoringService().seal(request)
        self.assertTrue(sealed.ok)
        assert sealed.artifact is not None

        def validator(name: str) -> Draft202012Validator:
            schema = schemas[f"https://github.com/lore2mud/lore2mud/schemas/{name}"]
            Draft202012Validator.check_schema(schema)
            return Draft202012Validator(schema, registry=registry)

        for unsafe_text in (
            "foo/bar",
            "owner_manuscript.txt",
            ".env",
            "..",
            "Story/Scene",
            " fixture-extractor/v1 ",
            "private / novel / chapter.txt",
            "ssh:\tprivate",
            "ssh\u200b:private",
            "ssh\u180e:synthetic",
            "ssh\U000110bd:synthetic",
            "ssh\U000e0001:synthetic",
            "\x1cpublic",
            "public\x1c",
            "mailto : public@example.test",
            "http : synthetic.example",
            "file : synthetic.txt",
            "ssh\uff1aprivate",
            "http\uff1aprivate",
            "tel\uff1a+123",
            "foo\uff0fbar.txt",
            "foo\u2215bar.txt",
            "\uff53\uff53\uff48:private",
            f"{'a' * 32}-{'b' * 32}",
        ):
            manifest_document = provenance_manifest_to_document(request.provenance)
            manifest_document["sources"][0]["public_label"] = unsafe_text
            self.assertTrue(
                list(validator("provenance_manifest.schema.json").iter_errors(manifest_document))
            )

        request_document = seal_request_to_document(request)
        request_document["elements"][0]["data"] = {
            "unsafe/key": "ssh:private",
            "nested": {"encoded": "foo%2Fbar"},
        }
        self.assertTrue(list(validator("seal_request.schema.json").iter_errors(request_document)))
        for unsafe_key in (
            "python_module",
            "pythonModule",
            "module / path",
            "network-endpoint",
            "url",
            "__class__",
            "pythonmodule",
            "code",
            "eval",
            "exec",
            "filesystem",
            "webhook",
        ):
            request_document = seal_request_to_document(request)
            request_document["elements"][0]["data"] = {unsafe_key: "public value"}
            self.assertTrue(
                list(validator("seal_request.schema.json").iter_errors(request_document))
            )
        request_document["elements"][0]["data"] = {
            "label": "story / scene",
            "note": "title: value",
            "ratio": "50% complete",
        }
        validator("seal_request.schema.json").validate(request_document)

        private_id_documents = []
        request_document = seal_request_to_document(request)
        request_document["project"]["project_id"] = "private_novel_project"
        private_id_documents.append(request_document)
        request_document = seal_request_to_document(request)
        request_document["anchors"][0]["anchor_id"] = "anchor_private_chapter"
        private_id_documents.append(request_document)
        request_document = seal_request_to_document(request)
        request_document["presentation_metadata"] = [
            {"key": "private_source_path", "value": "public label"}
        ]
        private_id_documents.append(request_document)
        for request_document in private_id_documents:
            self.assertTrue(
                list(validator("seal_request.schema.json").iter_errors(request_document))
            )

        for private_id in ("source_chapter58", "anchor_privatechapter"):
            request_document = seal_request_to_document(request)
            request_document["anchors"][0]["anchor_id"] = private_id
            self.assertTrue(
                list(validator("seal_request.schema.json").iter_errors(request_document))
            )

        package_document = deepcopy(
            sealed.artifact.package and game_package_to_document(sealed.artifact.package)
        )
        package_document["elements"][0]["data"] = {"label": "tel:+123"}
        self.assertTrue(
            list(validator("game_package_v2.schema.json").iter_errors(package_document))
        )
        package_document = game_package_to_document(sealed.artifact.package)
        package_document["content_files"][0]["document"] = {"value": "foo/bar"}
        self.assertTrue(
            list(validator("game_package_v2.schema.json").iter_errors(package_document))
        )
        for field in ("distributable", "release_evidence"):
            package_document = game_package_to_document(sealed.artifact.package)
            package_document[field] = True
            self.assertTrue(
                list(validator("game_package_v2.schema.json").iter_errors(package_document))
            )
            with self.assertRaises(PackageValidationError):
                load_game_package_document(package_document)

        evidence_document = deepcopy(
            sealed.artifact.evidence_manifest
            and authoring_result_to_document(sealed)["artifact"]["evidence_manifest"]
        )
        evidence_document["entries"][0]["kind"] = "http:private"
        self.assertTrue(
            list(validator("evidence_manifest.schema.json").iter_errors(evidence_document))
        )
        evidence_document = deepcopy(
            authoring_result_to_document(sealed)["artifact"]["evidence_manifest"]
        )
        evidence_document["entries"][0]["evidence_id"] = "private_source_hash"
        self.assertTrue(
            list(validator("evidence_manifest.schema.json").iter_errors(evidence_document))
        )

        candidate_documents = (
            ("game_package_v2.schema.json", game_package_to_document(sealed.artifact.package)),
            (
                "evidence_manifest.schema.json",
                authoring_result_to_document(sealed)["artifact"]["evidence_manifest"],
            ),
            ("seal_candidate.schema.json", authoring_result_to_document(sealed)["artifact"]),
        )
        for schema_name, candidate_document in candidate_documents:
            malformed = deepcopy(candidate_document)
            malformed["candidate_id"] = 7
            self.assertTrue(list(validator(schema_name).iter_errors(malformed)))

        predecessor_document = game_package_to_document(sealed.artifact.package)
        initial_request = seal_request_to_document(request)
        initial_request["predecessor_package"] = predecessor_document
        self.assertTrue(list(validator("seal_request.schema.json").iter_errors(initial_request)))

        initial_migration = seal_request_to_document(request)
        initial_migration["anchor_migrations"] = [
            anchor_migration_to_document(
                AnchorMigration(
                    "migration_schema_initial",
                    "anchor_schema_prior",
                    ("anchor_schema_current",),
                    "decision_public_arc",
                )
            )
        ]
        self.assertTrue(list(validator("seal_request.schema.json").iter_errors(initial_migration)))

        incremental_request = seal_request_to_document(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=sealed.artifact.package,
            )
        )
        incremental_request["predecessor_package"] = None
        self.assertTrue(
            list(validator("seal_request.schema.json").iter_errors(incremental_request))
        )

        initial_package = game_package_to_document(sealed.artifact.package)
        initial_package["predecessor_candidate_id"] = sealed.artifact.package.candidate_id
        initial_package["predecessor_package_sha256"] = sealed.artifact.package.package_sha256
        initial_package["predecessor_anchors_sha256"] = "0" * 64
        self.assertTrue(list(validator("game_package_v2.schema.json").iter_errors(initial_package)))

        incremental_package = game_package_to_document(sealed.artifact.package)
        incremental_package["seal_mode"] = SealMode.INCREMENTAL.value
        self.assertTrue(
            list(validator("game_package_v2.schema.json").iter_errors(incremental_package))
        )

        initial_candidate = deepcopy(authoring_result_to_document(sealed)["artifact"])
        assert isinstance(initial_candidate, dict)
        initial_candidate["predecessor_package"] = predecessor_document
        self.assertTrue(list(validator("seal_candidate.schema.json").iter_errors(initial_candidate)))

        incremental_result = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=sealed.artifact.package,
            )
        )
        self.assertTrue(incremental_result.ok)
        incremental_candidate = authoring_result_to_document(incremental_result)["artifact"]
        assert isinstance(incremental_candidate, dict)
        incremental_candidate["predecessor_package"] = None
        self.assertTrue(
            list(validator("seal_candidate.schema.json").iter_errors(incremental_candidate))
        )

    def test_complete_trace_chain_rejects_missing_reference_and_duplicate_id(self) -> None:
        manifest = self.provenance()
        broken = replace(
            manifest,
            trace_bindings=(
                replace(manifest.trace_bindings[0], rights_assertion_id="missing_rights"),
                *manifest.trace_bindings[1:],
            ),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(broken))
        duplicate = replace(
            manifest,
            project_elements=(manifest.project_elements[0], manifest.project_elements[0]),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(duplicate))

    def test_transformation_cycle_and_invalid_rights_are_rejected(self) -> None:
        manifest = self.provenance()
        cycle = replace(
            manifest,
            transformations=(
                replace(
                    manifest.transformations[0],
                    depends_on_transformation_ids=("transform_resolution",),
                ),
                *manifest.transformations[1:],
            ),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(cycle))
        denied = replace(
            manifest,
            rights_assertions=(replace(manifest.rights_assertions[0], status=RightsStatus.DENIED),),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(denied))

    def test_transformation_source_and_decision_sets_must_be_trace_bound(self) -> None:
        manifest = self.provenance()
        extra_source = SourceReference(
            "source_extra_trace",
            "synthetic_story",
            SourceVisibility.PUBLIC_SAFE,
            "Extra trace source",
        )
        extra_rights = RightsAssertion(
            "rights_extra_trace",
            "source_extra_trace",
            RightsStatus.AUTHORIZED,
            "adaptation scope",
            "creator",
        )
        extra_decision = CreatorDecisionRecord(
            "decision_extra_trace",
            CreatorDecisionKind.INCLUDE,
            True,
            "Extra source is intentionally material.",
            ("source_extra_trace",),
            ("rights_extra_trace",),
        )
        invalid = replace(
            manifest,
            sources=(*manifest.sources, extra_source),
            rights_assertions=(*manifest.rights_assertions, extra_rights),
            creator_decisions=(*manifest.creator_decisions, extra_decision),
            transformations=(
                replace(
                    manifest.transformations[0],
                    source_ids=("source_public_arc", "source_extra_trace"),
                    decision_ids=("decision_public_arc", "decision_extra_trace"),
                ),
                *manifest.transformations[1:],
            ),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(invalid))

    def test_evidence_schema_requires_an_admitted_entry(self) -> None:
        schemas, registry = _schema_registry()
        request = self.request()
        result = AuthoringService().seal(request)
        self.assertTrue(result.ok)
        assert result.artifact is not None
        document = authoring_result_to_document(result)["artifact"]
        assert isinstance(document, dict)
        evidence = dict(document["evidence_manifest"])
        evidence["entries"] = []
        schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/evidence_manifest.schema.json"
        ]
        self.assertTrue(list(Draft202012Validator(schema, registry=registry).iter_errors(evidence)))

    def test_candidate_loader_binds_provenance_evidence_entry_to_manifest_digest(self) -> None:
        result = AuthoringService().seal(self.request())
        self.assertTrue(result.ok)
        assert result.artifact is not None
        document = deepcopy(authoring_result_to_document(result)["artifact"])
        evidence = document["evidence_manifest"]
        provenance_entry = next(
            item
            for item in evidence["entries"]
            if item["kind"] == "public_provenance_manifest_v1"
        )
        provenance_entry["artifact_sha256"] = "f" * 64
        evidence_semantic = {
            key: evidence[key]
            for key in (
                "format_version",
                "identity_scope",
                "candidate_input_sha256",
                "provenance_manifest_sha256",
                "entries",
            )
        }
        evidence_digest = sha256_bytes(canonical_json_bytes(evidence_semantic))
        evidence["manifest_sha256"] = evidence_digest
        evidence["candidate_id"] = f"evidence_{evidence_digest[:24]}"

        package_draft = replace(
            result.artifact.package,
            candidate_id="package_pending",
            evidence_manifest_sha256=evidence_digest,
            package_sha256="0" * 64,
        )
        package_digest = game_package_sha256(package_draft)
        package = replace(
            package_draft,
            candidate_id=f"package_{package_digest[:24]}",
            package_sha256=package_digest,
        )
        document["package"] = game_package_to_document(package)
        document["candidate_id"] = package.candidate_id
        document["seal_input_sha256"] = sha256_bytes(
            canonical_json_bytes(
                {
                    "package_sha256": package.package_sha256,
                    "evidence_manifest_sha256": evidence_digest,
                    "provenance_manifest_sha256": evidence["provenance_manifest_sha256"],
                    "anchor_migration_sha256": document["anchor_migration_sha256"],
                    "seal_mode": package.seal_mode.value,
                    "predecessor_package_sha256": package.predecessor_package_sha256,
                }
            )
        )
        with self.assertRaises(PackageValidationError):
            load_seal_candidate_document(document)

    def test_sealed_manifest_rejects_unapproved_unbound_decisions(self) -> None:
        manifest = self.provenance()
        extra_source = SourceReference(
            "source_extra_arc",
            "synthetic_story",
            SourceVisibility.PUBLIC_SAFE,
            "Extra public arc",
        )
        extra_rights = RightsAssertion(
            "rights_extra_arc",
            "source_extra_arc",
            RightsStatus.REVIEW_REQUIRED,
            "review scope",
            "review authority",
        )
        extra_decision = CreatorDecisionRecord(
            "decision_extra_arc",
            CreatorDecisionKind.INCLUDE,
            False,
            "Unapproved extra decision.",
            ("source_extra_arc",),
            ("rights_extra_arc",),
        )
        invalid = replace(
            manifest,
            sources=(*manifest.sources, extra_source),
            rights_assertions=(*manifest.rights_assertions, extra_rights),
            creator_decisions=(*manifest.creator_decisions, extra_decision),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(invalid))

    def test_private_path_hash_and_private_id_never_enter_public_manifest(self) -> None:
        manifest = replace(
            self.provenance(),
            sources=(
                replace(
                    self.provenance().sources[0],
                    source_id="private_source_identifier",
                    public_label="C:\\Users\\owner\\novel\\chapter.txt",
                ),
            ),
        )
        with self.assertRaises(ProvenanceValidationError) as caught:
            load_provenance_manifest_document(provenance_manifest_to_document(manifest))
        self.assertNotIn("chapter.txt", str(caught.exception))

    def test_prototype_can_remain_unbound_but_traced_requires_complete_chain(self) -> None:
        prototype = replace(
            self.provenance(),
            mode=AdaptationMode.PROTOTYPE,
            trace_bindings=(),
        )
        restored = load_provenance_manifest_document(provenance_manifest_to_document(prototype))
        self.assertEqual(restored.mode, AdaptationMode.PROTOTYPE)

        traced = replace(prototype, mode=AdaptationMode.TRACED)
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(traced))

    def test_seal_rejects_provenance_not_bound_to_game_project_trace(self) -> None:
        request = replace(
            self.request(),
            project=self.project(include_project_trace=False),
        )
        result = AuthoringService().seal(request)
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_provenance_invalid")

    def test_public_projection_anonymizes_authorized_private_records(self) -> None:
        private = replace(
            self.provenance(),
            sources=(
                replace(
                    self.provenance().sources[0],
                    visibility=SourceVisibility.AUTHORIZED_PRIVATE,
                    public_label="Owner-controlled material",
                ),
            ),
            rights_assertions=(
                replace(
                    self.provenance().rights_assertions[0],
                    scope="Owner-only adaptation scope",
                    authority="Owner-held authorization record",
                ),
            ),
            creator_decisions=(
                replace(
                    self.provenance().creator_decisions[0],
                    rationale="Private source-specific adaptation rationale.",
                ),
            ),
        )
        projection = public_provenance_manifest_to_document(private)
        payload = canonical_json_bytes(projection)
        for private_value in (
            b"source_public_arc",
            b"rights_public_arc",
            b"decision_public_arc",
            b"Owner-controlled",
            b"Owner-only",
            b"Owner-held",
            b"source-specific",
        ):
            self.assertNotIn(private_value, payload)
        self.assertEqual(
            projection["sources"][0]["public_label"],
            "Authorized private source",
        )

    def test_private_component_element_labels_are_anonymized_and_identity_stable(self) -> None:
        marker = "unpublishedtitle"
        base = self.private_alias_request()

        def variant(element_kind: str) -> SealRequest:
            provenance = replace(
                base.provenance,
                project_elements=tuple(
                    replace(element, element_kind=element_kind)
                    for element in base.provenance.project_elements
                ),
            )
            return replace(
                base,
                provenance=provenance,
                elements=tuple(
                    replace(element, element_kind=element_kind) for element in base.elements
                ),
            )

        first_request = variant(marker)
        second_request = variant("another_private_label")
        first_projection = public_provenance_manifest_to_document(first_request.provenance)
        second_projection = public_provenance_manifest_to_document(second_request.provenance)
        self.assertEqual(
            canonical_json_bytes(first_projection),
            canonical_json_bytes(second_projection),
        )
        self.assertNotIn(marker.encode("utf-8"), canonical_json_bytes(first_projection))
        self.assertTrue(
            all(
                item["element_kind"] == "authorized_adapted_element"
                for item in first_projection["project_elements"]
            )
        )

        first = AgentAuthoringSDK().seal(first_request)
        second = AgentAuthoringSDK().seal(second_request)
        self.assertTrue(first.ok and second.ok)
        assert first.artifact is not None and second.artifact is not None
        first_bytes = canonical_json_bytes(authoring_result_to_document(first))
        second_bytes = canonical_json_bytes(authoring_result_to_document(second))
        self.assertEqual(first_bytes, second_bytes)
        self.assertNotIn(marker.encode("utf-8"), first_bytes)
        self.assertTrue(
            all(
                item.element_kind == "authorized_adapted_element"
                for item in first.artifact.package.elements
            )
        )

    def test_private_projection_identity_ignores_opaque_id_spelling(self) -> None:
        base = self.provenance()

        def variant(source_id: str) -> ProvenanceManifest:
            return replace(
                base,
                sources=(
                    replace(
                        base.sources[0],
                        source_id=source_id,
                        visibility=SourceVisibility.AUTHORIZED_PRIVATE,
                    ),
                ),
                rights_assertions=(replace(base.rights_assertions[0], source_id=source_id),),
                creator_decisions=(replace(base.creator_decisions[0], source_ids=(source_id,)),),
                transformations=tuple(
                    replace(item, source_ids=(source_id,)) for item in base.transformations
                ),
                trace_bindings=tuple(
                    replace(item, source_id=source_id) for item in base.trace_bindings
                ),
            )

        self.assertEqual(
            canonical_json_bytes(
                public_provenance_manifest_to_document(variant("source_ref_0001"))
            ),
            canonical_json_bytes(
                public_provenance_manifest_to_document(variant("source_ref_9999"))
            ),
        )

    def test_private_projection_identity_ignores_multi_source_id_ordering(self) -> None:
        base = self.provenance()

        def variant(
            first_source: str,
            second_source: str,
            first_rights: str,
            second_rights: str,
            first_decision: str,
            second_decision: str,
        ) -> ProvenanceManifest:
            source_for_suffix = {
                "opening": first_source,
                "signal": first_source,
                "choice": second_source,
                "resolution": second_source,
            }
            rights_for_suffix = {
                "opening": first_rights,
                "signal": first_rights,
                "choice": second_rights,
                "resolution": second_rights,
            }
            decision_for_suffix = {
                "opening": first_decision,
                "signal": first_decision,
                "choice": second_decision,
                "resolution": second_decision,
            }
            return replace(
                base,
                sources=(
                    SourceReference(
                        first_source,
                        "private_story",
                        SourceVisibility.AUTHORIZED_PRIVATE,
                        "Owner-controlled material A",
                    ),
                    SourceReference(
                        second_source,
                        "private_story",
                        SourceVisibility.AUTHORIZED_PRIVATE,
                        "Owner-controlled material B",
                    ),
                ),
                rights_assertions=(
                    RightsAssertion(
                        first_rights,
                        first_source,
                        RightsStatus.AUTHORIZED,
                        "Owner-only scope A",
                        "Owner authority A",
                    ),
                    RightsAssertion(
                        second_rights,
                        second_source,
                        RightsStatus.AUTHORIZED,
                        "Owner-only scope B",
                        "Owner authority B",
                    ),
                ),
                creator_decisions=(
                    CreatorDecisionRecord(
                        first_decision,
                        CreatorDecisionKind.INCLUDE,
                        True,
                        "Private rationale A",
                        (first_source,),
                        (first_rights,),
                    ),
                    CreatorDecisionRecord(
                        second_decision,
                        CreatorDecisionKind.INCLUDE,
                        True,
                        "Private rationale B",
                        (second_source,),
                        (second_rights,),
                    ),
                ),
                transformations=tuple(
                    replace(
                        item,
                        source_ids=(source_for_suffix[item.transformation_id.removeprefix("transform_")],),
                        decision_ids=(
                            decision_for_suffix[
                                item.transformation_id.removeprefix("transform_")
                            ],
                        ),
                    )
                    for item in base.transformations
                ),
                trace_bindings=tuple(
                    replace(
                        item,
                        source_id=source_for_suffix[item.binding_id.removeprefix("binding_")],
                        rights_assertion_id=rights_for_suffix[
                            item.binding_id.removeprefix("binding_")
                        ],
                        decision_id=decision_for_suffix[
                            item.binding_id.removeprefix("binding_")
                        ],
                    )
                    for item in base.trace_bindings
                ),
            )

        first = variant(
            "source_ref_1000",
            "source_ref_9000",
            "rights_ref_1000",
            "rights_ref_9000",
            "decision_ref_1000",
            "decision_ref_9000",
        )
        renamed = variant(
            "source_ref_9900",
            "source_ref_0100",
            "rights_ref_9900",
            "rights_ref_0100",
            "decision_ref_9900",
            "decision_ref_0100",
        )
        self.assertEqual(
            canonical_json_bytes(public_provenance_manifest_to_document(first)),
            canonical_json_bytes(public_provenance_manifest_to_document(renamed)),
        )

    def test_private_projection_rejects_ambiguous_alias_roles_before_seal(self) -> None:
        base = self.provenance()
        private_sources = tuple(
            SourceReference(
                f"source_ref_{suffix}",
                "private_story",
                SourceVisibility.AUTHORIZED_PRIVATE,
                "Owner-controlled material",
            )
            for suffix in ("alpha", "beta")
        )
        private_rights = tuple(
            RightsAssertion(
                f"rights_ref_{suffix}",
                f"source_ref_{suffix}",
                RightsStatus.AUTHORIZED,
                "Owner-only scope",
                "Owner authority",
            )
            for suffix in ("alpha", "beta")
        )
        private_decisions = tuple(
            CreatorDecisionRecord(
                f"decision_ref_{suffix}",
                CreatorDecisionKind.INCLUDE,
                True,
                "Private rationale",
                (f"source_ref_{suffix}",),
                (f"rights_ref_{suffix}",),
            )
            for suffix in ("alpha", "beta")
        )
        ambiguous = replace(
            base,
            sources=(*base.sources, *private_sources),
            rights_assertions=(*base.rights_assertions, *private_rights),
            creator_decisions=(*base.creator_decisions, *private_decisions),
        )

        with self.assertRaises(ProvenanceValidationError):
            public_provenance_manifest_to_document(ambiguous)
        typed = AuthoringService().validate_provenance(ambiguous)
        document = AuthoringService().validate_provenance_document(
            provenance_manifest_to_document(ambiguous)
        )
        sealed = AuthoringService().seal(replace(self.request(), provenance=ambiguous))
        self.assertFalse(typed.ok)
        self.assertFalse(document.ok)
        self.assertFalse(sealed.ok)
        self.assertEqual(typed.diagnostics[0].code, "provenance_invalid")
        self.assertEqual(document.diagnostics[0].code, "provenance_invalid")
        self.assertEqual(sealed.diagnostics[0].code, "seal_provenance_invalid")

    def test_private_projection_refines_non_isomorphic_private_graphs(self) -> None:
        base = self.provenance()

        def variant(
            balanced_source: str,
            unbalanced_source: str,
            balanced_rights: tuple[str, str],
            unbalanced_rights: tuple[str, str],
            balanced_decisions: tuple[str, str],
            unbalanced_decisions: tuple[str, str],
        ) -> ProvenanceManifest:
            sources = (
                SourceReference(
                    balanced_source,
                    "private_story",
                    SourceVisibility.AUTHORIZED_PRIVATE,
                    "Owner-controlled material",
                ),
                SourceReference(
                    unbalanced_source,
                    "private_story",
                    SourceVisibility.AUTHORIZED_PRIVATE,
                    "Owner-controlled material",
                ),
            )
            rights = (
                *(
                    RightsAssertion(
                        identifier,
                        balanced_source,
                        RightsStatus.AUTHORIZED,
                        "Owner-only scope",
                        "Owner authority",
                    )
                    for identifier in balanced_rights
                ),
                *(
                    RightsAssertion(
                        identifier,
                        unbalanced_source,
                        RightsStatus.AUTHORIZED,
                        "Owner-only scope",
                        "Owner authority",
                    )
                    for identifier in unbalanced_rights
                ),
            )
            decisions = (
                CreatorDecisionRecord(
                    balanced_decisions[0],
                    CreatorDecisionKind.INCLUDE,
                    True,
                    "Private rationale",
                    (balanced_source,),
                    (balanced_rights[0],),
                ),
                CreatorDecisionRecord(
                    balanced_decisions[1],
                    CreatorDecisionKind.TRANSFORM,
                    True,
                    "Private rationale",
                    (balanced_source,),
                    (balanced_rights[1],),
                ),
                CreatorDecisionRecord(
                    unbalanced_decisions[0],
                    CreatorDecisionKind.INCLUDE,
                    True,
                    "Private rationale",
                    (unbalanced_source,),
                    (unbalanced_rights[0],),
                ),
                CreatorDecisionRecord(
                    unbalanced_decisions[1],
                    CreatorDecisionKind.TRANSFORM,
                    True,
                    "Private rationale",
                    (unbalanced_source,),
                    (unbalanced_rights[0],),
                ),
            )
            return replace(
                base,
                sources=(*base.sources, *sources),
                rights_assertions=(*base.rights_assertions, *rights),
                creator_decisions=(*base.creator_decisions, *decisions),
            )

        first = variant(
            "source_ref_9000",
            "source_ref_1000",
            ("rights_ref_9001", "rights_ref_9002"),
            ("rights_ref_1001", "rights_ref_1002"),
            ("decision_ref_9001", "decision_ref_9002"),
            ("decision_ref_1001", "decision_ref_1002"),
        )
        renamed = variant(
            "source_ref_0001",
            "source_ref_9999",
            ("rights_ref_0002", "rights_ref_0003"),
            ("rights_ref_9998", "rights_ref_9997"),
            ("decision_ref_0002", "decision_ref_0003"),
            ("decision_ref_9998", "decision_ref_9997"),
        )
        self.assertEqual(
            canonical_json_bytes(public_provenance_manifest_to_document(first)),
            canonical_json_bytes(public_provenance_manifest_to_document(renamed)),
        )

    def test_service_diagnostics_do_not_echo_private_input(self) -> None:
        document = provenance_manifest_to_document(self.provenance())
        document["sources"][0]["public_label"] = "C:\\Users\\owner\\novel\\chapter.txt"
        result = AuthoringService().validate_provenance_document(document)
        payload = canonical_json_bytes(authoring_result_to_document(result))
        self.assertEqual(result.status, AuthoringStatus.REJECTED)
        self.assertNotIn(b"Users", payload)
        self.assertNotIn(b"chapter.txt", payload)
        self.assertNotIn(b"private_source_identifier", payload)

    def test_long_transformation_chain_is_iterative_across_service_sdk_and_web(self) -> None:
        manifest = self.long_provenance()
        document = provenance_manifest_to_document(manifest)
        restored = load_provenance_manifest_document(document)
        self.assertEqual(len(restored.transformations), 1200)

        service_result = AuthoringService().validate_provenance(manifest)
        sdk_result = AgentAuthoringSDK().validate_provenance(manifest)
        web_result = WebAuthoringTransport().dispatch(
            {"operation": "validate_provenance", "manifest": document}
        )
        self.assertTrue(service_result.ok)
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(service_result)),
            canonical_json_bytes(authoring_result_to_document(sdk_result)),
        )
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(sdk_result)),
            canonical_json_bytes(web_result),
        )


class AnchorAndPackageTests(V2_4Fixture):
    def test_anchor_migration_is_explicit_and_unresolved_targets_reject(self) -> None:
        old = (
            StoryAnchor("anchor_old_scene", AnchorKind.SCENE, "element_opening", "package_opening"),
        )
        current = (
            StoryAnchor("anchor_new_scene", AnchorKind.SCENE, "element_choice", "package_choice"),
        )
        report = validate_anchor_migrations(
            old,
            current,
            (
                AnchorMigration(
                    "migration_old_scene",
                    "anchor_old_scene",
                    ("anchor_new_scene",),
                    "decision_public_arc",
                ),
            ),
        )
        self.assertEqual(report.resolutions[0].resolved_anchor_ids, ("anchor_new_scene",))
        with self.assertRaises(AnchorValidationError):
            validate_anchor_migrations(old, current, ())

        changed = (replace(old[0], project_element_id="element_signal"),)
        with self.assertRaises(AnchorValidationError):
            validate_anchor_migrations(old, changed, ())

    def test_long_anchor_chain_resolves_and_redundant_current_migration_rejects(self) -> None:
        previous = tuple(
            StoryAnchor(
                f"anchor_{index:04d}",
                AnchorKind.SCENE,
                "element_opening",
                "package_opening",
            )
            for index in range(1200)
        )
        current = (
            StoryAnchor(
                "anchor_current",
                AnchorKind.SCENE,
                "element_choice",
                "package_choice",
            ),
        )
        migrations = tuple(
            AnchorMigration(
                f"migration_{index:04d}",
                f"anchor_{index:04d}",
                (
                    (f"anchor_{index + 1:04d}",)
                    if index < len(previous) - 1
                    else ("anchor_current",)
                ),
                "decision_public_arc",
            )
            for index in range(len(previous))
        )
        report = validate_anchor_migrations(
            previous,
            current,
            migrations,
        )
        self.assertEqual(report.resolutions[0].resolved_anchor_ids, ("anchor_current",))
        service_result = AuthoringService().validate_anchor_migrations(
            previous,
            current,
            migrations,
        )
        self.assertTrue(service_result.ok)

        redundant_current = (previous[0], *current)
        redundant_migration = (
            AnchorMigration(
                "migration_redundant",
                "anchor_0000",
                ("anchor_current",),
                "decision_public_arc",
            ),
        )
        with self.assertRaises(AnchorValidationError):
            validate_anchor_migrations(
                previous,
                redundant_current,
                redundant_migration,
            )
        rejected = AuthoringService().validate_anchor_migrations(
            previous,
            redundant_current,
            redundant_migration,
        )
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.diagnostics[0].code, "anchor_migration_invalid")

    def test_external_package_loader_requires_valid_v1_content_and_elements(self) -> None:
        result = AuthoringService().seal(self.request())
        self.assertTrue(result.ok)
        assert result.artifact is not None
        package = result.artifact.package

        def rehashed(**changes: object):
            draft = replace(
                package,
                candidate_id="package_pending",
                package_sha256="0" * 64,
                **changes,
            )
            digest = game_package_sha256(draft)
            return replace(
                draft,
                candidate_id=game_package_candidate_id(draft),
                package_sha256=digest,
            )

        with self.assertRaises(PackageValidationError):
            load_game_package_document(game_package_to_document(rehashed(content_files=())))
        with self.assertRaises(PackageValidationError):
            load_game_package_document(game_package_to_document(rehashed(elements=())))

        invalid_rooms = canonical_json_bytes({})
        invalid_content_files = tuple(
            replace(
                item,
                canonical_json=invalid_rooms,
                sha256=sha256_bytes(invalid_rooms),
            )
            if item.name == "rooms.json"
            else item
            for item in package.content_files
        )
        with self.assertRaises(PackageValidationError):
            load_game_package_document(
                game_package_to_document(rehashed(content_files=invalid_content_files))
            )

    def test_loaders_reject_collection_tails_instead_of_truncating(self) -> None:
        request_document = seal_request_to_document(self.request())
        request_document["presentation_metadata"] = [
            {"key": "layout", "value": "wide"} for _ in range(4097)
        ]
        with self.assertRaises(PackageValidationError):
            load_seal_request_document(request_document)

        migration_document = seal_request_to_document(self.request())
        migration_document["anchor_migrations"] = [
            {
                "migration_id": f"migration_{index:04d}",
                "from_anchor_id": "anchor_scene_prior",
                "to_anchor_ids": ["anchor_scene_choice"],
                "decision_id": "decision_public_arc",
            }
            for index in range(4097)
        ]
        with self.assertRaises(PackageValidationError):
            load_seal_request_document(migration_document)

        result = AuthoringService().seal(self.request())
        self.assertTrue(result.ok)
        assert result.artifact is not None
        package = result.artifact.package
        draft = replace(
            package,
            candidate_id="package_pending",
            package_sha256="0" * 64,
            capability_requirement_ids=tuple(f"capability_{index:04d}" for index in range(4097)),
        )
        rehashed = replace(
            draft,
            candidate_id=game_package_candidate_id(draft),
            package_sha256=game_package_sha256(draft),
        )
        with self.assertRaises(PackageValidationError):
            load_game_package_document(game_package_to_document(rehashed))

    def test_package_identity_excludes_presentation_metadata_and_round_trips(self) -> None:
        request = self.request()
        first = AuthoringService().seal(request)
        metadata = (
            WorkspaceMetadataEntry("layout", "wide"),
            WorkspaceMetadataEntry("selection", "anchor_scene_choice"),
        )
        second = AuthoringService().seal(
            replace(
                request,
                presentation_metadata=metadata,
            )
        )
        reordered = AuthoringService().seal(
            replace(
                request,
                elements=tuple(reversed(request.elements)),
                anchors=tuple(reversed(request.anchors)),
                simulation_reports=tuple(reversed(request.simulation_reports)),
            )
        )
        self.assertTrue(first.ok and second.ok and reordered.ok)
        assert (
            first.artifact is not None
            and second.artifact is not None
            and reordered.artifact is not None
        )
        self.assertEqual(
            canonical_game_package_bytes(first.artifact.package),
            canonical_game_package_bytes(second.artifact.package),
        )
        self.assertEqual(
            game_package_sha256(first.artifact.package),
            game_package_sha256(second.artifact.package),
        )
        self.assertEqual(
            game_package_candidate_id(first.artifact.package),
            second.artifact.candidate_id,
        )
        self.assertEqual(first.artifact.candidate_id, reordered.artifact.candidate_id)
        self.assertEqual(
            first.artifact.evidence_manifest.manifest_sha256,
            second.artifact.evidence_manifest.manifest_sha256,
        )
        self.assertEqual(
            first.artifact.evidence_manifest.manifest_sha256,
            reordered.artifact.evidence_manifest.manifest_sha256,
        )
        direct = replace(
            first.artifact.package,
            capability_requirement_ids=("capability_alpha", "capability_zeta"),
        )
        direct_reordered = replace(
            direct,
            content_files=tuple(reversed(direct.content_files)),
            capability_requirement_ids=tuple(reversed(direct.capability_requirement_ids)),
            elements=tuple(reversed(direct.elements)),
            anchors=tuple(reversed(direct.anchors)),
        )
        self.assertEqual(
            canonical_game_package_bytes(direct),
            canonical_game_package_bytes(direct_reordered),
        )
        self.assertEqual(game_package_sha256(direct), game_package_sha256(direct_reordered))
        self.assertEqual(
            game_package_candidate_id(direct), game_package_candidate_id(direct_reordered)
        )
        direct_evidence = first.artifact.evidence_manifest
        direct_evidence_reordered = replace(
            direct_evidence,
            entries=tuple(reversed(direct_evidence.entries)),
        )
        self.assertEqual(
            canonical_evidence_manifest_bytes(direct_evidence),
            canonical_evidence_manifest_bytes(direct_evidence_reordered),
        )
        self.assertEqual(
            second.artifact.evidence_manifest.presentation_metadata,
            metadata,
        )
        loaded = load_seal_candidate_document(authoring_result_to_document(first)["artifact"])
        self.assertEqual(loaded, first.artifact)

    def test_sealed_package_element_data_is_deeply_immutable(self) -> None:
        request = self.request()
        source_data = {
            "arc_step": "opening",
            "nested": [{"player_safe": True}],
        }
        request = replace(
            request,
            elements=(
                replace(request.elements[0], data=source_data),
                *request.elements[1:],
            ),
        )
        source_data["arc_step"] = "mutated_after_construction"

        result = AuthoringService().seal(request)
        self.assertTrue(result.ok)
        assert result.artifact is not None
        package = result.artifact.package
        before = canonical_game_package_bytes(package)
        before_sha = package.package_sha256
        element_data = next(
            item.data for item in package.elements if item.package_element_id == "package_opening"
        )

        with self.assertRaises(TypeError):
            element_data["arc_step"] = "mutated_in_place"  # type: ignore[index]
        nested = element_data["nested"]  # type: ignore[index]
        with self.assertRaises(TypeError):
            nested[0]["player_safe"] = False  # type: ignore[index]

        self.assertEqual(canonical_game_package_bytes(package), before)
        self.assertEqual(game_package_sha256(package), before_sha)
        self.assertEqual(package.package_sha256, before_sha)

    def test_semantic_change_creates_a_new_candidate_and_reseal_is_rejected(self) -> None:
        request = self.request()
        first = AuthoringService().seal(request)
        changed = replace(
            request,
            elements=(
                replace(
                    request.elements[0], data={"arc_step": "opening_changed", "player_safe": True}
                ),
                *request.elements[1:],
            ),
        )
        second = AuthoringService().seal(changed)
        self.assertTrue(first.ok and second.ok)
        assert first.artifact is not None and second.artifact is not None
        self.assertNotEqual(first.artifact.candidate_id, second.artifact.candidate_id)
        with self.assertRaises(PackageValidationError):
            reseal_game_package(first.artifact.package)

    def test_seal_binds_explicit_anchor_migration_into_candidate_identity(self) -> None:
        request = self.request()
        previous = (
            StoryAnchor(
                "anchor_scene_prior",
                AnchorKind.SCENE,
                "element_choice",
                "package_choice",
            ),
        )
        migration = (
            AnchorMigration(
                "migration_scene_prior",
                "anchor_scene_prior",
                ("anchor_scene_choice",),
                "decision_public_arc",
            ),
        )
        result = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=self.sealed_package(replace(request, anchors=previous)),
                anchor_migrations=migration,
            )
        )
        self.assertTrue(result.ok)
        assert result.artifact is not None
        candidate = result.artifact
        self.assertEqual(
            candidate.package.anchor_migration_sha256,
            candidate.anchor_migration_sha256,
        )
        self.assertEqual(
            candidate.anchor_migration_report.migrations,
            migration,
        )
        document = authoring_result_to_document(result)["artifact"]
        assert isinstance(document, dict)
        document["seal_input_sha256"] = "0" * 64
        with self.assertRaises(PackageValidationError):
            load_seal_candidate_document(document)

    def test_incremental_seal_requires_and_binds_complete_predecessor_lineage(self) -> None:
        request = self.request()
        predecessor = self.sealed_package(request)
        incremental = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=predecessor,
            )
        )
        self.assertTrue(incremental.ok)
        assert incremental.artifact is not None
        candidate = incremental.artifact
        self.assertEqual(
            candidate.anchor_migration_report.required_anchor_ids,
            tuple(item.anchor_id for item in predecessor.anchors),
        )
        self.assertEqual(candidate.predecessor_package, predecessor)
        self.assertEqual(candidate.package.predecessor_candidate_id, predecessor.candidate_id)
        self.assertEqual(candidate.package.predecessor_package_sha256, predecessor.package_sha256)
        self.assertNotEqual(candidate.candidate_id, predecessor.candidate_id)

        removed_resume = replace(
            request,
            seal_mode=SealMode.INCREMENTAL,
            predecessor_package=predecessor,
            anchors=tuple(item for item in request.anchors if item.kind is not AnchorKind.RESUME),
        )
        unresolved = AuthoringService().seal(removed_resume)
        self.assertFalse(unresolved.ok)
        self.assertEqual(unresolved.diagnostics[0].code, "seal_anchor_invalid")

        missing_predecessor = AuthoringService().seal(
            replace(request, seal_mode=SealMode.INCREMENTAL)
        )
        self.assertFalse(missing_predecessor.ok)
        self.assertEqual(missing_predecessor.diagnostics[0].code, "seal_lineage_invalid")

        unexpected_predecessor = AuthoringService().seal(
            replace(request, predecessor_package=predecessor)
        )
        self.assertFalse(unexpected_predecessor.ok)
        self.assertEqual(unexpected_predecessor.diagnostics[0].code, "seal_lineage_invalid")

        partial_predecessor = replace(predecessor, anchors=predecessor.anchors[:-1])
        rejected_partial = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=partial_predecessor,
            )
        )
        self.assertFalse(rejected_partial.ok)
        self.assertEqual(rejected_partial.diagnostics[0].code, "seal_lineage_invalid")

    def test_incremental_identity_changes_with_predecessor_identity(self) -> None:
        request = self.request()
        first_predecessor = self.sealed_package(request)
        changed_request = replace(
            request,
            elements=(
                replace(
                    request.elements[0],
                    data={"arc_step": "opening_predecessor_variant", "player_safe": True},
                ),
                *request.elements[1:],
            ),
        )
        second_predecessor = self.sealed_package(changed_request)
        first = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=first_predecessor,
            )
        )
        second = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=second_predecessor,
            )
        )
        self.assertTrue(first.ok and second.ok)
        assert first.artifact is not None and second.artifact is not None
        self.assertNotEqual(first.artifact.candidate_id, second.artifact.candidate_id)

    def test_incremental_seal_rejects_rehashed_predecessor_anchor_pair_tampering(
        self,
    ) -> None:
        request = self.request()
        predecessor = self.sealed_package(request)
        forged_anchor = replace(
            predecessor.anchors[0],
            package_element_id=predecessor.elements[1].package_element_id,
        )
        forged_draft = replace(
            predecessor,
            anchors=(forged_anchor, *predecessor.anchors[1:]),
            candidate_id="package_pending",
            package_sha256="0" * 64,
        )
        forged_digest = game_package_sha256(forged_draft)
        forged = replace(
            forged_draft,
            candidate_id=f"package_{forged_digest[:24]}",
            package_sha256=forged_digest,
        )

        with self.assertRaises(PackageValidationError):
            load_game_package_document(game_package_to_document(forged))
        result = AuthoringService().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=forged,
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_lineage_invalid")

    def test_private_provenance_migration_round_trips_with_public_seal_identity(self) -> None:
        request = self.request()
        private_manifest = replace(
            request.provenance,
            sources=(
                replace(
                    request.provenance.sources[0],
                    visibility=SourceVisibility.AUTHORIZED_PRIVATE,
                    public_label="Owner-controlled material",
                ),
            ),
            creator_decisions=(
                replace(
                    request.provenance.creator_decisions[0],
                    rationale="Owner-controlled adaptation decision.",
                ),
            ),
        )
        previous = (
            StoryAnchor(
                "anchor_scene_prior",
                AnchorKind.SCENE,
                "element_choice",
                "package_choice",
            ),
        )
        migration = (
            AnchorMigration(
                "migration_scene_prior",
                "anchor_scene_prior",
                ("anchor_scene_choice",),
                "decision_public_arc",
            ),
        )
        result = AuthoringService().seal(
            replace(
                request,
                provenance=private_manifest,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=self.sealed_package(replace(request, anchors=previous)),
                anchor_migrations=migration,
            )
        )
        self.assertTrue(result.ok)
        assert result.artifact is not None
        document = authoring_result_to_document(result)["artifact"]
        loaded = load_seal_candidate_document(document)
        self.assertEqual(loaded, result.artifact)

    def test_seal_rejects_unknown_anchor_migration_decision_and_pair_mismatch(self) -> None:
        request = self.request()
        invalid_decision = replace(
            request,
            seal_mode=SealMode.INCREMENTAL,
            predecessor_package=self.sealed_package(
                replace(
                    request,
                    anchors=(
                        StoryAnchor(
                            "anchor_scene_prior",
                            AnchorKind.SCENE,
                            "element_choice",
                            "package_choice",
                        ),
                    ),
                )
            ),
            anchor_migrations=(
                AnchorMigration(
                    "migration_scene_prior",
                    "anchor_scene_prior",
                    ("anchor_scene_choice",),
                    "missing_decision",
                ),
            ),
        )
        rejected = AuthoringService().seal(invalid_decision)
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.diagnostics[0].code, "seal_anchor_invalid")

        mismatched = replace(
            request,
            anchors=(
                StoryAnchor(
                    "anchor_scene_choice",
                    AnchorKind.SCENE,
                    "element_opening",
                    "package_choice",
                ),
            ),
        )
        rejected = AuthoringService().seal(mismatched)
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.diagnostics[0].code, "seal_anchor_invalid")

    def test_executable_package_data_is_rejected_before_seal(self) -> None:
        request = self.request()
        malicious = replace(
            request,
            elements=(
                replace(
                    request.elements[0],
                    data={"python_module": "lore2mud.private", "player_safe": True},
                ),
                *request.elements[1:],
            ),
        )
        result = AuthoringService().seal(malicious)
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_private_or_executable_data")

    def test_package_data_rejects_forbidden_key_variants(self) -> None:
        for key in (
            "script_url",
            "python_code",
            "module_name",
            "plugin_name",
            "native_code",
            "shell_command",
            "process_id",
            "network_config",
            "host_name",
            "http_url",
            "endpoint_url",
            "command_line",
            "pythonmodule",
            "code",
            "eval",
            "exec",
            "filesystem",
            "webhook",
        ):
            with self.subTest(key=key):
                request = self.request()
                malicious = replace(
                    request,
                    elements=(
                        replace(request.elements[0], data={key: "blocked"}),
                        *request.elements[1:],
                    ),
                )
                result = AuthoringService().seal(malicious)
                self.assertFalse(result.ok)
                self.assertEqual(
                    result.diagnostics[0].code,
                    "seal_private_or_executable_data",
                )

    def test_package_data_rejects_private_or_uri_keys(self) -> None:
        for key in (
            "../novel/chapter.txt",
            r"C:\Users\owner\novel\chapter.txt",
            "https://private.example/source",
            "//private.example/source",
            "data:text/plain,private",
            "secret/chapter",
        ):
            with self.subTest(key=key):
                request = self.request()
                malicious = replace(
                    request,
                    elements=(
                        replace(request.elements[0], data={key: "safe"}),
                        *request.elements[1:],
                    ),
                )
                result = AuthoringService().seal(malicious)
                self.assertFalse(result.ok)
                self.assertEqual(
                    result.diagnostics[0].code,
                    "seal_private_or_executable_data",
                )

    def test_typed_evidence_report_must_be_replay_verified(self) -> None:
        request = self.request()
        invalid = replace(
            request,
            simulation_reports=(replace(request.simulation_reports[0], replay_verified=False),),
        )
        result = AgentAuthoringSDK().seal(invalid)
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_evidence_invalid")

    def test_public_text_rejects_absolute_relative_and_uri_paths(self) -> None:
        for value in (
            "/",
            "/tmp",
            "/x",
            "//private.example/x",
            r"\private\chapter.txt",
            "../novel/chapter.txt",
            r"C:private\chapter.txt",
            "private / novel / chapter.txt",
            "C: / Users / owner / novel / chapter.txt",
            "foo/bar",
            "foo/bar.txt",
            "foo/bar.txt#secret",
            "foo/bar.txt%20",
            "owner_manuscript.txt",
            "public_fixture.json",
            "archive.7z",
            ".env",
            ".",
            "..",
            "~",
            "foo%2Fbar",
            "foo%2fbar",
            "foo%5Cbar",
            "foo%5cbar",
            "foo%252Fbar",
            "alice/diary",
            "data:text/plain,private",
            "mailto:private@example.test",
            "mailto : public@example.test",
            "custom://private.example/source",
            "javascript:alert(1)",
            "urn:private:source",
            "tel:+123",
            "ssh:private",
            "ssh:\tprivate",
            "ssh\t:private",
            "http : synthetic.example",
            "file : synthetic.txt",
            "ssh\uff1aprivate",
            "http\uff1aprivate",
            "tel\uff1a+123",
            "foo\uff0fbar.txt",
            "foo\u2215bar.txt",
            "\uff53\uff53\uff48:private",
            "ssh\x7f:private",
            "ssh\u200b:private",
            "ssh\u180e:synthetic",
            "ssh\U000110bd:synthetic",
            "ssh\U000e0001:synthetic",
            "http:private",
            f"{'g' * 33}:payload",
            "novel/chapter",
            "note=/tmp/private_source.txt",
            f"{'a' * 32}\u200b{'b' * 32}",
            f"{'a' * 32}-{'b' * 32}",
            "sha256: " + " ".join(["01234567"] * 8),
            " / ",
            "story\t/\tscene",
            "story\f/\fscene",
            "story\v/\vscene",
            "story\u00a0/\u00a0scene",
            "Story/Scene",
            "fixture-extractor/V1",
            " story/scene ",
            "public\tlabel",
            "\x00",
            "\f",
            "\v",
        ):
            with self.subTest(value=value):
                manifest = self.provenance()
                invalid = replace(
                    manifest,
                    sources=(replace(manifest.sources[0], public_label=value),),
                )
                with self.assertRaises(ProvenanceValidationError):
                    load_provenance_manifest_document(provenance_manifest_to_document(invalid))

                request = self.request()
                malicious = replace(
                    request,
                    elements=(
                        replace(request.elements[0], data={"label": value}),
                        *request.elements[1:],
                    ),
                )
                result = AuthoringService().seal(malicious)
                self.assertFalse(result.ok)
                self.assertEqual(
                    result.diagnostics[0].code,
                    "seal_private_or_executable_data",
                )

    def test_public_text_allows_display_slash_labels(self) -> None:
        for value in (
            "fixture-extractor/v1",
            "fixture-extractor / v1",
            "story/scene",
            "story / scene",
            "hand/body",
            "hand / body",
        ):
            with self.subTest(value=value):
                manifest = self.provenance()
                updated = replace(
                    manifest,
                    sources=(replace(manifest.sources[0], public_label=value),),
                )
                self.assertEqual(
                    load_provenance_manifest_document(provenance_manifest_to_document(updated))
                    .sources[0]
                    .public_label,
                    value,
                )
                request = self.request()
                result = AuthoringService().seal(
                    replace(
                        request,
                        elements=(
                            replace(request.elements[0], data={"label": value}),
                            *request.elements[1:],
                        ),
                    )
                )
                self.assertTrue(result.ok)

    def test_bounded_json_rejects_duplicate_object_members(self) -> None:
        with self.assertRaises(BoundedJsonError) as context:
            parse_bounded_json(
                b'{"value": 1, "value": 2}',
                DEFAULT_JSON_READ_LIMITS,
                reject_duplicate_members=True,
            )
        self.assertEqual(context.exception.code, JsonReadErrorCode.INVALID_JSON)

    def test_seal_rejects_private_aliases_in_public_ids_and_metadata(self) -> None:
        request = self.request()
        cases = (
            replace(request, project=self.project("private_novel_project")),
            replace(request, project=self.project("source_chapter58")),
            replace(
                request,
                anchors=(
                    replace(request.anchors[0], anchor_id="anchor_private_chapter"),
                    *request.anchors[1:],
                ),
            ),
            replace(
                request,
                anchors=(
                    replace(request.anchors[0], anchor_id="anchor_privatechapter"),
                    *request.anchors[1:],
                ),
            ),
            replace(
                request,
                presentation_metadata=(
                    WorkspaceMetadataEntry("private_source_path", "public label"),
                ),
            ),
        )
        for value in cases:
            with self.subTest(value=value):
                result = AuthoringService().seal(value)
                self.assertFalse(result.ok)
                self.assertIn(
                    result.diagnostics[0].code,
                    {"seal_private_or_executable_data", "seal_rejected"},
                )

    def test_seal_request_rejects_legacy_caller_supplied_evidence_hashes(self) -> None:
        document = seal_request_to_document(self.request())
        document.pop("simulation_reports")
        private_hash = "0123456789abcdef" * 4
        document["evidence_entries"] = [
            {
                "evidence_id": "private_source_hash",
                "kind": "simulation",
                "artifact_sha256": private_hash,
                "admitted": True,
            }
        ]
        result = AuthoringService().seal_document(document)
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_input_invalid")
        rendered = canonical_json_bytes(authoring_result_to_document(result))
        self.assertNotIn(private_hash.encode("ascii"), rendered)
        self.assertNotIn(b"private_source_hash", rendered)

    def test_sealed_manifest_rejects_unbound_denied_source(self) -> None:
        manifest = self.provenance()
        denied_source = SourceReference(
            "source_denied_arc",
            "synthetic_story",
            SourceVisibility.PUBLIC_SAFE,
            "Denied public arc",
        )
        denied_rights = RightsAssertion(
            "rights_denied_arc",
            "source_denied_arc",
            RightsStatus.DENIED,
            "denied scope",
            "denied authority",
        )
        denied_decision = CreatorDecisionRecord(
            "decision_denied_arc",
            CreatorDecisionKind.INCLUDE,
            True,
            "Denied source must not enter a sealed chain.",
            ("source_denied_arc",),
            ("rights_denied_arc",),
        )
        invalid = replace(
            manifest,
            sources=(*manifest.sources, denied_source),
            rights_assertions=(*manifest.rights_assertions, denied_rights),
            creator_decisions=(*manifest.creator_decisions, denied_decision),
        )
        with self.assertRaises(ProvenanceValidationError):
            load_provenance_manifest_document(provenance_manifest_to_document(invalid))

    def test_validation_output_anonymizes_authorized_private_manifest(self) -> None:
        manifest = self.provenance()
        private = replace(
            manifest,
            sources=(
                replace(
                    manifest.sources[0],
                    visibility=SourceVisibility.AUTHORIZED_PRIVATE,
                    public_label="Owner-controlled source label",
                ),
            ),
            creator_decisions=(
                replace(
                    manifest.creator_decisions[0],
                    rationale="Owner-controlled adaptation rationale",
                ),
            ),
        )
        result = AuthoringService().validate_provenance(private)
        self.assertTrue(result.ok)
        document = authoring_result_to_document(result)
        encoded = canonical_json_bytes(document)
        self.assertNotIn(b"Owner-controlled source label", encoded)
        self.assertNotIn(b"Owner-controlled adaptation rationale", encoded)
        self.assertNotIn(b"source_public_arc", encoded)
        self.assertIn(b"source_ref_", encoded)

    def test_seal_rejects_private_path_in_v1_content_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "content"
            shutil.copytree(CONTENT, root)
            items_path = root / "items.json"
            items = json.loads(items_path.read_text(encoding="utf-8"))
            items[0]["adaptation_notes"] = "/tmp/private_source.txt"
            items_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            project = create_game_project(
                project_id="private_path_project",
                blueprint=load_blueprint(BLUEPRINT),
                content_root=root,
                public_inputs=(
                    PublicInputDescriptor(
                        "public_arc_brief",
                        "application/json",
                        "Public synthetic story arc",
                    ),
                ),
            )
        request = replace(self.request(), project=project)
        result = AuthoringService().seal(request)
        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics[0].code, "seal_private_or_executable_data")

    def test_public_safe_30_to_60_minute_arc_produces_traceable_sealed_candidate(self) -> None:
        sdk = AgentAuthoringSDK()
        project = self.project()
        simulation = sdk.simulate(project, self.story_arc_simulation_request())
        self.assertTrue(simulation.ok)
        assert type(simulation.artifact) is SimulationReport
        report = simulation.artifact
        self.assertEqual(len(report.turns), 31)
        self.assertEqual(report.outcome, SimulationOutcome.WIN)
        self.assertTrue(report.replay_verified)
        self.assertEqual(
            report.fingerprint,
            "8daafa0216dcb6591d9819f4c8b4fc24bce787dfe94dae5730424c6f316ca05e",
        )
        self.assertEqual(
            tuple(item.after_step for item in report.checkpoints),
            (0, 9, 17, 24, 31),
        )
        self.assertTrue(all(item.equivalent for item in report.checkpoints))

        replay = sdk.replay(project, report)
        self.assertTrue(replay.ok)
        self.assertEqual(replay.artifact, report)

        request = replace(
            self.request(),
            project=project,
            simulation_reports=(report,),
        )
        first = sdk.seal(request)
        second = sdk.seal(request)
        self.assertTrue(first.ok and second.ok)
        assert first.artifact is not None and second.artifact is not None
        self.assertEqual(
            canonical_game_package_bytes(first.artifact.package),
            canonical_game_package_bytes(second.artifact.package),
        )
        self.assertEqual(
            canonical_evidence_manifest_bytes(first.artifact.evidence_manifest),
            canonical_evidence_manifest_bytes(second.artifact.evidence_manifest),
        )
        self.assertEqual(first.artifact.candidate_id, second.artifact.candidate_id)
        self.assertIn(
            report.fingerprint,
            {item.artifact_sha256 for item in first.artifact.evidence_manifest.entries},
        )
        self.assertTrue(first.artifact.package.sealed)
        self.assertFalse(first.artifact.package.distributable)
        self.assertFalse(first.artifact.package.release_evidence)
        self.assertEqual(
            {item.project_element_id for item in first.artifact.package.elements},
            {item.element_id for item in self.provenance().project_elements},
        )
        self.assertEqual(
            first.artifact.package.evidence_manifest_sha256,
            first.artifact.evidence_manifest.manifest_sha256,
        )


class TransportParityTests(V2_4Fixture):
    def test_sdk_web_and_structured_cli_share_seal_bytes_and_diagnostics(self) -> None:
        request = self.request()
        sdk_result = AgentAuthoringSDK().seal(request)
        request_document = seal_request_to_document(request)
        web_result = WebAuthoringTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        in_app_web_result = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(sdk_result)),
            canonical_json_bytes(web_result),
        )
        self.assertEqual(web_result, in_app_web_result)

        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            request_path.write_bytes(canonical_json_bytes(request_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={**dict(PYTHONPATH=str(ROOT / "src")), **{"PYTHONIOENCODING": "utf-8"}},
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        cli_document = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(
            canonical_json_bytes(cli_document),
            canonical_json_bytes(authoring_result_to_document(sdk_result)),
        )

    def test_sdk_web_and_structured_cli_share_incremental_seal_bytes(self) -> None:
        request = self.request()
        incremental = replace(
            request,
            seal_mode=SealMode.INCREMENTAL,
            predecessor_package=self.sealed_package(request),
        )
        typed = AgentAuthoringSDK().seal(incremental)
        self.assertTrue(typed.ok)
        request_document = seal_request_to_document(incremental)
        document_sdk = AgentAuthoringSDK().seal_document(request_document)
        web = WebAuthoringTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        expected = canonical_json_bytes(authoring_result_to_document(typed))
        self.assertEqual(canonical_json_bytes(authoring_result_to_document(document_sdk)), expected)
        self.assertEqual(canonical_json_bytes(web), expected)
        self.assertEqual(in_app_web, web)

        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "incremental_seal_request.json"
            request_path.write_bytes(canonical_json_bytes(request_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={**dict(PYTHONPATH=str(ROOT / "src")), **{"PYTHONIOENCODING": "utf-8"}},
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        cli = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(canonical_json_bytes(cli), expected)

    def test_private_source_connected_ids_are_aliased_across_all_seal_transports(
        self,
    ) -> None:
        marker = b"unpublishedtitle"
        request = self.private_alias_request()
        typed = AgentAuthoringSDK().seal(request)
        self.assertTrue(typed.ok)
        assert typed.artifact is not None
        artifact = typed.artifact
        expected = canonical_json_bytes(authoring_result_to_document(typed))
        self.assertNotIn(marker, expected)
        self.assertTrue(
            all(
                item.package_element_id.startswith("package_ref_")
                and item.project_element_id.startswith("project_element_ref_")
                for item in artifact.package.elements
            )
        )
        self.assertTrue(
            all(
                item.project_element_id.startswith("project_element_ref_")
                and item.package_element_id.startswith("package_ref_")
                for item in artifact.package.anchors
            )
        )
        assert artifact.provenance_manifest is not None
        self.assertTrue(
            all(
                item.transformation_id.startswith("transformation_ref_")
                for item in artifact.provenance_manifest.transformations
            )
        )
        self.assertTrue(
            all(
                item.element_id.startswith("project_element_ref_")
                for item in artifact.provenance_manifest.project_elements
            )
        )
        self.assertTrue(
            all(
                item.binding_id.startswith("binding_ref_")
                and item.package_element_id.startswith("package_ref_")
                for item in artifact.provenance_manifest.trace_bindings
            )
        )

        incremental = AgentAuthoringSDK().seal(
            replace(
                request,
                seal_mode=SealMode.INCREMENTAL,
                predecessor_package=artifact.package,
            )
        )
        self.assertTrue(incremental.ok)
        assert incremental.artifact is not None
        self.assertEqual(incremental.artifact.package.anchors, artifact.package.anchors)
        self.assertNotIn(
            marker,
            canonical_json_bytes(authoring_result_to_document(incremental)),
        )

        request_document = seal_request_to_document(request)
        document_sdk = AgentAuthoringSDK().seal_document(request_document)
        web = WebAuthoringTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        self.assertTrue(document_sdk.ok)
        self.assertEqual(canonical_json_bytes(authoring_result_to_document(document_sdk)), expected)
        self.assertEqual(canonical_json_bytes(web), expected)
        self.assertEqual(in_app_web, web)
        self.assertNotIn(marker, canonical_json_bytes(web))

        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "private_alias_seal_request.json"
            request_path.write_bytes(canonical_json_bytes(request_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={
                    **dict(PYTHONPATH=str(ROOT / "src")),
                    **{"PYTHONIOENCODING": "utf-8"},
                },
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        cli = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(canonical_json_bytes(cli), expected)
        self.assertNotIn(marker, canonical_json_bytes(cli))

    def test_sdk_web_and_cli_share_private_text_rejection(self) -> None:
        private_value = "foo/bar.txt#secret"
        request = self.request()
        typed_request = replace(
            request,
            elements=(
                replace(request.elements[0], data={"label": private_value}),
                *request.elements[1:],
            ),
        )
        typed_sdk = AgentAuthoringSDK().seal(typed_request)
        request_document = seal_request_to_document(request)
        request_document["elements"][0]["data"] = {"label": private_value}

        sdk = AgentAuthoringSDK().seal_document(request_document)
        web = WebAuthoringTransport().dispatch({"operation": "seal", "request": request_document})
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        self.assertFalse(sdk.ok)
        self.assertEqual(sdk.diagnostics[0].code, "seal_private_or_executable_data")
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(typed_sdk)),
            canonical_json_bytes(authoring_result_to_document(sdk)),
        )
        self.assertEqual(web, in_app_web)
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(sdk)),
            canonical_json_bytes(web),
        )
        self.assertNotIn(private_value.encode("utf-8"), canonical_json_bytes(web))

        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            request_path.write_bytes(canonical_json_bytes(request_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={
                    **dict(PYTHONPATH=str(ROOT / "src")),
                    **{"PYTHONIOENCODING": "utf-8"},
                },
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        cli_document = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(
            canonical_json_bytes(cli_document),
            canonical_json_bytes(authoring_result_to_document(sdk)),
        )

    def test_provenance_sdk_web_and_cli_share_private_text_rejection(self) -> None:
        private_value = "alice/diary"
        manifest_document = provenance_manifest_to_document(self.provenance())
        manifest_document["sources"][0]["public_label"] = private_value

        sdk = AgentAuthoringSDK().validate_provenance_document(manifest_document)
        web = WebAuthoringTransport().dispatch(
            {"operation": "validate_provenance", "manifest": manifest_document}
        )
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "validate_provenance", "manifest": manifest_document}
        )
        self.assertFalse(sdk.ok)
        self.assertEqual(sdk.diagnostics[0].code, "provenance_private_data")
        self.assertEqual(web, in_app_web)
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(sdk)),
            canonical_json_bytes(web),
        )
        self.assertNotIn(private_value.encode("utf-8"), canonical_json_bytes(web))

        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "provenance_manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(manifest_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "validate-provenance",
                    "--manifest",
                    str(manifest_path),
                ],
                cwd=ROOT,
                env={
                    **dict(PYTHONPATH=str(ROOT / "src")),
                    **{"PYTHONIOENCODING": "utf-8"},
                },
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        cli_document = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(
            canonical_json_bytes(cli_document),
            canonical_json_bytes(authoring_result_to_document(sdk)),
        )

    def test_sdk_document_cli_and_web_reject_public_boundary_bypasses(self) -> None:
        request = self.request()
        cases = (
            (
                "format_character_u180e",
                {"label": "ssh\u180e:format_u180e_marker"},
                "format_u180e_marker",
            ),
            (
                "format_character_astral",
                {"label": "ssh\U000110bd:format_astral_marker"},
                "format_astral_marker",
            ),
            (
                "spaced_mailto_scheme",
                {"label": "mailto : marker@example.test"},
                "marker@example.test",
            ),
            (
                "spaced_http_scheme",
                {"label": "http : marker.example"},
                "marker.example",
            ),
            (
                "spaced_file_scheme",
                {"label": "file : marker.txt"},
                "marker.txt",
            ),
            (
                "fullwidth_colon_scheme",
                {"label": "ssh\uff1aformat_fullwidth_colon_marker"},
                "format_fullwidth_colon_marker",
            ),
            (
                "fullwidth_slash_path",
                {"label": "foo\uff0fblocked_fullwidth_path.txt"},
                "blocked_fullwidth_path.txt",
            ),
            (
                "division_slash_path",
                {"label": "foo\u2215blocked_division_path.txt"},
                "blocked_division_path.txt",
            ),
            (
                "fullwidth_scheme_letters",
                {"label": "\uff53\uff53\uff48:blocked_fullwidth_scheme"},
                "blocked_fullwidth_scheme",
            ),
            (
                "concatenated_python_module",
                {"pythonmodule": "blocked_key_marker"},
                "blocked_key_marker",
            ),
            ("code_field", {"code": "blocked_key_marker"}, "blocked_key_marker"),
            ("eval_field", {"eval": "blocked_key_marker"}, "blocked_key_marker"),
            ("exec_field", {"exec": "blocked_key_marker"}, "blocked_key_marker"),
            (
                "filesystem_field",
                {"filesystem": "blocked_key_marker"},
                "blocked_key_marker",
            ),
            (
                "webhook_field",
                {"webhook": "blocked_key_marker"},
                "blocked_key_marker",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            for name, data, blocked_fragment in cases:
                with self.subTest(case=name):
                    typed_request = replace(
                        request,
                        elements=(
                            replace(request.elements[0], data=data),
                            *request.elements[1:],
                        ),
                    )
                    typed = AgentAuthoringSDK().seal(typed_request)
                    document = seal_request_to_document(request)
                    document["elements"][0]["data"] = data
                    document_sdk = AgentAuthoringSDK().seal_document(document)
                    web = WebAuthoringTransport().dispatch(
                        {"operation": "seal", "request": document}
                    )
                    in_app_web = AuthoringWebTransport().dispatch(
                        {"operation": "seal", "request": document}
                    )
                    request_path.write_bytes(canonical_json_bytes(document))
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "lore2mud",
                            "author",
                            "seal",
                            "--request",
                            str(request_path),
                        ],
                        cwd=ROOT,
                        env={
                            **dict(PYTHONPATH=str(ROOT / "src")),
                            **{"PYTHONIOENCODING": "utf-8"},
                        },
                        capture_output=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    cli = json.loads(completed.stdout.decode("utf-8"))
                    expected = canonical_json_bytes(authoring_result_to_document(typed))
                    self.assertFalse(typed.ok)
                    self.assertEqual(
                        typed.diagnostics[0].code,
                        "seal_private_or_executable_data",
                    )
                    self.assertEqual(
                        canonical_json_bytes(authoring_result_to_document(document_sdk)),
                        expected,
                    )
                    self.assertEqual(canonical_json_bytes(web), expected)
                    self.assertEqual(canonical_json_bytes(in_app_web), expected)
                    self.assertEqual(canonical_json_bytes(cli), expected)
                    self.assertNotIn(blocked_fragment.encode("utf-8"), expected)

    def test_typed_document_cli_and_web_share_seal_rejection_categories(self) -> None:
        request = self.request()
        provenance = request.provenance
        predecessor = self.sealed_package(request)
        forged_anchor = replace(
            predecessor.anchors[0],
            package_element_id=predecessor.elements[1].package_element_id,
        )
        forged_draft = replace(
            predecessor,
            anchors=(forged_anchor, *predecessor.anchors[1:]),
            candidate_id="package_pending",
            package_sha256="0" * 64,
        )
        forged_digest = game_package_sha256(forged_draft)
        forged_predecessor = replace(
            forged_draft,
            candidate_id=f"package_{forged_digest[:24]}",
            package_sha256=forged_digest,
        )
        cases = (
            (
                "private_text",
                replace(
                    request,
                    provenance=replace(
                        provenance,
                        sources=(replace(provenance.sources[0], public_label="foo/bar.txt"),),
                    ),
                ),
                "seal_private_or_executable_data",
            ),
            (
                "denied_rights",
                replace(
                    request,
                    provenance=replace(
                        provenance,
                        rights_assertions=(
                            replace(
                                provenance.rights_assertions[0],
                                status=RightsStatus.DENIED,
                            ),
                        ),
                    ),
                ),
                "seal_provenance_invalid",
            ),
            (
                "duplicate_element",
                replace(
                    request,
                    elements=(request.elements[0], request.elements[0], *request.elements[1:]),
                ),
                "seal_rejected",
            ),
            (
                "unverified_report",
                replace(
                    request,
                    simulation_reports=(
                        replace(request.simulation_reports[0], replay_verified=False),
                    ),
                ),
                "seal_evidence_invalid",
            ),
            (
                "forged_predecessor",
                replace(
                    request,
                    seal_mode=SealMode.INCREMENTAL,
                    predecessor_package=forged_predecessor,
                ),
                "seal_lineage_invalid",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            for name, typed_request, expected_code in cases:
                with self.subTest(case=name):
                    document = seal_request_to_document(typed_request)
                    typed = AgentAuthoringSDK().seal(typed_request)
                    sdk = AgentAuthoringSDK().seal_document(document)
                    web = WebAuthoringTransport().dispatch(
                        {"operation": "seal", "request": document}
                    )
                    in_app_web = AuthoringWebTransport().dispatch(
                        {"operation": "seal", "request": document}
                    )
                    request_path.write_bytes(canonical_json_bytes(document))
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "lore2mud",
                            "author",
                            "seal",
                            "--request",
                            str(request_path),
                        ],
                        cwd=ROOT,
                        env={
                            **dict(PYTHONPATH=str(ROOT / "src")),
                            **{"PYTHONIOENCODING": "utf-8"},
                        },
                        capture_output=True,
                        check=False,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    cli = json.loads(completed.stdout.decode("utf-8"))
                    expected = canonical_json_bytes(authoring_result_to_document(typed))
                    self.assertEqual(typed.diagnostics[0].code, expected_code)
                    self.assertEqual(
                        canonical_json_bytes(authoring_result_to_document(sdk)), expected
                    )
                    self.assertEqual(canonical_json_bytes(web), expected)
                    self.assertEqual(canonical_json_bytes(in_app_web), expected)
                    self.assertEqual(canonical_json_bytes(cli), expected)

    def test_mixed_invalid_simulation_reports_share_evidence_diagnostic(self) -> None:
        request = self.request()
        typed_request = replace(
            request,
            simulation_reports=(object(), request.simulation_reports[0]),  # type: ignore[arg-type]
        )
        document = seal_request_to_document(request)
        document["simulation_reports"].insert(0, {"invalid": True})

        typed = AgentAuthoringSDK().seal(typed_request)
        sdk = AgentAuthoringSDK().seal_document(document)
        web = WebAuthoringTransport().dispatch({"operation": "seal", "request": document})
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": document}
        )
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            request_path.write_bytes(canonical_json_bytes(document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={
                    **dict(PYTHONPATH=str(ROOT / "src")),
                    **{"PYTHONIOENCODING": "utf-8"},
                },
                capture_output=True,
                check=False,
            )
        cli = json.loads(completed.stdout.decode("utf-8"))
        expected = canonical_json_bytes(authoring_result_to_document(typed))
        self.assertFalse(typed.ok)
        self.assertEqual(typed.diagnostics[0].code, "seal_evidence_invalid")
        self.assertEqual(canonical_json_bytes(authoring_result_to_document(sdk)), expected)
        self.assertEqual(canonical_json_bytes(web), expected)
        self.assertEqual(canonical_json_bytes(in_app_web), expected)
        self.assertEqual(canonical_json_bytes(cli), expected)

    def test_sdk_and_web_share_bounded_rejection_diagnostic(self) -> None:
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        sdk = AgentAuthoringSDK().seal_document(cyclic)
        web = WebAuthoringTransport().dispatch({"operation": "seal", "request": cyclic})
        self.assertEqual(sdk.diagnostics[0].code, "authoring_input_too_complex")
        self.assertEqual(web["diagnostics"][0]["code"], sdk.diagnostics[0].code)

    def test_sdk_web_and_cli_reject_oversized_seal_request_without_truncation(self) -> None:
        request_document = seal_request_to_document(self.request())
        request_document["presentation_metadata"] = [
            {"key": "layout", "value": "wide"} for _ in range(4097)
        ]
        sdk = AgentAuthoringSDK().seal_document(request_document)
        web = WebAuthoringTransport().dispatch({"operation": "seal", "request": request_document})
        in_app_web = AuthoringWebTransport().dispatch(
            {"operation": "seal", "request": request_document}
        )
        self.assertFalse(sdk.ok)
        self.assertEqual(sdk.diagnostics[0].code, "seal_input_invalid")
        self.assertEqual(web, in_app_web)
        self.assertEqual(
            canonical_json_bytes(authoring_result_to_document(sdk)),
            canonical_json_bytes(web),
        )

        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "seal_request.json"
            request_path.write_bytes(canonical_json_bytes(request_document))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lore2mud",
                    "author",
                    "seal",
                    "--request",
                    str(request_path),
                ],
                cwd=ROOT,
                env={
                    **dict(PYTHONPATH=str(ROOT / "src")),
                    **{"PYTHONIOENCODING": "utf-8"},
                },
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        cli_document = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(
            canonical_json_bytes(cli_document),
            canonical_json_bytes(authoring_result_to_document(sdk)),
        )


if __name__ == "__main__":
    unittest.main()
