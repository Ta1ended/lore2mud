from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import (
    ContentValidationError,
    load_content_pack,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class ContentLoaderTests(unittest.TestCase):
    def test_original_demo_loads(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(pack.id, "original_demo")
        self.assertEqual(pack.version, "0.10.0")
        self.assertEqual(len(pack.rooms), 9)
        self.assertEqual(len(pack.monsters), 4)
        self.assertEqual(len(pack.quests), 8)
        self.assertEqual(len(pack.items), 8)
        self.assertEqual(len(pack.characters), 2)
        self.assertEqual(len(pack.dialogues), 2)
        self.assertIn("item_ash_mite_gel", pack.items)
        self.assertIn("monster_spark_hound", pack.monsters)
        self.assertIn("monster_mist_crawler", pack.monsters)
        self.assertIn("monster_prism_sentinel", pack.monsters)
        self.assertIn("quest_clear_spark_hound", pack.quests)
        self.assertIn("quest_clear_mist_crawler", pack.quests)
        self.assertIn("quest_clear_prism_sentinel", pack.quests)
        self.assertIn("quest_restore_beacon", pack.quests)
        self.assertIn("room_beacon_heart", pack.rooms)
        self.assertIn("item_beacon_core", pack.items)
        self.assertEqual(pack.start_room_id, "room_ember_wharf")

    def test_dangling_room_exit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "broken_pack"
            shutil.copytree(DEMO_PATH, pack_path)
            rooms_path = pack_path / "rooms.json"
            rooms = json.loads(rooms_path.read_text(encoding="utf-8"))
            rooms[0]["exits"]["north"] = "room_missing"
            rooms_path.write_text(
                json.dumps(rooms, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)
            self.assertIn("room_missing", str(caught.exception))
            self.assertIn("不存在的房间", str(caught.exception))

    def test_invalid_stable_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "broken_pack"
            shutil.copytree(DEMO_PATH, pack_path)
            items_path = pack_path / "items.json"
            items = json.loads(items_path.read_text(encoding="utf-8"))
            items[0]["id"] = "Bad Display Name"
            items_path.write_text(
                json.dumps(items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)
            self.assertIn("稳定 ID", str(caught.exception))

    def test_missing_required_number_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "broken_pack"
            shutil.copytree(DEMO_PATH, pack_path)
            monsters_path = pack_path / "monsters.json"
            monsters = json.loads(
                monsters_path.read_text(encoding="utf-8")
            )
            del monsters[0]["attack"]
            monsters_path.write_text(
                json.dumps(monsters, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)
            self.assertIn("attack 是必填字段", str(caught.exception))

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "broken_pack"
            shutil.copytree(DEMO_PATH, pack_path)
            items_path = pack_path / "items.json"
            items = json.loads(items_path.read_text(encoding="utf-8"))
            items[0]["model_guess"] = "untrusted"
            items_path.write_text(
                json.dumps(items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)
            self.assertIn("未知字段", str(caught.exception))

    def test_schema_documents_are_valid_json(self) -> None:
        schema_dir = PROJECT_ROOT / "schemas"
        schema_files = list(schema_dir.glob("*.schema.json"))
        self.assertGreaterEqual(len(schema_files), 6)
        for schema_file in schema_files:
            with self.subTest(schema=schema_file.name):
                data = json.loads(schema_file.read_text(encoding="utf-8"))
                self.assertIn("$schema", data)
                self.assertIn("title", data)


if __name__ == "__main__":
    unittest.main()
