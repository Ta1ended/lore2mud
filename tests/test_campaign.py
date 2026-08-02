from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from pipeline.campaign import (
    ApplyKnowledgeCompletion,
    CampaignBuildError,
    CampaignValidationError,
    InteractActorCompletion,
    campaign_spec_to_document,
    compile_campaign_spec,
    main,
    narrative_model_sha256,
    registry_campaign_plan_to_document,
    validate_campaign_spec_document,
    validate_registry_campaign_plan_document,
    write_campaign_spec,
)
from pipeline.narrative_model import (
    narrative_model_to_document,
    validate_narrative_model_document,
)


REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "campaign"
KINDS = ("magic_event", "urban_investigation")


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _path(kind: str, name: str) -> Path:
    return FIXTURES / kind / name


def _model_document(kind: str = "magic_event") -> dict:
    return _read_json(_path(kind, "narrative_model.json"))


def _plan_document(kind: str = "magic_event") -> dict:
    return _read_json(_path(kind, "valid_plan.json"))


def _expected_document(kind: str = "magic_event") -> dict:
    return _read_json(_path(kind, "expected_spec.json"))


def _model(kind: str = "magic_event"):
    return validate_narrative_model_document(_model_document(kind))


def _plan(kind: str = "magic_event"):
    return validate_registry_campaign_plan_document(_plan_document(kind))


def _spec(kind: str = "magic_event"):
    return compile_campaign_spec(_model(kind), _plan(kind))


def _item(document: dict, collection: str, id_field: str, item_id: str) -> dict:
    return next(
        value for value in document[collection] if value[id_field] == item_id
    )


class PlanValidationTests(unittest.TestCase):
    def test_both_original_plans_are_frozen_and_canonical(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                plan = _plan(kind)
                self.assertEqual(
                    registry_campaign_plan_to_document(plan),
                    registry_campaign_plan_to_document(
                        validate_registry_campaign_plan_document(
                            registry_campaign_plan_to_document(plan)
                        )
                    ),
                )
                self.assertEqual(
                    [actor.kind for actor in plan.actors].count("player"), 1
                )
                with self.assertRaises(FrozenInstanceError):
                    plan.campaign_id = "changed"  # type: ignore[misc]

    def test_root_versions_and_nullable_refs_have_strict_json_types(self) -> None:
        with self.assertRaises(CampaignValidationError):
            validate_registry_campaign_plan_document([])
        for field_path, value in (
            (("format_version",), True),
            (("format_version",), 1.0),
            (("format_version",), 2),
            (("source_narrative_model", "format_version"), True),
            (("source_narrative_model", "format_version"), 1.0),
            (("source_narrative_model", "narrative_model_sha256"), True),
            (
                ("source_narrative_model", "narrative_model_sha256"),
                "A" * 64,
            ),
            (("actors", 0, "source_entity_ref"), False),
            (("actors", 0, "starting_location_ref"), 0),
            (("scenes", 0, "location_ref"), False),
        ):
            with self.subTest(field_path=field_path, value=value):
                document = _plan_document()
                target: object = document
                for part in field_path[:-1]:
                    target = target[part]  # type: ignore[index]
                target[field_path[-1]] = value  # type: ignore[index]
                with self.assertRaises(CampaignValidationError):
                    validate_registry_campaign_plan_document(document)

    def test_unknown_fields_bad_ids_and_enums_are_rejected(self) -> None:
        cases: list[tuple[tuple[object, ...], object]] = [
            ((), {"extra": True}),
            (("campaign_id",), "Campaign-ID"),
            (("actors", 0, "kind"), "boss"),
            (("scenes", 0, "kind"), "cutscene"),
            (("knowledge_beats", 0, "state"), "corrected"),
        ]
        for field_path, value in cases:
            with self.subTest(field_path=field_path):
                document = _plan_document()
                if not field_path:
                    document.update(value)  # type: ignore[arg-type]
                else:
                    target: object = document
                    for part in field_path[:-1]:
                        target = target[part]  # type: ignore[index]
                    target[field_path[-1]] = value  # type: ignore[index]
                with self.assertRaises(CampaignValidationError):
                    validate_registry_campaign_plan_document(document)

    def test_scope_must_equal_real_bindings_and_reject_bad_omissions(self) -> None:
        document = _plan_document()
        document["scope"]["entity_uses"].pop()
        with self.assertRaisesRegex(CampaignValidationError, "campaign bindings"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        document["scope"]["entity_omissions"] = [
            {
                "entity_ref": document["scope"]["entity_uses"][0],
                "reason": "Also omitted.",
            }
        ]
        with self.assertRaisesRegex(CampaignValidationError, "uses and omits"):
            validate_registry_campaign_plan_document(document)

        for reason in ("", "   ", False):
            with self.subTest(reason=reason):
                document = _plan_document()
                document["scope"]["entity_omissions"] = [
                    {"entity_ref": "entity_unused", "reason": reason}
                ]
                with self.assertRaises(CampaignValidationError):
                    validate_registry_campaign_plan_document(document)

        document = _plan_document()
        omission = {"entity_ref": "entity_unused", "reason": "Outside the cut."}
        document["scope"]["entity_omissions"] = [omission, copy.deepcopy(omission)]
        with self.assertRaisesRegex(CampaignValidationError, "duplicated"):
            validate_registry_campaign_plan_document(document)

    def test_location_routes_and_start_reachability_are_strict(self) -> None:
        document = _plan_document()
        document["start_location_ref"] = "location_missing"
        with self.assertRaisesRegex(CampaignValidationError, "unknown location"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        base = _item(document, "locations", "location_id", "location_spire_base")
        base["exits"] = [base["exits"][0]]
        with self.assertRaisesRegex(CampaignValidationError, "reachable"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        base = _item(document, "locations", "location_id", "location_spire_base")
        duplicate = copy.deepcopy(base["exits"][0])
        duplicate["direction"] = duplicate["direction"].upper()
        duplicate["name"] = "Alternate stairs"
        base["exits"].append(duplicate)
        with self.assertRaisesRegex(CampaignValidationError, "route label"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        document["locations"][0]["exits"][0]["target_location_ref"] = (
            "location_missing"
        )
        with self.assertRaisesRegex(CampaignValidationError, "unknown target"):
            validate_registry_campaign_plan_document(document)

    def test_player_start_must_equal_campaign_root_in_plan_spec_and_compile(
        self,
    ) -> None:
        for document, validator in (
            (_plan_document(), validate_registry_campaign_plan_document),
            (_expected_document(), validate_campaign_spec_document),
        ):
            with self.subTest(validator=validator.__name__):
                crown = _item(
                    document, "locations", "location_id", "location_spire_crown"
                )
                crown["exits"] = []
                player = _item(document, "actors", "actor_id", "actor_mender")
                player["starting_location_ref"] = "location_spire_crown"
                with self.assertRaisesRegex(
                    CampaignValidationError, "starting_location_ref must equal"
                ):
                    validator(document)

        plan = _plan()
        mutated_locations = tuple(
            replace(location, exits=())
            if location.location_id == "location_spire_crown"
            else location
            for location in plan.locations
        )
        mutated_actors = tuple(
            replace(actor, starting_location_ref="location_spire_crown")
            if actor.actor_id == "actor_mender"
            else actor
            for actor in plan.actors
        )
        with self.assertRaisesRegex(
            CampaignBuildError, "starting_location_ref must equal"
        ):
            compile_campaign_spec(
                _model(),
                replace(
                    plan,
                    locations=mutated_locations,
                    actors=mutated_actors,
                ),
            )

    def test_physical_scene_dependencies_require_directed_travel(self) -> None:
        document = _plan_document()
        market = _item(
            document, "locations", "location_id", "location_market_steps"
        )
        market["exits"].append(
            {
                "direction": "crownward",
                "name": "Public crown lift",
                "target_location_ref": "location_spire_crown",
            }
        )
        base = _item(document, "locations", "location_id", "location_spire_base")
        base["exits"] = []
        parley = _item(document, "scenes", "scene_id", "scene_parley")
        parley["location_ref"] = None
        with self.assertRaisesRegex(
            CampaignValidationError, "not reachable from predecessor scene"
        ):
            validate_registry_campaign_plan_document(document)

    def test_exactly_one_player_and_internal_refs_are_required(self) -> None:
        for mutation in ("zero_players", "two_players", "bad_actor", "bad_location"):
            with self.subTest(mutation=mutation):
                document = _plan_document()
                if mutation == "zero_players":
                    _item(document, "actors", "actor_id", "actor_mender")["kind"] = (
                        "character"
                    )
                elif mutation == "two_players":
                    _item(document, "actors", "actor_id", "actor_warden")["kind"] = (
                        "player"
                    )
                elif mutation == "bad_actor":
                    document["scenes"][0]["participating_actor_refs"] = [
                        "actor_missing"
                    ]
                else:
                    document["actors"][0]["starting_location_ref"] = (
                        "location_missing"
                    )
                with self.assertRaises(CampaignValidationError):
                    validate_registry_campaign_plan_document(document)

    def test_scene_and_objective_graphs_are_acyclic_and_closed(self) -> None:
        document = _plan_document()
        _item(document, "scenes", "scene_id", "scene_arrival")[
            "predecessor_scene_refs"
        ] = ["scene_retuning"]
        with self.assertRaisesRegex(CampaignValidationError, "DAG"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        document["objectives"][0]["predecessor_objective_refs"] = [
            "objective_retune_spire"
        ]
        with self.assertRaisesRegex(CampaignValidationError, "DAG"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document()
        document["objectives"][0]["scene_refs"] = ["scene_parley"]
        with self.assertRaisesRegex(CampaignValidationError, "not bound"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document("urban_investigation")
        report = _item(
            document, "objectives", "objective_id", "objective_file_report"
        )
        report["mutually_exclusive_objective_refs"] = []
        with self.assertRaisesRegex(CampaignValidationError, "symmetric"):
            validate_registry_campaign_plan_document(document)

    def test_objective_dependencies_cannot_require_exclusive_paths(self) -> None:
        document = _plan_document("urban_investigation")
        report = _item(
            document, "objectives", "objective_id", "objective_file_report"
        )
        report["predecessor_objective_refs"].append("objective_shadow_courier")
        with self.assertRaisesRegex(
            CampaignValidationError, "depends on mutually exclusive"
        ):
            validate_registry_campaign_plan_document(document)

        document = _plan_document("urban_investigation")
        document["objectives"].append(
            {
                "objective_id": "objective_close_case",
                "title": "Close the Case",
                "description": "Attempt to require both exclusive decision paths.",
                "phase_ref": "phase_decision",
                "scene_refs": ["scene_report"],
                "predecessor_objective_refs": [
                    "objective_file_report",
                    "objective_shadow_courier",
                ],
                "mutually_exclusive_objective_refs": [],
                "source_proposition_refs": ["prop_cart_remained_locked"],
                "completion": {
                    "kind": "reach_location",
                    "location_ref": "location_records_office",
                },
                "adaptation_notes": "Exercise impossible predecessor ancestry rejection.",
            }
        )
        with self.assertRaisesRegex(
            CampaignValidationError, "requires mutually exclusive predecessor ancestry"
        ):
            validate_registry_campaign_plan_document(document)

    def test_completion_is_a_strict_tagged_union(self) -> None:
        for completion in (
            {"kind": "complete_scene"},
            {"kind": "complete_scene", "scene_ref": "scene_retuning", "extra": 1},
            {"kind": "unknown", "scene_ref": "scene_retuning"},
            {"kind": True, "scene_ref": "scene_retuning"},
            {"kind": "reach_location", "location_ref": "location_missing"},
            {"kind": "apply_knowledge", "knowledge_ref": "knowledge_missing"},
        ):
            with self.subTest(completion=completion):
                document = _plan_document()
                document["objectives"][1]["completion"] = completion
                with self.assertRaises(CampaignValidationError):
                    validate_registry_campaign_plan_document(document)

    def test_completion_targets_are_owned_by_same_phase_objective_scenes(
        self,
    ) -> None:
        cases = (
            (
                "later_phase_knowledge",
                "magic_event",
                "objective_hear_echo",
                {
                    "kind": "apply_knowledge",
                    "knowledge_ref": "knowledge_retuning_possible",
                },
                "scene_refs",
            ),
            (
                "earlier_phase_knowledge",
                "magic_event",
                "objective_hear_echo",
                {
                    "kind": "apply_knowledge",
                    "knowledge_ref": "knowledge_spire_unstable",
                },
                "objective phase",
            ),
            (
                "unrelated_branch_knowledge",
                "urban_investigation",
                "objective_file_report",
                {
                    "kind": "apply_knowledge",
                    "knowledge_ref": "knowledge_courier_route",
                },
                "scene_refs",
            ),
            (
                "unrelated_location",
                "magic_event",
                "objective_retune_spire",
                {
                    "kind": "reach_location",
                    "location_ref": "location_market_steps",
                },
                "scene_refs",
            ),
            (
                "unrelated_actor",
                "magic_event",
                "objective_retune_spire",
                {"kind": "interact_actor", "actor_ref": "actor_warden"},
                "scene_refs",
            ),
            (
                "earlier_phase_scene",
                "magic_event",
                "objective_hear_echo",
                {"kind": "complete_scene", "scene_ref": "scene_arrival"},
                "objective phase",
            ),
        )
        for name, kind, objective_id, completion, expected in cases:
            with self.subTest(name=name):
                document = _plan_document(kind)
                objective = _item(
                    document, "objectives", "objective_id", objective_id
                )
                objective["completion"] = completion
                with self.assertRaisesRegex(CampaignValidationError, expected):
                    validate_registry_campaign_plan_document(document)

    def test_apply_knowledge_ownership_is_shared_by_plan_spec_and_compile(
        self,
    ) -> None:
        for document, validator in (
            (_plan_document(), validate_registry_campaign_plan_document),
            (_expected_document(), validate_campaign_spec_document),
        ):
            with self.subTest(validator=validator.__name__):
                objective = _item(
                    document,
                    "objectives",
                    "objective_id",
                    "objective_hear_echo",
                )
                objective["completion"] = {
                    "kind": "apply_knowledge",
                    "knowledge_ref": "knowledge_retuning_possible",
                }
                with self.assertRaisesRegex(CampaignValidationError, "scene_refs"):
                    validator(document)

        plan = _plan()
        mutated_objectives = tuple(
            replace(
                objective,
                completion=ApplyKnowledgeCompletion(
                    kind="apply_knowledge",
                    knowledge_ref="knowledge_retuning_possible",
                ),
            )
            if objective.objective_id == "objective_hear_echo"
            else objective
            for objective in plan.objectives
        )
        with self.assertRaisesRegex(CampaignBuildError, "scene_refs"):
            compile_campaign_spec(
                _model(), replace(plan, objectives=mutated_objectives)
            )

    def test_completion_target_cannot_alias_other_phase_or_branch_scenes(
        self,
    ) -> None:
        cases = (
            (
                "location_also_in_earlier_scene",
                "magic_event",
                "objective_hear_echo",
                {
                    "kind": "reach_location",
                    "location_ref": "location_spire_base",
                },
                None,
                "scene_arrival",
            ),
            (
                "actor_also_in_later_scene",
                "magic_event",
                "objective_hear_echo",
                {"kind": "interact_actor", "actor_ref": "actor_echo"},
                None,
                "scene_retuning",
            ),
            (
                "knowledge_owned_by_exclusive_branch",
                "urban_investigation",
                "objective_file_report",
                {
                    "kind": "apply_knowledge",
                    "knowledge_ref": "knowledge_courier_route",
                },
                "scene_tail",
                "mutually exclusive objective",
            ),
        )
        for name, kind, objective_id, completion, added_scene, expected in cases:
            with self.subTest(name=name):
                for document, validator in (
                    (_plan_document(kind), validate_registry_campaign_plan_document),
                    (_expected_document(kind), validate_campaign_spec_document),
                ):
                    objective = _item(
                        document, "objectives", "objective_id", objective_id
                    )
                    if added_scene is not None:
                        objective["scene_refs"].append(added_scene)
                    objective["completion"] = completion
                    with self.assertRaisesRegex(CampaignValidationError, expected):
                        validator(document)

    def test_compile_rejects_actor_completion_that_aliases_a_later_scene(
        self,
    ) -> None:
        plan = _plan()
        mutated_objectives = tuple(
            replace(
                objective,
                completion=InteractActorCompletion(
                    kind="interact_actor",
                    actor_ref="actor_echo",
                ),
            )
            if objective.objective_id == "objective_hear_echo"
            else objective
            for objective in plan.objectives
        )
        with self.assertRaisesRegex(CampaignBuildError, "scene_retuning"):
            compile_campaign_spec(
                _model(), replace(plan, objectives=mutated_objectives)
            )

    def test_exclusive_branches_may_share_a_noncompletion_setup_scene(self) -> None:
        document = _plan_document("urban_investigation")
        for objective_id in (
            "objective_file_report",
            "objective_shadow_courier",
        ):
            objective = _item(
                document, "objectives", "objective_id", objective_id
            )
            objective["scene_refs"].append("scene_records")

        validate_registry_campaign_plan_document(document)

    def test_correction_requires_retraction_confirmation_and_reachability(self) -> None:
        document = _plan_document("urban_investigation")
        document["knowledge_corrections"][0]["corrects_knowledge_ref"] = (
            "knowledge_missing"
        )
        with self.assertRaisesRegex(CampaignValidationError, "unknown knowledge beat"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document("urban_investigation")
        document["knowledge_beats"] = [
            value
            for value in document["knowledge_beats"]
            if value["knowledge_id"] != "knowledge_cart_retracted"
        ]
        with self.assertRaisesRegex(CampaignValidationError, "retracted projection"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document("urban_investigation")
        document["knowledge_corrections"][0]["later_proposition_ref"] = (
            "prop_courier_used_west_ramp"
        )
        with self.assertRaisesRegex(CampaignValidationError, "confirmed projection"):
            validate_registry_campaign_plan_document(document)

        document = _plan_document("urban_investigation")
        document["knowledge_corrections"][0]["scene_ref"] = "scene_rumor"
        with self.assertRaisesRegex(CampaignValidationError, "must occur after"):
            validate_registry_campaign_plan_document(document)

    def test_semantically_unordered_input_collections_are_canonical(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                canonical = registry_campaign_plan_to_document(_plan(kind))
                shuffled = copy.deepcopy(canonical)
                for key in (
                    "locations",
                    "actors",
                    "scenes",
                    "objectives",
                    "knowledge_beats",
                    "knowledge_corrections",
                ):
                    shuffled[key].reverse()
                for key in (
                    "entity_uses",
                    "entity_omissions",
                    "perspective_uses",
                    "perspective_omissions",
                    "proposition_uses",
                    "proposition_omissions",
                    "beat_uses",
                    "beat_omissions",
                ):
                    shuffled["scope"][key].reverse()
                for location in shuffled["locations"]:
                    location["source_entity_refs"].reverse()
                    location["source_proposition_refs"].reverse()
                    location["exits"].reverse()
                for scene in shuffled["scenes"]:
                    scene["participating_actor_refs"].reverse()
                    scene["narrative_beat_refs"].reverse()
                    scene["predecessor_scene_refs"].reverse()
                    scene["source_proposition_refs"].reverse()
                for objective in shuffled["objectives"]:
                    objective["scene_refs"].reverse()
                    objective["predecessor_objective_refs"].reverse()
                    objective["mutually_exclusive_objective_refs"].reverse()
                    objective["source_proposition_refs"].reverse()
                self.assertEqual(
                    registry_campaign_plan_to_document(
                        validate_registry_campaign_plan_document(shuffled)
                    ),
                    canonical,
                )


class CompilationTests(unittest.TestCase):
    def test_both_genres_compile_to_golden_and_preserve_source_snapshot(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                spec = _spec(kind)
                self.assertEqual(campaign_spec_to_document(spec), _expected_document(kind))
                self.assertEqual(
                    narrative_model_to_document(spec.source_narrative_model),
                    narrative_model_to_document(_model(kind)),
                )
                self.assertEqual(
                    validate_campaign_spec_document(campaign_spec_to_document(spec)),
                    spec,
                )
                self.assertEqual(
                    _plan(kind).source_narrative_model.narrative_model_sha256,
                    narrative_model_sha256(_model(kind)),
                )

    def test_source_identity_must_match_exactly(self) -> None:
        for field, value in (("model_id", "other_model"), ("format_version", 2)):
            with self.subTest(field=field):
                document = _plan_document()
                document["source_narrative_model"][field] = value
                if field == "format_version":
                    with self.assertRaises(CampaignValidationError):
                        validate_registry_campaign_plan_document(document)
                else:
                    with self.assertRaisesRegex(CampaignBuildError, "does not match"):
                        compile_campaign_spec(
                            _model(), validate_registry_campaign_plan_document(document)
                        )

    def test_same_id_snapshot_drift_is_rejected_by_canonical_sha256(self) -> None:
        document = _model_document()
        document["propositions"][0]["statement"] = (
            "The same stable proposition ID now carries changed public fixture text."
        )
        drifted = validate_narrative_model_document(document)
        self.assertEqual(drifted.model_id, _model().model_id)
        self.assertNotEqual(narrative_model_sha256(drifted), narrative_model_sha256(_model()))
        with self.assertRaisesRegex(CampaignBuildError, "narrative_model_sha256"):
            compile_campaign_spec(drifted, _plan())

    def test_each_source_category_requires_complete_accounting(self) -> None:
        def add_entity(document: dict) -> None:
            document["scope"]["entity_refs"].append("entity_unbound")

        def add_perspective(document: dict) -> None:
            document["perspectives"].append(
                {
                    "perspective_id": "perspective_unbound",
                    "entity_ref": "entity_field_mender",
                    "summary": "An unbound public fixture perspective.",
                }
            )
            document["beats"][0]["perspective_refs"].append("perspective_unbound")

        def add_proposition(document: dict) -> None:
            document["propositions"].append(
                {
                    "proposition_id": "prop_unbound",
                    "statement": "An unbound public fixture proposition.",
                    "status": "adaptation_only",
                    "claim_refs": [],
                    "rationale": "Exercise campaign accounting closure.",
                }
            )
            document["beats"][0]["proposition_refs"].append("prop_unbound")

        def add_beat(document: dict) -> None:
            document["beats"].append(
                {
                    "beat_id": "beat_unbound",
                    "phase_ref": "phase_resolution",
                    "predecessor_refs": ["beat_parley"],
                    "perspective_refs": ["perspective_mender"],
                    "proposition_refs": ["prop_mender_can_retune"],
                    "disclosures": [],
                    "summary": "An unbound public fixture beat.",
                }
            )

        for category, mutation in (
            ("entity", add_entity),
            ("perspective", add_perspective),
            ("proposition", add_proposition),
            ("beat", add_beat),
        ):
            with self.subTest(category=category):
                document = _model_document()
                mutation(document)
                model = validate_narrative_model_document(document)
                with self.assertRaisesRegex(CampaignBuildError, f"{category}s"):
                    compile_campaign_spec(model, _plan())

    def test_foreign_bound_refs_are_rejected_for_all_source_categories(self) -> None:
        cases = ("entity", "perspective", "proposition", "beat")
        for category in cases:
            with self.subTest(category=category):
                document = _plan_document()
                if category == "entity":
                    actor = _item(document, "actors", "actor_id", "actor_echo")
                    actor["source_entity_ref"] = "entity_foreign"
                    uses = document["scope"]["entity_uses"]
                    uses[uses.index("entity_storm_echo")] = "entity_foreign"
                elif category == "perspective":
                    knowledge = _item(
                        document,
                        "knowledge_beats",
                        "knowledge_id",
                        "knowledge_echo_intent",
                    )
                    knowledge["perspective_ref"] = "perspective_foreign"
                    uses = document["scope"]["perspective_uses"]
                    uses[uses.index("perspective_echo")] = "perspective_foreign"
                elif category == "proposition":
                    actor = _item(document, "actors", "actor_id", "actor_echo")
                    actor["source_proposition_refs"].append("prop_foreign")
                    document["scope"]["proposition_uses"].append("prop_foreign")
                else:
                    scene = _item(document, "scenes", "scene_id", "scene_arrival")
                    scene["narrative_beat_refs"].append("beat_foreign")
                    document["scope"]["beat_uses"].append("beat_foreign")
                plan = validate_registry_campaign_plan_document(document)
                with self.assertRaisesRegex(CampaignBuildError, "foreign"):
                    compile_campaign_spec(_model(), plan)

    def test_reasoned_omission_closes_an_unbound_source_entity(self) -> None:
        document = _plan_document()
        actor = _item(document, "actors", "actor_id", "actor_echo")
        actor["source_entity_ref"] = None
        document["scope"]["entity_uses"].remove("entity_storm_echo")
        document["scope"]["entity_omissions"] = [
            {
                "entity_ref": "entity_storm_echo",
                "reason": "The event uses its perspective and proposition but no direct actor binding.",
            }
        ]
        spec = compile_campaign_spec(
            _model(), validate_registry_campaign_plan_document(document)
        )
        self.assertEqual(
            spec.scope.entity_omissions[0].source_ref, "entity_storm_echo"
        )

    def test_scene_mapping_preserves_source_phase_and_reachability(self) -> None:
        document = _plan_document()
        parley = _item(document, "scenes", "scene_id", "scene_parley")
        parley["predecessor_scene_refs"] = []
        plan = validate_registry_campaign_plan_document(document)
        with self.assertRaisesRegex(CampaignBuildError, "beat reachability"):
            compile_campaign_spec(_model(), plan)

        document = _plan_document()
        parley = _item(document, "scenes", "scene_id", "scene_parley")
        parley["phase_ref"] = "phase_opening"
        objective = _item(
            document, "objectives", "objective_id", "objective_hear_echo"
        )
        objective["phase_ref"] = "phase_opening"
        plan = validate_registry_campaign_plan_document(document)
        with self.assertRaisesRegex(CampaignBuildError, "does not match"):
            compile_campaign_spec(_model(), plan)

        document = _plan_document()
        parley = _item(document, "scenes", "scene_id", "scene_parley")
        parley["narrative_beat_refs"].append("beat_arrival")
        plan = validate_registry_campaign_plan_document(document)
        with self.assertRaisesRegex(CampaignBuildError, "multiple scenes"):
            compile_campaign_spec(_model(), plan)

    def test_knowledge_beats_must_exactly_project_source_disclosures(self) -> None:
        document = _plan_document()
        knowledge = _item(
            document,
            "knowledge_beats",
            "knowledge_id",
            "knowledge_echo_intent",
        )
        knowledge["state"] = "confirmed"
        plan = validate_registry_campaign_plan_document(document)
        with self.assertRaisesRegex(CampaignBuildError, "exactly project"):
            compile_campaign_spec(_model(), plan)

    def test_retraction_requires_a_reachable_earlier_projected_belief(self) -> None:
        model_document = _model_document()
        parley = _item(model_document, "beats", "beat_id", "beat_parley")
        parley["disclosures"][0]["state"] = "retracted"
        model = validate_narrative_model_document(model_document)

        plan_document = _plan_document()
        knowledge = _item(
            plan_document,
            "knowledge_beats",
            "knowledge_id",
            "knowledge_echo_intent",
        )
        knowledge["state"] = "retracted"
        plan = validate_registry_campaign_plan_document(plan_document)
        with self.assertRaisesRegex(CampaignBuildError, "retracts without"):
            compile_campaign_spec(model, plan)

    def test_impossible_source_disclosure_regression_is_rejected(self) -> None:
        model_document = _model_document("urban_investigation")
        rumor = _item(model_document, "beats", "beat_id", "beat_rumor")
        records = _item(model_document, "beats", "beat_id", "beat_records")
        rumor_disclosure = next(
            value
            for value in rumor["disclosures"]
            if value["proposition_ref"] == "prop_cart_left_east"
        )
        records_disclosure = next(
            value
            for value in records["disclosures"]
            if value["proposition_ref"] == "prop_cart_left_east"
        )
        rumor_disclosure["state"] = "confirmed"
        records_disclosure["state"] = "heard"
        model = validate_narrative_model_document(model_document)

        plan_document = _plan_document("urban_investigation")
        heard = _item(
            plan_document,
            "knowledge_beats",
            "knowledge_id",
            "knowledge_cart_heard",
        )
        retracted = _item(
            plan_document,
            "knowledge_beats",
            "knowledge_id",
            "knowledge_cart_retracted",
        )
        heard["state"] = "confirmed"
        retracted["state"] = "heard"
        plan_document["knowledge_corrections"] = []
        objective = _item(
            plan_document,
            "objectives",
            "objective_id",
            "objective_verify_timeline",
        )
        objective["completion"] = {
            "kind": "apply_knowledge",
            "knowledge_ref": "knowledge_cart_locked",
        }
        plan = validate_registry_campaign_plan_document(plan_document)
        with self.assertRaisesRegex(CampaignBuildError, "impossible source disclosure"):
            compile_campaign_spec(model, plan)

    def test_urban_repeated_knowledge_track_must_be_totally_source_ordered(self) -> None:
        model_document = _model_document("urban_investigation")
        for suffix in ("a", "b"):
            model_document["beats"].append(
                {
                    "beat_id": f"beat_branch_{suffix}",
                    "phase_ref": "phase_decision",
                    "predecessor_refs": ["beat_records"],
                    "perspective_refs": ["perspective_records"],
                    "proposition_refs": ["prop_cart_remained_locked"],
                    "disclosures": [
                        {
                            "perspective_ref": "perspective_records",
                            "proposition_ref": "prop_cart_remained_locked",
                            "state": "confirmed",
                        }
                    ],
                    "summary": f"Independent public fixture branch {suffix} repeats the record.",
                }
            )
        model = validate_narrative_model_document(model_document)

        plan_document = _plan_document("urban_investigation")
        plan_document["source_narrative_model"]["narrative_model_sha256"] = (
            narrative_model_sha256(model)
        )
        report = _item(
            plan_document, "objectives", "objective_id", "objective_file_report"
        )
        for suffix in ("a", "b"):
            scene_id = f"scene_branch_{suffix}"
            beat_id = f"beat_branch_{suffix}"
            plan_document["scenes"].append(
                {
                    "scene_id": scene_id,
                    "kind": "revelation",
                    "phase_ref": "phase_decision",
                    "location_ref": "location_records_office",
                    "participating_actor_refs": ["actor_investigator"],
                    "narrative_beat_refs": [beat_id],
                    "predecessor_scene_refs": ["scene_records"],
                    "source_proposition_refs": ["prop_cart_remained_locked"],
                    "adaptation_notes": "Exercise unordered branch knowledge rejection.",
                }
            )
            plan_document["knowledge_beats"].append(
                {
                    "knowledge_id": f"knowledge_branch_{suffix}",
                    "scene_ref": scene_id,
                    "actor_ref": "actor_investigator",
                    "source_beat_ref": beat_id,
                    "perspective_ref": "perspective_records",
                    "proposition_ref": "prop_cart_remained_locked",
                    "state": "confirmed",
                    "adaptation_notes": "Exact branch disclosure projection.",
                }
            )
            plan_document["scope"]["beat_uses"].append(beat_id)
            report["scene_refs"].append(scene_id)
        plan = validate_registry_campaign_plan_document(plan_document)
        with self.assertRaisesRegex(CampaignBuildError, "unordered source updates"):
            compile_campaign_spec(model, plan)

    def test_urban_source_order_also_requires_campaign_scene_reachability(self) -> None:
        document = _plan_document("urban_investigation")
        tail = _item(document, "scenes", "scene_id", "scene_tail")
        tail["predecessor_scene_refs"] = []
        plan = validate_registry_campaign_plan_document(document)
        with self.assertRaisesRegex(CampaignBuildError, "beat reachability"):
            compile_campaign_spec(_model("urban_investigation"), plan)

    def test_embedded_snapshot_cannot_be_reinterpreted_after_compilation(self) -> None:
        document = _expected_document()
        source_beat = _item(
            document["source_narrative_model"], "beats", "beat_id", "beat_parley"
        )
        source_beat["disclosures"][0]["state"] = "confirmed"
        with self.assertRaisesRegex(CampaignValidationError, "exactly project"):
            validate_campaign_spec_document(document)

    def test_malformed_and_noncanonical_typed_inputs_are_build_errors(self) -> None:
        malformed_model = replace(_model(), beats=("bad",))
        with self.assertRaises(CampaignBuildError):
            compile_campaign_spec(malformed_model, _plan())

        malformed_plan = replace(_plan(), campaign_id=1)
        with self.assertRaises(CampaignBuildError):
            compile_campaign_spec(_model(), malformed_plan)

        noncanonical = replace(_plan(), actors=tuple(reversed(_plan().actors)))
        with self.assertRaisesRegex(CampaignBuildError, "canonical"):
            compile_campaign_spec(_model(), noncanonical)


class SchemaAndGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = {
            name: _read_json(REPO / "schemas" / name)
            for name in (
                "registry_campaign_plan.schema.json",
                "campaign_spec.schema.json",
                "narrative_model.schema.json",
            )
        }
        resources = [
            (schema["$id"], Resource.from_contents(schema))
            for schema in cls.schemas.values()
        ]
        cls.registry = Registry().with_resources(resources)

    def test_schemas_are_valid_draft_2020_12_contracts(self) -> None:
        for name in (
            "registry_campaign_plan.schema.json",
            "campaign_spec.schema.json",
        ):
            with self.subTest(name=name):
                schema = self.schemas[name]
                self.assertEqual(
                    schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
                )
                self.assertFalse(schema["additionalProperties"])
                Draft202012Validator.check_schema(schema)

    def test_plan_and_spec_schemas_share_start_and_completion_contracts(
        self,
    ) -> None:
        plan_schema = self.schemas["registry_campaign_plan.schema.json"]
        spec_schema = self.schemas["campaign_spec.schema.json"]
        self.assertEqual(
            plan_schema["properties"]["start_location_ref"]["$ref"],
            "#/$defs/campaign_start_location_ref",
        )
        self.assertEqual(
            spec_schema["properties"]["start_location_ref"]["$ref"],
            "registry_campaign_plan.schema.json#/$defs/campaign_start_location_ref",
        )
        self.assertEqual(
            spec_schema["properties"]["objectives"]["items"]["$ref"],
            "registry_campaign_plan.schema.json#/$defs/objective",
        )
        self.assertIn(
            "must equal",
            plan_schema["$defs"]["campaign_start_location_ref"]["description"],
        )
        for completion_name in (
            "reach_location_completion",
            "interact_actor_completion",
            "complete_scene_completion",
            "apply_knowledge_completion",
        ):
            with self.subTest(completion=completion_name):
                self.assertIn(
                    "objective",
                    plan_schema["$defs"][completion_name]["description"],
                )

    def test_all_plan_and_golden_instances_validate_against_schemas(self) -> None:
        plan_validator = Draft202012Validator(
            self.schemas["registry_campaign_plan.schema.json"],
            registry=self.registry,
        )
        spec_validator = Draft202012Validator(
            self.schemas["campaign_spec.schema.json"], registry=self.registry
        )
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(list(plan_validator.iter_errors(_plan_document(kind))), [])
                self.assertEqual(
                    list(spec_validator.iter_errors(_expected_document(kind))), []
                )

    def test_schema_rejects_bool_boundaries_and_union_field_leakage(self) -> None:
        validator = Draft202012Validator(
            self.schemas["registry_campaign_plan.schema.json"],
            registry=self.registry,
        )
        document = _plan_document()
        document["format_version"] = True
        self.assertTrue(list(validator.iter_errors(document)))

        document = _plan_document()
        document["source_narrative_model"]["narrative_model_sha256"] = "A" * 64
        self.assertTrue(list(validator.iter_errors(document)))

        document = _plan_document()
        document["objectives"][0]["completion"]["actor_ref"] = "actor_echo"
        self.assertTrue(list(validator.iter_errors(document)))

    def test_golden_bytes_are_stable_for_both_genres(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp_dir:
                output = Path(temp_dir) / "campaign_spec.json"
                write_campaign_spec(_spec(kind), output)
                self.assertEqual(
                    output.read_bytes(), _path(kind, "expected_spec.json").read_bytes()
                )


class WriterTests(unittest.TestCase):
    def test_writer_returns_resolved_path_and_fsyncs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "campaign_spec.json"
            with patch("pipeline.campaign.os.fsync") as fsync:
                result = write_campaign_spec(_spec(), output)
            self.assertEqual(result, output.resolve())
            fsync.assert_called_once()

    def test_replace_failure_preserves_output_and_cleans_owned_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "campaign_spec.json"
            output.write_bytes(b"old\n")
            with patch("pipeline.campaign.os.replace", side_effect=OSError("blocked")):
                with self.assertRaises(OSError):
                    write_campaign_spec(_spec(), output)
            self.assertEqual(output.read_bytes(), b"old\n")
            self.assertEqual(
                list(Path(temp_dir).glob(".campaign_spec.json.*.tmp")), []
            )

    def test_prevalidation_precedes_temp_creation_and_missing_parent_is_error(self) -> None:
        invalid = replace(_spec(), campaign_id="Not-Stable")
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pipeline.campaign.tempfile.mkstemp") as mkstemp:
                with self.assertRaises(CampaignValidationError):
                    write_campaign_spec(invalid, Path(temp_dir) / "spec.json")
            mkstemp.assert_not_called()
            with self.assertRaises(FileNotFoundError):
                write_campaign_spec(
                    _spec(), Path(temp_dir) / "missing" / "spec.json"
                )

    def test_writer_rejects_output_symlink_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            target = temp / "target.json"
            target.write_bytes(b"old\n")
            output = temp / "spec.json"
            try:
                os.symlink(target, output)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaises(OSError):
                write_campaign_spec(_spec(), output)
            self.assertEqual(target.read_bytes(), b"old\n")

    def test_writer_uses_flush_fsync_and_replace(self) -> None:
        source = inspect.getsource(write_campaign_spec)
        for token in ("os.fdopen", "handle.flush()", "os.fsync", "os.replace"):
            self.assertIn(token, source)


class CliTests(unittest.TestCase):
    def _args(self, kind: str, output: Path) -> list[str]:
        return [
            "--narrative-model",
            str(_path(kind, "narrative_model.json")),
            "--campaign-plan",
            str(_path(kind, "valid_plan.json")),
            "--output",
            str(output),
        ]

    def test_in_process_cli_matches_both_goldens_and_preserves_inputs(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp_dir:
                model_path = _path(kind, "narrative_model.json")
                plan_path = _path(kind, "valid_plan.json")
                before = (model_path.read_bytes(), plan_path.read_bytes())
                output = Path(temp_dir) / "spec.json"
                self.assertEqual(main(self._args(kind, output)), 0)
                self.assertEqual(
                    output.read_bytes(), _path(kind, "expected_spec.json").read_bytes()
                )
                self.assertEqual(before, (model_path.read_bytes(), plan_path.read_bytes()))

    def test_repository_external_module_invocation_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "external_spec.json"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.campaign",
                    *self._args("urban_investigation", output),
                ],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                output.read_bytes(),
                _path("urban_investigation", "expected_spec.json").read_bytes(),
            )

    def test_missing_arguments_exit_two(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--narrative-model", str(_path("magic_event", "narrative_model.json"))])
        self.assertEqual(caught.exception.code, 2)

    def test_bad_json_and_missing_parent_return_one_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bad = temp / "bad.json"
            bad.write_text("{", encoding="utf-8")
            output = temp / "out.json"
            args = self._args("magic_event", output)
            args[args.index(str(_path("magic_event", "valid_plan.json")))] = str(bad)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())

            missing = temp / "missing" / "out.json"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args("magic_event", missing)), 1)
            self.assertFalse(missing.exists())

    def test_direct_and_hardlink_output_aliases_are_rejected(self) -> None:
        for input_name in ("narrative_model.json", "valid_plan.json"):
            with self.subTest(input_name=input_name):
                input_path = _path("magic_event", input_name)
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(main(self._args("magic_event", input_path)), 1)
                self.assertIn("points to an input file", stderr.getvalue())

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            model = temp / "model.json"
            plan = temp / "plan.json"
            model.write_bytes(_path("magic_event", "narrative_model.json").read_bytes())
            plan.write_bytes(_path("magic_event", "valid_plan.json").read_bytes())
            output = temp / "output.json"
            try:
                os.link(plan, output)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            before = plan.read_bytes()
            args = [
                "--narrative-model",
                str(model),
                "--campaign-plan",
                str(plan),
                "--output",
                str(output),
            ]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertEqual(plan.read_bytes(), before)
            self.assertEqual(output.read_bytes(), before)

    def test_input_aliases_and_symlinks_are_rejected_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            same = temp / "same.json"
            same.write_text("not json", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(
                    [
                        "--narrative-model",
                        str(same),
                        "--campaign-plan",
                        str(same),
                        "--output",
                        str(temp / "out.json"),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertIn("Input paths point to the same file", stderr.getvalue())

            model = temp / "model.json"
            model.write_bytes(_path("magic_event", "narrative_model.json").read_bytes())
            model_link = temp / "model-link.json"
            output_link = temp / "output-link.json"
            try:
                os.symlink(model, model_link)
                os.symlink(model, output_link)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            args = [
                "--narrative-model",
                str(model_link),
                "--campaign-plan",
                str(_path("magic_event", "valid_plan.json")),
                "--output",
                str(temp / "out.json"),
            ]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args("magic_event", output_link)), 1)


if __name__ == "__main__":
    unittest.main()
