"""L2W-4 tests for registry-backed micro adaptation."""

from __future__ import annotations

import copy
import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "registry_adaptation"
sys.path.insert(0, str(REPO))

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.world import World
from pipeline.canon_registry import validate_canon_registry_document
from pipeline.registry_adaptation import (
    RegistryAdaptationManifest,
    RegistryAdaptationPlan,
    RegistryAdaptationValidationError,
    RegistryCompilationError,
    RegistryMicroContentPack,
    RegistryOmissionEntry,
    RegistryClaimRef,
    compile_registry_micro_pack,
    main,
    registry_adaptation_manifest_to_document,
    registry_pack_to_documents,
    validate_registry_adaptation_manifest_document,
    validate_registry_adaptation_plan,
    write_registry_micro_pack,
)


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def registry_data() -> dict:
    return _read_json(FIXTURE / "canon_registry.json")


def plan_data() -> dict:
    return _read_json(FIXTURE / "valid_plan.json")


def registry():
    return validate_canon_registry_document(registry_data())


def plan():
    return validate_registry_adaptation_plan(plan_data())


def compiled():
    return compile_registry_micro_pack(registry(), plan())


def _registry_with_omitted_entity() -> tuple[dict, dict]:
    data = registry_data()
    data["entities"].append(
        {
            "entity_id": "canon_spare_chime",
            "entity_type": "item",
            "canonical_name": "Spare Chime",
            "aliases": [],
            "members": [
                {
                    "promotion_id": "promo_ch001",
                    "source_entity_id": "source_spare_chime",
                    "source_candidate_id": "candidate_spare_chime",
                    "source_canonical_name": "Spare Chime",
                    "source_aliases": [],
                }
            ],
            "claims": [
                {
                    "source": {
                        "promotion_id": "promo_ch001",
                        "source_entity_id": "source_spare_chime",
                        "source_claim_id": "claim_description",
                    },
                    "predicate": "description",
                    "value": {"kind": "text", "text": "A spare bronze chime."},
                    "source_chapters": ["chapter_000001"],
                    "source_support": "explicit",
                    "certainty": "certain",
                    "inference_basis": None,
                    "review_reason": "The spare is described directly.",
                }
            ],
            "merge_reason": "This item has one reviewed source entity.",
        }
    )
    plan = plan_data()
    plan["omissions"] = [
        {"registry_entity_ref": "canon_spare_chime", "reason": "Outside this slice."}
    ]
    return data, plan


class FrozenModelTests(unittest.TestCase):
    def test_plan_and_manifest_models_are_frozen(self):
        self.assertTrue(RegistryAdaptationPlan.__dataclass_params__.frozen)
        self.assertTrue(RegistryAdaptationManifest.__dataclass_params__.frozen)
        value = plan()
        with self.assertRaises(FrozenInstanceError):
            value.adaptation_id = "changed"  # type: ignore[misc]

    def test_micro_pack_type_checks(self):
        pack = compiled()
        with self.assertRaises(TypeError):
            RegistryMicroContentPack(
                pack=(), rooms=pack.rooms, items=pack.items, characters=pack.characters,
                quests=pack.quests, dialogues=pack.dialogues, monsters=pack.monsters,
                shops=pack.shops, manifest=pack.manifest,
            )
        with self.assertRaises(TypeError):
            RegistryMicroContentPack(
                pack={}, rooms={"bad": 1}, items=pack.items, characters=pack.characters,
                quests=pack.quests, dialogues=pack.dialogues, monsters=pack.monsters,
                shops=pack.shops, manifest=pack.manifest,
            )


class PlanValidationTests(unittest.TestCase):
    def test_valid_plan(self):
        self.assertEqual(plan().source_registry_id, "fixture_registry")
        self.assertEqual(len(plan().character.registry_claim_refs), 2)

    def test_root_bool_and_version_matrix(self):
        for key, value in (("format_version", True), ("source_registry_version", True)):
            data = plan_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(RegistryAdaptationValidationError):
                validate_registry_adaptation_plan(data)

    def test_unknown_root_and_nested_field(self):
        data = plan_data()
        data["unexpected"] = 1
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)
        data = plan_data()
        data["character"]["unexpected"] = 1
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)

    def test_stable_id_matrix(self):
        cases = [
            ("adaptation_id", "Bad ID"),
            ("source_registry_id", "Bad ID"),
            ("pack.id", "Bad ID"),
            ("pack.start_room_id", "Bad ID"),
            ("room.registry_entity_ref", "Bad ID"),
            ("room.game_id", "Bad ID"),
            ("quest.game_id", "Bad ID"),
            ("dialogue.start_node_id", "Bad ID"),
        ]
        for path, value in cases:
            data = plan_data()
            target = data
            parts = path.split(".")
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
            with self.subTest(path=path), self.assertRaises(
                RegistryAdaptationValidationError
            ):
                validate_registry_adaptation_plan(data)

    def test_bool_and_invalid_integer_nested(self):
        for path in (
            ("pack", "player", "max_hp"),
            ("pack", "player", "attack"),
            ("pack", "player", "defense"),
            ("pack", "player", "inventory_capacity"),
            ("pack", "player", "coins"),
            ("quest", "required_quantity"),
            ("quest", "reward_experience"),
        ):
            data = plan_data()
            target = data
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = True
            with self.subTest(path=path), self.assertRaises(
                RegistryAdaptationValidationError
            ):
                validate_registry_adaptation_plan(data)

    def test_claim_ref_is_composite_and_strict(self):
        data = plan_data()
        ref = data["room"]["registry_claim_refs"][0]
        ref.pop("source_claim_id")
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)
        data = plan_data()
        data["room"]["registry_claim_refs"].append(
            {
                "promotion_id": "promo_ch001",
                "source_entity_id": "source_echo_vault",
                "source_claim_id": "claim_description",
            }
        )
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)

    def test_dialogue_nested_contract(self):
        data = plan_data()
        data["dialogue"]["nodes"][0]["options"][0]["next_node_id"] = []
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)
        data = plan_data()
        data["dialogue"]["nodes"][0]["options"][0]["effects"] = [{"kind": "x"}]
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)

    def test_omission_duplicate(self):
        data = plan_data()
        data["omissions"] = [
            {"registry_entity_ref": "canon_spare", "reason": "one"},
            {"registry_entity_ref": "canon_spare", "reason": "two"},
        ]
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_plan(data)


class CompilationTests(unittest.TestCase):
    def test_registry_id_and_version_mismatch(self):
        current = plan()
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, source_registry_id="other_registry")
            )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, source_registry_version=2)
            )

    def test_entity_missing_type_and_reuse(self):
        current = plan()
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, room=replace(current.room, registry_entity_ref="missing"))
            )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, room=replace(current.room, registry_entity_ref="canon_lyra"))
            )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, item=replace(current.item, registry_entity_ref="canon_lyra"))
            )

    def test_foreign_and_missing_claims_are_rejected(self):
        current = plan()
        foreign = RegistryClaimRef("promo_ch001", "source_echo_vault", "claim_description")
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, character=replace(current.character, registry_claim_refs=(foreign,)))
            )
        missing = replace(
            current.character,
            registry_claim_refs=(current.character.registry_claim_refs[0],),
        )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(registry(), replace(current, character=missing))

    def test_duplicate_manual_claim_ref_is_rejected(self):
        current = plan()
        duplicated = replace(
            current.room,
            registry_claim_refs=(
                current.room.registry_claim_refs[0],
                current.room.registry_claim_refs[0],
            ),
        )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(registry(), replace(current, room=duplicated))

    def test_coverage_requires_every_other_entity_omitted(self):
        raw_registry, raw_plan = _registry_with_omitted_entity()
        current_registry = validate_canon_registry_document(raw_registry)
        missing_omission_plan = validate_registry_adaptation_plan(
            dict(raw_plan, omissions=[])
        )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(current_registry, missing_omission_plan)
        valid = validate_registry_adaptation_plan(raw_plan)
        self.assertEqual(len(compile_registry_micro_pack(current_registry, valid).manifest.omissions), 1)

    def test_selected_entity_cannot_be_omitted(self):
        current = plan()
        bad = replace(
            current,
            omissions=(RegistryOmissionEntry("canon_echo_vault", "wrong"),),
        )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(registry(), bad)

    def test_game_id_and_target_reference_invariants(self):
        current = plan()
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, dialogue=replace(current.dialogue, character_id="other"))
            )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, quest=replace(current.quest, target_item_id="other"))
            )
        with self.assertRaises(RegistryCompilationError):
            compile_registry_micro_pack(
                registry(), replace(current, quest=replace(current.quest, game_id=current.dialogue.game_id))
            )

    def test_output_scope_and_verbatim_text(self):
        pack = compiled()
        self.assertEqual(len(pack.rooms), 1)
        self.assertEqual(len(pack.characters), 1)
        self.assertEqual(len(pack.items), 1)
        self.assertEqual(len(pack.quests), 1)
        self.assertEqual(len(pack.dialogues), 1)
        self.assertEqual(pack.monsters, ())
        self.assertEqual(pack.shops, ())
        self.assertEqual(pack.rooms[0]["description"], plan_data()["room"]["description"])
        self.assertEqual(pack.items[0]["description"], plan_data()["item"]["description"])
        self.assertEqual(pack.pack["extensions"]["canon_provider"]["kind"], "registry_adaptation_manifest")
        self.assertEqual(pack.pack["extensions"]["canon_provider"]["path"], "registry_adaptation_manifest.json")
        self.assertEqual(pack.characters[0]["canon_ref"]["source_chapters"], ["chapter_000001", "chapter_000002"])

    def test_conflicting_character_claims_are_preserved(self):
        manifest = compiled().manifest
        binding = next(item for item in manifest.bindings if item.game_kind == "character")
        self.assertEqual(
            [(ref.promotion_id, ref.source_entity_id, ref.source_claim_id) for ref in binding.registry_claim_refs],
            [
                ("promo_ch001", "source_lyra_early", "claim_role"),
                ("promo_ch002", "source_lyra_later", "claim_role"),
            ],
        )


class DeterminismTests(unittest.TestCase):
    def test_reversed_registry_and_claim_input_is_byte_stable(self):
        raw_registry = registry_data()
        raw_registry["entities"].reverse()
        raw_registry["sources"].reverse()
        raw_plan = plan_data()
        raw_plan["character"]["registry_claim_refs"].reverse()
        first = registry_pack_to_documents(compiled())
        second = registry_pack_to_documents(
            compile_registry_micro_pack(
                validate_canon_registry_document(raw_registry),
                validate_registry_adaptation_plan(raw_plan),
            )
        )
        self.assertEqual(first, second)

    def test_reversed_omissions_are_byte_stable(self):
        raw_registry, raw_plan = _registry_with_omitted_entity()
        raw_plan["omissions"].reverse()
        first_registry = validate_canon_registry_document(raw_registry)
        first_plan = validate_registry_adaptation_plan(_registry_with_omitted_entity()[1])
        second_plan = validate_registry_adaptation_plan(raw_plan)
        self.assertEqual(
            registry_pack_to_documents(compile_registry_micro_pack(first_registry, first_plan)),
            registry_pack_to_documents(compile_registry_micro_pack(first_registry, second_plan)),
        )


class ManifestValidationTests(unittest.TestCase):
    def test_valid_round_trip_and_canonical_sorting(self):
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        parsed = validate_registry_adaptation_manifest_document(document)
        self.assertEqual(parsed, compiled().manifest)
        self.assertEqual([b.game_kind for b in parsed.bindings], ["character", "item", "room"])

    def test_manifest_bool_and_unknown_field(self):
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["source_registry_version"] = True
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["unexpected"] = 1
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)

    def test_manifest_missing_or_foreign_claim_and_chapter_mismatch(self):
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["bindings"][0]["registry_claim_refs"][0]["promotion_id"] = "foreign"
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["bindings"][0]["source_chapters"] = ["chapter_000001"]
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)

    def test_manifest_duplicate_and_cross_set_ids(self):
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["bindings"].append(copy.deepcopy(document["bindings"][0]))
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        document["game_only"][0]["game_id"] = document["bindings"][0]["game_id"]
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)

    def test_manifest_sources_are_complete_and_distinct(self):
        document = registry_adaptation_manifest_to_document(compiled().manifest)
        source = copy.deepcopy(document["sources"][0])
        document["sources"].append(source)
        with self.assertRaises(RegistryAdaptationValidationError):
            validate_registry_adaptation_manifest_document(document)


class SchemaTests(unittest.TestCase):
    def _schema(self, name: str) -> dict:
        return _read_json(REPO / "schemas" / name)

    def test_plan_is_draft_2020_12_and_strict(self):
        schema = self._schema("registry_adaptation_plan.schema.json")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["$defs"]["entity_adaptation"]["properties"]["registry_claim_refs"]["minItems"], 1)
        self.assertEqual(schema["$defs"]["quest_adaptation"]["properties"]["required_quantity"], {"const": 1})

    def test_manifest_has_complete_sources_and_exact_counts(self):
        schema = self._schema("registry_adaptation_manifest.schema.json")
        self.assertEqual(schema["properties"]["bindings"]["minItems"], 3)
        self.assertEqual(schema["properties"]["bindings"]["maxItems"], 3)
        self.assertEqual(schema["properties"]["game_only"]["minItems"], 2)
        self.assertEqual(schema["properties"]["game_only"]["maxItems"], 2)
        self.assertEqual(
            set(schema["$defs"]["source"]["required"]),
            {"promotion_id", "chapter_id", "chapter_sha256", "extracted_by", "review_id", "reviewed_by"},
        )


class WriterTests(unittest.TestCase):
    def test_golden_serializer_and_writer(self):
        expected_dir = FIXTURE / "expected_output"
        pack = compiled()
        for filename, payload in registry_pack_to_documents(pack):
            self.assertEqual(payload, (expected_dir / filename).read_bytes(), filename)
        with tempfile.TemporaryDirectory() as td:
            output = write_registry_micro_pack(pack, Path(td) / "output")
            for filename, payload in registry_pack_to_documents(pack):
                self.assertEqual((output / filename).read_bytes(), payload)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_registry_micro_pack(compiled(), output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_prevalidation_happens_before_temp_creation(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            invalid = compiled()
            with patch(
                "pipeline.registry_adaptation.registry_pack_to_documents",
                return_value=[("bad.json", b"{}")],
            ):
                with self.assertRaises(RegistryCompilationError):
                    write_registry_micro_pack(invalid, output)
            self.assertFalse(output.exists())
            self.assertEqual(
                list(Path(td).glob(".l2w_registry_adaptation_*")), []
            )

    def test_staged_failure_cleans_only_invocation_temp(self):
        with tempfile.TemporaryDirectory() as td:
            preserved = Path(td) / ".l2w_registry_adaptation_existing"
            preserved.mkdir()
            (preserved / "marker").write_text("keep", encoding="utf-8")
            with patch(
                "pipeline.registry_adaptation.load_content_pack",
                side_effect=RuntimeError("forced"),
            ):
                with self.assertRaises(RuntimeError):
                    write_registry_micro_pack(compiled(), Path(td) / "output")
            self.assertTrue((preserved / "marker").exists())
            self.assertEqual(list(Path(td).glob(".l2w_registry_adaptation_*")), [preserved])

    def test_second_lexists_race_rejects_publish(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            with patch(
                "pipeline.registry_adaptation.os.path.lexists",
                side_effect=[False, True],
            ):
                with self.assertRaises(FileExistsError):
                    write_registry_micro_pack(compiled(), output)
            self.assertFalse(output.exists())

    def test_writer_contains_flush_and_fsync(self):
        source = inspect.getsource(write_registry_micro_pack)
        self.assertIn(".flush()", source)
        self.assertIn("os.fsync", source)

    @unittest.skipUnless(os.name == "posix", "symlink creation is unavailable on this host")
    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            target.mkdir()
            link = Path(td) / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                write_registry_micro_pack(compiled(), link)


class CLITests(unittest.TestCase):
    def _write_inputs(self, directory: Path) -> tuple[Path, Path]:
        registry_path = directory / "registry.json"
        plan_path = directory / "plan.json"
        registry_path.write_text(
            json.dumps(registry_data(), ensure_ascii=False), encoding="utf-8"
        )
        plan_path.write_text(
            json.dumps(plan_data(), ensure_ascii=False), encoding="utf-8"
        )
        return registry_path, plan_path

    def test_in_process_cli_success_and_failures(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            registry_path, plan_path = self._write_inputs(directory)
            self.assertEqual(
                main(
                    [
                        "--canon-registry",
                        str(registry_path),
                        "--adaptation-plan",
                        str(plan_path),
                        "--output-dir",
                        str(directory / "output"),
                    ]
                ),
                0,
            )
            for filename, payload in registry_pack_to_documents(compiled()):
                self.assertEqual(
                    (directory / "output" / filename).read_bytes(), payload, filename
                )
            bad_plan = directory / "bad_plan.json"
            bad_plan.write_text("{}", encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "--canon-registry",
                        str(registry_path),
                        "--adaptation-plan",
                        str(bad_plan),
                        "--output-dir",
                        str(directory / "bad_output"),
                    ]
                ),
                1,
            )

    def test_subprocess_cli_and_external_validate(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            registry_path, plan_path = self._write_inputs(directory)
            output = directory / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.registry_adaptation",
                    "--canon-registry",
                    str(registry_path),
                    "--adaptation-plan",
                    str(plan_path),
                    "--output-dir",
                    str(output),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            validate = subprocess.run(
                [sys.executable, "-m", "lore2mud", "validate", "--content", str(output)],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            for filename, payload in registry_pack_to_documents(compiled()):
                self.assertEqual((output / filename).read_bytes(), payload)

    def test_output_conflict_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            registry_path, plan_path = self._write_inputs(directory)
            output = directory / "output"
            output.mkdir()
            self.assertEqual(
                main(
                    [
                        "--canon-registry",
                        str(registry_path),
                        "--adaptation-plan",
                        str(plan_path),
                        "--output-dir",
                        str(output),
                    ]
                ),
                1,
            )


class WorldPlaythroughTests(unittest.TestCase):
    def test_loader_world_and_collect_quest(self):
        with tempfile.TemporaryDirectory() as td:
            output = write_registry_micro_pack(compiled(), Path(td) / "output")
            content_pack = load_content_pack(output)
            world = World.from_content_pack(content_pack)
            self.assertEqual(len(content_pack.rooms), 1)
            self.assertIn("quest_lift_key", world.quest_states)
            self.assertFalse(world.quest_states["quest_lift_key"].completed)
            outcome = world.take("item_tuning_key")
            self.assertEqual(outcome.item_id, "item_tuning_key")
            self.assertTrue(world.quest_states["quest_lift_key"].completed)
            self.assertEqual(world.player.experience, 2)


if __name__ == "__main__":
    unittest.main()
