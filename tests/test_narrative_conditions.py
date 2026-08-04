"""GEN-1 contracts for typed narrative state and safe conditions."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.models import QuestState
from lore2mud.engine.save import (
    LEGACY_SAVE_FORMAT_VERSION,
    SAVE_FORMAT_VERSION,
    SaveLoadError,
    SaveLoadService,
)
from lore2mud.engine.world import World, WorldRuleError
from lore2mud.inventory.models import ItemStack
from lore2mud.narrative.conditions import evaluate_condition
from lore2mud.narrative.models import (
    AllCondition,
    AnyCondition,
    AtLocationCondition,
    BoolStateDefinition,
    ConditionContext,
    EnumStateDefinition,
    HasItemCondition,
    IntStateDefinition,
    NotCondition,
    QuestStatusCondition,
    StateCompareCondition,
    StateEqualsCondition,
)
from lore2mud.web.app import PlayerSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class PackCopy:
    def __init__(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "pack"
        shutil.copytree(DEMO_PATH, self.path)

    def close(self) -> None:
        self._temp.cleanup()

    def read(self, name: str) -> object:
        return json.loads((self.path / name).read_text("utf-8"))

    def write(self, name: str, value: object) -> None:
        (self.path / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _beacon_world() -> World:
    world = World.from_content_pack(load_content_pack(DEMO_PATH))
    world.player.room_id = "room_beacon_heart"
    world.player.inventory.stacks.append(ItemStack("item_beacon_core", 1))
    world.quest_states["quest_restore_beacon"] = QuestState(
        "quest_restore_beacon", completed=True
    )
    return world


class NarrativeStateContentTests(unittest.TestCase):
    def test_all_three_frozen_state_definitions_load(self) -> None:
        pack = load_content_pack(DEMO_PATH)

        self.assertEqual(pack.version, "0.10.0")
        self.assertIsInstance(
            pack.narrative_state_defs["state_beacon_enabled"],
            BoolStateDefinition,
        )
        strength = pack.narrative_state_defs["state_signal_strength"]
        self.assertIsInstance(strength, IntStateDefinition)
        self.assertEqual((strength.initial, strength.minimum, strength.maximum), (1, 0, 3))
        mode = pack.narrative_state_defs["state_station_mode"]
        self.assertIsInstance(mode, EnumStateDefinition)
        self.assertEqual(mode.values, ("standby", "active", "silent"))
        with self.assertRaises(FrozenInstanceError):
            strength.initial = 2  # type: ignore[misc]

    def test_missing_optional_state_file_preserves_legacy_pack_loading(self) -> None:
        pack_copy = PackCopy()
        self.addCleanup(pack_copy.close)
        (pack_copy.path / "narrative_state.json").unlink()
        dialogues = pack_copy.read("dialogues.json")
        dialogues[1]["nodes"][0]["options"][0].pop("condition")
        pack_copy.write("dialogues.json", dialogues)

        pack = load_content_pack(pack_copy.path)

        self.assertEqual(pack.narrative_state_defs, {})
        self.assertEqual(World.from_content_pack(pack).narrative_state, {})

    def test_state_definition_invalid_matrix_is_rejected(self) -> None:
        cases = (
            lambda doc: doc["states"][0].update(initial=1),
            lambda doc: doc["states"][1].update(initial=True),
            lambda doc: doc["states"][1].update(initial=4),
            lambda doc: doc["states"][1].update(minimum=4, maximum=2),
            lambda doc: doc["states"][1].update(minimum=None),
            lambda doc: doc["states"][1].update(maximum=None),
            lambda doc: doc["states"][2].update(initial="missing"),
            lambda doc: doc["states"][2].update(values=["standby", "standby"]),
            lambda doc: doc["states"][0].update(kind="float"),
            lambda doc: doc.update(format_version=True),
            lambda doc: doc["states"].append(dict(doc["states"][0])),
        )
        for mutate in cases:
            with self.subTest(mutate=mutate):
                pack_copy = PackCopy()
                try:
                    document = pack_copy.read("narrative_state.json")
                    mutate(document)
                    pack_copy.write("narrative_state.json", document)
                    with self.assertRaises(ContentValidationError):
                        load_content_pack(pack_copy.path)
                finally:
                    pack_copy.close()

    def test_typed_state_id_cannot_alias_a_legacy_flag(self) -> None:
        pack_copy = PackCopy()
        self.addCleanup(pack_copy.close)
        document = pack_copy.read("narrative_state.json")
        document["states"][0]["id"] = "flag_beacon_restored"
        pack_copy.write("narrative_state.json", document)

        with self.assertRaisesRegex(ContentValidationError, "legacy flag"):
            load_content_pack(pack_copy.path)


class NarrativeConditionContentTests(unittest.TestCase):
    @staticmethod
    def _restore_option(dialogues: object) -> dict:
        return dialogues[1]["nodes"][0]["options"][0]

    def test_original_demo_loads_the_bounded_condition_tree(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        option = pack.dialogues["dialogue_beacon_echo"].nodes[
            "node_beacon_greeting"
        ].options[0]

        self.assertIsInstance(option.condition, AllCondition)
        self.assertEqual(len(option.condition.conditions), 6)
        self.assertEqual(
            tuple(type(condition) for condition in option.condition.conditions),
            (
                StateEqualsCondition,
                StateCompareCondition,
                StateEqualsCondition,
                HasItemCondition,
                AtLocationCondition,
                QuestStatusCondition,
            ),
        )

    def test_invalid_condition_shape_reference_and_type_matrix_is_rejected(self) -> None:
        conditions = (
            {"kind": "state_equals", "state_id": "state_missing", "value": True},
            {"kind": "state_equals", "state_id": "state_beacon_enabled", "value": 1},
            {
                "kind": "state_compare",
                "state_id": "state_beacon_enabled",
                "operator": "gte",
                "value": 1,
            },
            {
                "kind": "state_compare",
                "state_id": "state_signal_strength",
                "operator": "eq",
                "value": 1,
            },
            {"kind": "has_item", "item_id": "item_missing", "quantity": 1},
            {"kind": "at_location", "location_id": "room_missing"},
            {"kind": "quest_status", "quest_id": "quest_missing", "status": "active"},
            {"kind": "quest_status", "quest_id": "quest_restore_beacon", "status": "done"},
            {"kind": "all", "conditions": []},
            {"kind": "not", "condition": None},
            {"kind": "script", "source": "return true"},
        )
        for condition in conditions:
            with self.subTest(condition=condition):
                pack_copy = PackCopy()
                try:
                    dialogues = pack_copy.read("dialogues.json")
                    self._restore_option(dialogues)["condition"] = condition
                    pack_copy.write("dialogues.json", dialogues)
                    with self.assertRaises(ContentValidationError):
                        load_content_pack(pack_copy.path)
                finally:
                    pack_copy.close()

    def test_every_nonterminal_node_requires_an_unconditional_fallback(self) -> None:
        pack_copy = PackCopy()
        self.addCleanup(pack_copy.close)
        dialogues = pack_copy.read("dialogues.json")
        options = dialogues[0]["nodes"][0]["options"]
        for option in options:
            option["condition"] = {
                "kind": "state_equals",
                "state_id": "state_beacon_enabled",
                "value": True,
            }
        pack_copy.write("dialogues.json", dialogues)

        with self.assertRaisesRegex(ContentValidationError, "无条件选项"):
            load_content_pack(pack_copy.path)

    def test_condition_depth_and_node_budgets_are_enforced(self) -> None:
        leaf: dict[str, object] = {
            "kind": "state_equals",
            "state_id": "state_beacon_enabled",
            "value": True,
        }
        deep = leaf
        for _ in range(17):
            deep = {"kind": "not", "condition": deep}
        wide = {"kind": "all", "conditions": [leaf] * 257}
        for condition, message in ((deep, "最大深度"), (wide, "最大节点数")):
            with self.subTest(message=message):
                pack_copy = PackCopy()
                try:
                    dialogues = pack_copy.read("dialogues.json")
                    self._restore_option(dialogues)["condition"] = condition
                    pack_copy.write("dialogues.json", dialogues)
                    with self.assertRaisesRegex(ContentValidationError, message):
                        load_content_pack(pack_copy.path)
                finally:
                    pack_copy.close()

    def test_schema_documents_expose_strict_state_and_condition_contracts(self) -> None:
        state_schema = json.loads(
            (PROJECT_ROOT / "schemas" / "narrative_state.schema.json").read_text("utf-8")
        )
        dialogue_schema = json.loads(
            (PROJECT_ROOT / "schemas" / "dialogue.schema.json").read_text("utf-8")
        )

        self.assertFalse(state_schema["additionalProperties"])
        self.assertEqual(state_schema["properties"]["format_version"]["const"], 1)
        self.assertEqual(len(state_schema["$defs"]["state_definition"]["oneOf"]), 3)
        option_properties = dialogue_schema["properties"]["nodes"]["items"][
            "properties"
        ]["options"]["items"]["properties"]
        self.assertEqual(
            option_properties["condition"]["$ref"],
            "#/$defs/narrative_condition",
        )
        self.assertEqual(len(dialogue_schema["$defs"]["narrative_condition"]["oneOf"]), 7)


class PureConditionEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {"state_bool": True, "state_int": 2, "state_enum": "ready"}
        self.inventory = {"item_key": 2}
        self.quests = {
            "quest_new": "not_accepted",
            "quest_active": "active",
            "quest_done": "completed",
        }
        self.context = ConditionContext(
            state_values=MappingProxyType(self.state),
            inventory_quantities=MappingProxyType(self.inventory),
            location_id="room_here",
            quest_statuses=MappingProxyType(self.quests),  # type: ignore[arg-type]
        )

    def test_leaf_and_logical_truth_table(self) -> None:
        true_conditions = (
            StateEqualsCondition("state_bool", True),
            StateEqualsCondition("state_enum", "ready"),
            StateCompareCondition("state_int", "gte", 2),
            HasItemCondition("item_key", 2),
            AtLocationCondition("room_here"),
            QuestStatusCondition("quest_done", "completed"),
            NotCondition(HasItemCondition("item_missing", 1)),
            AllCondition((StateEqualsCondition("state_bool", True), AtLocationCondition("room_here"))),
            AnyCondition((AtLocationCondition("room_elsewhere"), AtLocationCondition("room_here"))),
        )
        for condition in true_conditions:
            with self.subTest(condition=condition):
                self.assertTrue(evaluate_condition(condition, self.context))

        self.assertFalse(evaluate_condition(StateEqualsCondition("state_bool", 1), self.context))
        self.assertFalse(evaluate_condition(StateCompareCondition("state_int", "gt", 2), self.context))
        self.assertFalse(evaluate_condition(QuestStatusCondition("quest_active", "completed"), self.context))

    def test_short_circuit_and_context_immutability(self) -> None:
        self.assertTrue(
            evaluate_condition(
                AnyCondition(
                    (
                        AtLocationCondition("room_here"),
                        StateEqualsCondition("state_missing", True),
                    )
                ),
                self.context,
            )
        )
        self.assertFalse(
            evaluate_condition(
                AllCondition(
                    (
                        AtLocationCondition("room_elsewhere"),
                        StateEqualsCondition("state_missing", True),
                    )
                ),
                self.context,
            )
        )
        self.assertEqual(self.state, {"state_bool": True, "state_int": 2, "state_enum": "ready"})
        self.assertEqual(self.inventory, {"item_key": 2})
        self.assertEqual(self.quests["quest_done"], "completed")


class NarrativeConditionWorldTests(unittest.TestCase):
    def test_world_validates_typed_updates_and_recomputes_options(self) -> None:
        world = _beacon_world()

        visible = world.start_dialogue("character_beacon_echo")
        self.assertEqual(
            tuple(option.option_id for option in visible.options),
            ("opt_restore_beacon", "opt_beacon_bye"),
        )
        world.end_dialogue()

        world.set_narrative_state("state_beacon_enabled", False)
        filtered = world.start_dialogue("character_beacon_echo")
        self.assertEqual(
            tuple(option.option_id for option in filtered.options),
            ("opt_beacon_bye",),
        )
        active_before = world.active_dialogue
        with self.assertRaisesRegex(WorldRuleError, "无效的选项"):
            world.select_option(2)
        self.assertEqual(world.active_dialogue, active_before)
        ending = world.select_option(1)
        self.assertTrue(ending.ended)
        self.assertNotIn("flag_beacon_restored", world.flags)

    def test_world_rejects_unknown_wrong_type_and_out_of_range_values(self) -> None:
        world = _beacon_world()
        cases = (
            ("state_missing", True),
            ("state_beacon_enabled", 1),
            ("state_signal_strength", True),
            ("state_signal_strength", 4),
            ("state_station_mode", "missing"),
        )
        before = dict(world.narrative_state)
        for state_id, value in cases:
            with self.subTest(state_id=state_id, value=value):
                with self.assertRaises(WorldRuleError):
                    world.set_narrative_state(state_id, value)
                self.assertEqual(world.narrative_state, before)


class NarrativeStateSaveTests(unittest.TestCase):
    def test_v9_round_trip_preserves_strict_typed_state(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.set_narrative_state("state_beacon_enabled", False)
        world.set_narrative_state("state_signal_strength", 3)
        world.set_narrative_state("state_station_mode", "active")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            data = json.loads(service.save_path.read_text("utf-8"))
            loaded = service.load()

        self.assertEqual(SAVE_FORMAT_VERSION, 9)
        self.assertEqual(data["save_format_version"], 9)
        self.assertEqual(data["narrative_state"], world.narrative_state)
        self.assertEqual(loaded.narrative_state, world.narrative_state)

    def test_v8_rejects_state_key_type_range_and_enum_corruption(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        cases = (
            lambda state: state.pop("state_beacon_enabled"),
            lambda state: state.update(state_extra=True),
            lambda state: state.update(state_beacon_enabled=1),
            lambda state: state.update(state_signal_strength=True),
            lambda state: state.update(state_signal_strength=4),
            lambda state: state.update(state_station_mode="missing"),
        )
        for mutate in cases:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temp_dir:
                service = SaveLoadService(pack, Path(temp_dir))
                service.save(World.from_content_pack(pack))
                data = json.loads(service.save_path.read_text("utf-8"))
                mutate(data["narrative_state"])
                service.save_path.write_text(json.dumps(data), "utf-8")
                with self.assertRaises(SaveLoadError):
                    service.load()

    def test_v7_is_read_only_compatible_only_for_a_pack_without_state(self) -> None:
        stateful_pack = load_content_pack(DEMO_PATH)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(stateful_pack, Path(temp_dir))
            service.save(World.from_content_pack(stateful_pack))
            data = json.loads(service.save_path.read_text("utf-8"))
            data["save_format_version"] = LEGACY_SAVE_FORMAT_VERSION
            data.pop("narrative_state")
            for key in ("actors", "scene_states", "objective_states", "knowledge_states"):
                data.pop(key)
            service.save_path.write_text(json.dumps(data), "utf-8")
            with self.assertRaisesRegex(SaveLoadError, "save v7"):
                service.load()

        pack_copy = PackCopy()
        self.addCleanup(pack_copy.close)
        (pack_copy.path / "narrative_state.json").unlink()
        dialogues = pack_copy.read("dialogues.json")
        self._remove_restore_condition(dialogues)
        pack_copy.write("dialogues.json", dialogues)
        legacy_pack = load_content_pack(pack_copy.path)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(legacy_pack, Path(temp_dir))
            service.save(World.from_content_pack(legacy_pack))
            data = json.loads(service.save_path.read_text("utf-8"))
            data["save_format_version"] = LEGACY_SAVE_FORMAT_VERSION
            data.pop("narrative_state")
            for key in ("actors", "scene_states", "objective_states", "knowledge_states"):
                data.pop(key)
            service.save_path.write_text(json.dumps(data), "utf-8")

            loaded = service.load()
            service.save(loaded)
            rewritten = json.loads(service.save_path.read_text("utf-8"))

        self.assertEqual(loaded.narrative_state, {})
        self.assertEqual(rewritten["save_format_version"], SAVE_FORMAT_VERSION)
        self.assertEqual(rewritten["narrative_state"], {})

    @staticmethod
    def _remove_restore_condition(dialogues: object) -> None:
        dialogues[1]["nodes"][0]["options"][0].pop("condition")


class NarrativeConditionWebTests(unittest.TestCase):
    def test_web_uses_world_filtered_options_and_reindexes_them(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        with tempfile.TemporaryDirectory() as temp_dir:
            session = PlayerSession(pack, SaveLoadService(pack, Path(temp_dir)))
            session.world.player.room_id = "room_beacon_heart"
            session.world.player.inventory.stacks.append(ItemStack("item_beacon_core", 1))
            session.world.quest_states["quest_restore_beacon"] = QuestState(
                "quest_restore_beacon", completed=True
            )
            session.world.set_narrative_state("state_beacon_enabled", False)

            started = session.dispatch(
                {"type": "talk", "target": "character_beacon_echo"}
            )
            options = started["snapshot"]["dialogue"]["options"]
            self.assertEqual(
                options,
                [
                    {
                        "index": 1,
                        "id": "opt_beacon_bye",
                        "text": "先听一会儿回声。",
                        "intent": {"type": "choose_dialogue", "index": 1},
                    }
                ],
            )
            before = started["snapshot"]
            rejected = session.dispatch({"type": "choose_dialogue", "index": 2})
            self.assertFalse(rejected["ok"])
            self.assertEqual(rejected["snapshot"], before)
            ended = session.dispatch({"type": "choose_dialogue", "index": 1})

        self.assertTrue(ended["ok"])
        self.assertIsNone(ended["snapshot"]["dialogue"])


if __name__ == "__main__":
    unittest.main()
