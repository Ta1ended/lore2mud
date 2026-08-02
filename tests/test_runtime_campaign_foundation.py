"""Runtime Campaign Foundation v1 cross-genre contract tests."""

from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud.cli import main
from lore2mud.content import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import (
    PREVIOUS_SAVE_FORMAT_VERSION,
    SAVE_FORMAT_VERSION,
    SaveLoadError,
    SaveLoadService,
    _serialize_world,
)
from lore2mud.engine.world import World, WorldRuleError
from lore2mud.web.app import PlayerSession


ROOT = Path(__file__).resolve().parents[1]
MAGIC = ROOT / "tests" / "fixtures" / "campaign_magic"
URBAN = ROOT / "tests" / "fixtures" / "campaign_urban"


def _world(path: Path) -> World:
    return World.from_content_pack(load_content_pack(path))


class CampaignSchemaAndLoaderTests(unittest.TestCase):
    def test_cross_genre_fixtures_load_and_validate_against_draft_2020_12(self) -> None:
        schema_documents = {
            document["$id"]: document
            for schema_path in (ROOT / "schemas").glob("*.schema.json")
            for document in [json.loads(schema_path.read_text("utf-8"))]
            if "$id" in document
        }
        registry = Registry().with_resources(
            (uri, Resource.from_contents(document))
            for uri, document in schema_documents.items()
        )
        campaign_schema = schema_documents[
            "https://example.invalid/lore2mud/campaign.schema.json"
        ]
        Draft202012Validator.check_schema(campaign_schema)
        validator = Draft202012Validator(campaign_schema, registry=registry)
        for fixture in (MAGIC, URBAN):
            with self.subTest(fixture=fixture.name):
                pack = load_content_pack(fixture)
                self.assertIsNotNone(pack.campaign)
                validator.validate(json.loads((fixture / "campaign.json").read_text("utf-8")))

    def test_optional_campaign_keeps_original_demo_compatible(self) -> None:
        pack = load_content_pack(ROOT / "examples" / "original_demo")
        self.assertIsNone(pack.campaign)
        world = World.from_content_pack(pack)
        self.assertEqual(world.available_campaign_actions(), ())
        self.assertEqual(world.scene_states, {})
        self.assertEqual(world.objective_states, {})
        self.assertEqual(world.knowledge_states, {})

    def test_empty_dialogue_view_nodes_fail_schema_loader_and_cli(self) -> None:
        schema_documents = {
            document["$id"]: document
            for schema_path in (ROOT / "schemas").glob("*.schema.json")
            for document in [json.loads(schema_path.read_text("utf-8"))]
            if "$id" in document
        }
        registry = Registry().with_resources(
            (uri, Resource.from_contents(document))
            for uri, document in schema_documents.items()
        )
        validator = Draft202012Validator(
            schema_documents["https://example.invalid/lore2mud/campaign.schema.json"],
            registry=registry,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "urban"
            shutil.copytree(URBAN, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["dialogue_views"][0]["nodes"] = []
            campaign_path.write_text(
                json.dumps(document, indent=2), encoding="utf-8"
            )

            schema_errors = list(validator.iter_errors(document))
            self.assertTrue(
                any(
                    list(error.absolute_path) == ["dialogue_views", 0, "nodes"]
                    and error.validator == "minItems"
                    for error in schema_errors
                )
            )
            with self.assertRaisesRegex(ContentValidationError, "nodes 不能为空"):
                load_content_pack(path)

            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                exit_code = main(["validate", "--content", str(path)])
            self.assertEqual(exit_code, 1)
            self.assertIn("nodes 不能为空", stderr.getvalue())

    def test_campaign_rejects_dependency_cycles_and_asymmetric_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "urban"
            shutil.copytree(URBAN, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["objectives"][0]["initial_status"] = "inactive"
            document["objectives"][0]["dependency_ids"] = ["objective_clear_vendor"]
            document["objectives"][2]["dependency_ids"] = ["objective_check_camera"]
            document["objectives"][2]["exclusive_with"] = []
            campaign_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(path)
            message = str(caught.exception)
            self.assertIn("依赖图包含环", message)
            self.assertIn("互斥必须对称", message)

    def test_campaign_rejects_unowned_and_multiply_owned_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "magic"
            shutil.copytree(MAGIC, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["interactables"][1]["action_ids"].append("action_open_ward")
            document["actions"].append(
                {
                    "id": "action_unowned",
                    "label": "Unowned",
                    "result_text": "Nothing.",
                    "effects": [],
                }
            )
            campaign_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(path)
            message = str(caught.exception)
            self.assertIn("action_open_ward", message)
            self.assertIn("action_unowned", message)

    def test_campaign_unique_item_rewards_join_cross_source_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "magic"
            shutil.copytree(MAGIC, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["actions"][0]["effects"][0]["item_id"] = "item_moon_key"
            campaign_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(
                ContentValidationError,
                "item_moon_key.*campaign",
            ):
                load_content_pack(path)


    def test_campaign_loader_enforces_schema_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "magic"
            shutil.copytree(MAGIC, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["location_views"][0].pop("exits")
            document["actor_views"][0].pop("descriptions")
            document["scenes"][0].pop("initial_status")
            document["objectives"][0].pop("dependency_ids")
            document["knowledge"][0].pop("initial_status")
            campaign_path.write_text(
                json.dumps(document, indent=2), encoding="utf-8"
            )
            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(path)
            message = str(caught.exception)
            self.assertIn(
                "location_views[0].exits " + "是必填字段", message
            )
            self.assertIn(
                "actor_views[0].descriptions " + "是必填字段", message
            )
            self.assertIn(
                "scenes[0].initial_status " + "是必填字段", message
            )
            self.assertIn(
                "objectives[0].dependency_ids " + "是必填字段", message
            )
            self.assertIn(
                "knowledge[0].initial_status " + "是必填字段", message
            )


class MagicCampaignRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(MAGIC)

    def test_world_projects_description_exit_actor_scene_and_actions(self) -> None:
        self.assertEqual(self.world.available_exits(), {})
        self.assertIn("sleeps", self.world.location_description())
        self.assertEqual(
            [value.id for value in self.world.available_characters()],
            ["character_clockmaker"],
        )
        self.assertEqual(
            [value.id for value in self.world.available_scenes()],
            ["scene_awaken_ward"],
        )
        self.assertEqual(
            [value.id for value in self.world.available_interactables()],
            ["interactable_ward_dial"],
        )
        self.assertEqual(
            [value.action.id for value in self.world.available_campaign_actions()],
            ["action_unstable_charge", "action_open_ward"],
        )

    def test_late_effect_failure_rolls_back_every_mutable_branch(self) -> None:
        before = _serialize_world(self.world)
        with self.assertRaises(WorldRuleError):
            self.world.execute_campaign_action("action_unstable_charge")
        self.assertEqual(_serialize_world(self.world), before)
        self.assertIsNone(self.world.player.inventory.find_stack("item_ward_spark"))

    def test_successful_action_advances_all_runtime_domains(self) -> None:
        outcome = self.world.execute_campaign_action("action_open_ward")
        self.assertEqual(outcome.action_id, "action_open_ward")
        self.assertEqual(self.world.narrative_state["state_ward_power"], 1)
        self.assertEqual(self.world.narrative_state["state_ward_mode"], "open")
        self.assertIn("east", self.world.available_exits())
        self.assertIn("Blue fire", self.world.location_description())
        self.assertEqual(self.world.available_characters(), ())
        self.assertEqual(
            self.world.characters["character_clockmaker"].presence, "absent"
        )
        self.assertEqual(
            self.world.objective_states["objective_awaken_ward"].status,
            "completed",
        )
        self.assertEqual(
            self.world.knowledge_states["knowledge_ward_nature"].status,
            "confirmed",
        )
        self.assertEqual(
            [value.action.id for value in self.world.available_campaign_actions()],
            ["action_finish_ward"],
        )
        self.world.execute_campaign_action("action_finish_ward")
        self.assertEqual(
            self.world.scene_states["scene_awaken_ward"].status, "completed"
        )
        self.assertEqual(self.world.available_interactables(), ())

    def test_hidden_actions_reject_id_cli_string_and_raw_index(self) -> None:
        snapshot = _serialize_world(self.world)
        with self.assertRaisesRegex(WorldRuleError, "当前不可用"):
            self.world.execute_campaign_action("action_finish_ward")
        commands = CommandProcessor(self.world)
        self.assertIn("当前不可用", commands.execute("act action_finish_ward").text)
        self.assertIn("未知指令", commands.execute("3").text)
        self.assertEqual(_serialize_world(self.world), snapshot)

    def test_actor_scene_objective_and_knowledge_round_trip_without_replay(self) -> None:
        pack = load_content_pack(MAGIC)
        self.world.execute_campaign_action("action_open_ward")
        before = _serialize_world(self.world)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(self.world)
            loaded = service.load()
            saved = json.loads((Path(temp_dir) / "default.json").read_text("utf-8"))
        self.assertEqual(SAVE_FORMAT_VERSION, 9)
        self.assertEqual(saved["save_format_version"], 9)
        self.assertEqual(_serialize_world(loaded), before)
        self.assertEqual(
            loaded.player.inventory.find_stack("item_moon_key").quantity,  # type: ignore[union-attr]
            1,
        )
        self.assertEqual(
            loaded.scene_states["scene_awaken_ward"].stage_index, 1
        )

    def test_campaign_rejects_v8_and_strictly_validates_v9_actor_state(self) -> None:
        pack = load_content_pack(MAGIC)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(self.world)
            save_path = Path(temp_dir) / "default.json"
            document = json.loads(save_path.read_text("utf-8"))
            legacy = deepcopy(document)
            legacy["save_format_version"] = PREVIOUS_SAVE_FORMAT_VERSION
            for key in ("actors", "scene_states", "objective_states", "knowledge_states"):
                legacy.pop(key)
            save_path.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaisesRegex(SaveLoadError, "save v8"):
                service.load()

            document["actors"]["character_clockmaker"]["enabled"] = "yes"
            save_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SaveLoadError, "enabled"):
                service.load()


class UrbanKnowledgeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(URBAN)

    def test_dynamic_dialogue_and_knowledge_correction_are_player_scoped(self) -> None:
        self.assertIn(
            "vendor had access",
            self.world.dialogue_node_text("dialogue_dispatcher", "node_report"),
        )
        self.world.execute_campaign_action("action_check_timestamp")
        self.assertIn(
            "already left",
            self.world.dialogue_node_text("dialogue_dispatcher", "node_report"),
        )
        self.world.execute_campaign_action("action_correct_vendor_record")
        self.assertEqual(
            self.world.knowledge_states["knowledge_vendor_access"].status,
            "corrected",
        )
        self.assertEqual(
            self.world.objective_states["objective_clear_vendor"].status,
            "active",
        )
        self.assertEqual(
            self.world.objective_states["objective_accuse_vendor"].status,
            "failed",
        )
        entries = {entry.id: entry for entry in self.world.available_log_entries()}
        self.assertIn("timestamp shows", entries["knowledge_vendor_access"].text)
        self.assertNotIn("unknown", {entry.status for entry in entries.values()})

    def test_objective_dependencies_and_mutual_exclusion_are_authoritative(self) -> None:
        with self.assertRaisesRegex(WorldRuleError, "当前不可用"):
            self.world.execute_campaign_action("action_accuse_vendor")
        self.world.execute_campaign_action("action_check_timestamp")
        self.world.execute_campaign_action("action_accuse_vendor")
        self.assertEqual(
            self.world.objective_states["objective_accuse_vendor"].status,
            "active",
        )
        self.assertEqual(
            self.world.objective_states["objective_clear_vendor"].status,
            "failed",
        )
        with self.assertRaisesRegex(WorldRuleError, "不能激活"):
            self.world._apply_campaign_effect(  # exercise the World gate directly
                self.world.campaign.actions["action_correct_vendor_record"].effects[0]  # type: ignore[union-attr]
            )

    def test_web_returns_structured_actions_and_rejects_hidden_payloads(self) -> None:
        pack = load_content_pack(URBAN)
        with tempfile.TemporaryDirectory() as temp_dir:
            session = PlayerSession(pack, SaveLoadService(pack, Path(temp_dir)))
            initial = session.snapshot()
            self.assertEqual(
                [row["id"] for row in initial["campaign"]["actions"]],
                ["action_check_timestamp"],
            )
            self.assertEqual(
                [row["id"] for row in initial["campaign"]["journal"] if row["category"] == "story"],
                ["log_camera_result"],
            )
            rejected = session.dispatch(
                {"type": "campaign_action", "action_id": "action_correct_vendor_record"}
            )
            self.assertFalse(rejected["ok"])
            self.assertFalse(session.world.narrative_state["state_camera_checked"])
            fallback = session.dispatch(
                {"type": "command", "command": "act action_check_timestamp"}
            )
            self.assertFalse(fallback["ok"])
            accepted = session.dispatch(
                {"type": "campaign_action", "action_id": "action_check_timestamp"}
            )
            self.assertTrue(accepted["ok"])
            self.assertEqual(
                {row["id"] for row in accepted["snapshot"]["campaign"]["actions"]},
                {"action_accuse_vendor", "action_correct_vendor_record"},
            )

    def test_cli_journal_commands_and_help_are_authoritative(self) -> None:
        commands = CommandProcessor(self.world)
        self.assertIn("action_check_timestamp", commands.execute("actions").text)
        self.assertIn("actions", commands.execute("help actions").text)
        self.assertIn("act", commands.execute("help act").text)
        self.assertIn(
            "Check the platform camera", commands.execute("objectives").text
        )
        self.assertIn("Vendor access", commands.execute("knowledge").text)
        self.assertIn("log_camera_result", commands.execute("journal").text)

    def test_active_dialogue_must_remain_player_visible_on_save_and_load(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "urban"
            shutil.copytree(URBAN, path)
            campaign_path = path / "campaign.json"
            document = json.loads(campaign_path.read_text("utf-8"))
            document["actor_views"] = [
                {
                    "actor_id": "character_dispatcher",
                    "descriptions": [{"text": "The dispatcher is at the desk."}],
                    "condition": {
                        "kind": "state_equals",
                        "state_id": "state_camera_checked",
                        "value": False,
                    },
                }
            ]
            campaign_path.write_text(
                json.dumps(document, indent=2), encoding="utf-8"
            )
            pack = load_content_pack(path)
            world = World.from_content_pack(pack)
            world.start_dialogue("character_dispatcher")
            self.assertIsNotNone(world.active_dialogue)
            world.narrative_state["state_camera_checked"] = True
            with self.assertRaisesRegex(SaveLoadError, "不可交互"):
                _serialize_world(world)

            world.narrative_state["state_camera_checked"] = False
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            saved_path = Path(temp_dir) / "default.json"
            document = json.loads(saved_path.read_text("utf-8"))
            document["narrative_state"]["state_camera_checked"] = True
            saved_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SaveLoadError, "不可交互"):
                service.load()


if __name__ == "__main__":
    unittest.main()
