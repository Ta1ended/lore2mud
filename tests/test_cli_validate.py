"""Tests for the lore2mud CLI — validate subcommand, legacy fallback, and
argument handling regressions."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS
from lore2mud.cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


# -- validate success --------------------------------------------------------


class ValidateSuccessTests(unittest.TestCase):
    """Validate exits 0 with the demo pack."""

    def test_demo_pack_exits_zero(self) -> None:
        exit_code = main(["validate", "--content", str(DEMO_PATH)])
        self.assertEqual(exit_code, 0)

    def test_demo_pack_prints_ok(self) -> None:
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            main(["validate", "--content", str(DEMO_PATH)])
        self.assertIn("[OK]", stdout.getvalue())
        self.assertIn("内容包校验通过", stdout.getvalue())

    def test_cli_reconfigures_legacy_output_streams_to_utf8(self) -> None:
        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="cp1252")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="cp1252")
        try:
            with (
                mock.patch("sys.stdout", stdout),
                mock.patch("sys.stderr", stderr),
                mock.patch("lore2mud.cli.sys.frozen", True, create=True),
            ):
                exit_code = main(["validate", "--content", str(DEMO_PATH)])
                stdout.flush()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.encoding, "utf-8")
            self.assertEqual(stderr.encoding, "utf-8")
            self.assertIn(
                "内容包校验通过",
                stdout_bytes.getvalue().decode("utf-8"),
            )
        finally:
            stdout.detach()
            stderr.detach()

    def test_embedded_cli_preserves_host_output_encoding(self) -> None:
        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="cp1252")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="cp1252")
        try:
            with (
                mock.patch.dict(os.environ, {"LORE2MUD_UTF8_IO": "0"}),
                mock.patch("sys.stdout", stdout),
                mock.patch("sys.stderr", stderr),
                mock.patch("lore2mud.cli.sys.frozen", False, create=True),
                mock.patch("lore2mud.web.server.serve"),
            ):
                exit_code = main(["web", "--content", str(DEMO_PATH)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.encoding, "cp1252")
            self.assertEqual(stderr.encoding, "cp1252")
        finally:
            stdout.detach()
            stderr.detach()

    def test_validate_does_not_start_game(self) -> None:
        """run_game must never be called during validation."""
        with mock.patch("lore2mud.cli.run_game") as mock_run:
            main(["validate", "--content", str(DEMO_PATH)])
        mock_run.assert_not_called()

    def test_validate_calls_validate_content_pack(self) -> None:
        """Must use the public validation entry point, not load_content_pack."""
        with mock.patch("lore2mud.cli.validate_content_pack") as mock_vcp:
            mock_vcp.return_value = ()
            main(["validate", "--content", str(DEMO_PATH)])
        mock_vcp.assert_called_once()


# -- validate content / encoding errors --------------------------------------


class ValidateContentErrorTests(unittest.TestCase):
    """Validate reports structural / reference errors and exits 1."""

    def test_directory_not_found_exits_one(self) -> None:
        exit_code = main(["validate", "--content", "/nonexistent_pack_dir"])
        self.assertEqual(exit_code, 1)

    def test_directory_not_found_unified_format(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            main(["validate", "--content", "/nonexistent_pack_dir"])
        output = stderr.getvalue()
        self.assertIn("[ERROR] 内容包校验失败:", output)
        self.assertIn("- ", output)

    def test_multiple_errors_all_reported(self) -> None:
        """Inject two distinct errors; both must appear in stderr."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "broken"
            shutil.copytree(DEMO_PATH, pack_path)

            # Error 1: dangling room exit
            rooms = json.loads(
                (pack_path / "rooms.json").read_text(encoding="utf-8")
            )
            rooms[0]["exits"]["north"] = "room_ghost"
            (pack_path / "rooms.json").write_text(
                json.dumps(rooms, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # Error 2: bad stable id on item
            items = json.loads(
                (pack_path / "items.json").read_text(encoding="utf-8")
            )
            items[0]["id"] = "Bad ID"
            (pack_path / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                exit_code = main(["validate", "--content", str(pack_path)])

            output = stderr.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("room_ghost", output)
            self.assertIn("稳定 ID", output)

    def test_missing_pack_json_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "empty"
            pack_path.mkdir()
            exit_code = main(["validate", "--content", str(pack_path)])
            self.assertEqual(exit_code, 1)


class ValidateEncodingErrorTests(unittest.TestCase):
    """Invalid UTF-8 in a JSON file must not produce a traceback."""

    def test_invalid_utf8_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "badenc"
            shutil.copytree(DEMO_PATH, pack_path)
            (pack_path / "pack.json").write_bytes(b"\x80\x81\xff\xfe")

            exit_code = main(["validate", "--content", str(pack_path)])
            self.assertEqual(exit_code, 1)

    def test_invalid_utf8_prints_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "badenc"
            shutil.copytree(DEMO_PATH, pack_path)
            (pack_path / "pack.json").write_bytes(b"\x80\x81\xff\xfe")

            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                main(["validate", "--content", str(pack_path)])

            output = stderr.getvalue()
            self.assertIn("[ERROR] 内容包校验失败:", output)
            self.assertIn("UTF-8", output)

    def test_json_resource_limits_exit_one_with_validation_diagnostics(self) -> None:
        limits = DEFAULT_JSON_READ_LIMITS
        cases = (
            (
                "huge_integer",
                b'{"value":' + b"9" * (limits.max_integer_digits + 1) + b"}",
            ),
            (
                "deep",
                b"[" * (limits.max_depth + 1)
                + b"0"
                + b"]" * (limits.max_depth + 1),
            ),
            ("many_nodes", b"[" + b"0," * limits.max_nodes + b"0]"),
            ("oversized", b" " * (limits.max_bytes + 1)),
        )
        for label, payload in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                pack_path = Path(temp_dir) / "hostile_pack"
                shutil.copytree(DEMO_PATH, pack_path)
                (pack_path / "pack.json").write_bytes(payload)
                stderr = io.StringIO()

                with mock.patch("sys.stderr", stderr):
                    exit_code = main(["validate", "--content", str(pack_path)])

                self.assertEqual(exit_code, 1)
                self.assertIn("[ERROR] 内容包校验失败:", stderr.getvalue())


class ValidateOSErrorTests(unittest.TestCase):
    """OSError during validation uses the unified error format."""

    def test_oserror_unified_format(self) -> None:
        """Simulate an OSError (e.g. permission denied) and verify format."""
        with mock.patch(
            "lore2mud.cli.validate_content_pack",
            side_effect=OSError("Permission denied"),
        ):
            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                exit_code = main(["validate", "--content", str(DEMO_PATH)])

        self.assertEqual(exit_code, 1)
        output = stderr.getvalue()
        self.assertIn("[ERROR] 内容包校验失败:", output)
        self.assertIn("Permission denied", output)


# -- legacy command backward compatibility ------------------------------------


class LegacyCommandTests(unittest.TestCase):
    """The old ``lore2mud --content <dir>`` form still enters play mode."""

    def test_legacy_enters_play(self) -> None:
        with (
            mock.patch("lore2mud.cli.run_game", return_value=0) as mock_run,
            mock.patch("lore2mud.cli.SaveLoadService"),
        ):
            main(["--content", str(DEMO_PATH)])
        mock_run.assert_called_once()

    def test_legacy_with_player_name(self) -> None:
        """``lore2mud --content <dir> --player-name 测试者`` works."""
        with (
            mock.patch("lore2mud.cli.run_game", return_value=0) as mock_run,
            mock.patch("lore2mud.cli.SaveLoadService"),
            mock.patch("lore2mud.cli.load_content_pack") as mock_load,
            mock.patch("lore2mud.cli.GameSession"),
        ):
            mock_load.return_value = mock.MagicMock()
            main(["--content", str(DEMO_PATH), "--player-name", "测试者"])
        mock_run.assert_called_once()

    def test_legacy_with_save_dir(self) -> None:
        """``lore2mud --content <dir> --save-dir custom-saves`` works."""
        with (
            mock.patch("lore2mud.cli.run_game", return_value=0) as mock_run,
            mock.patch("lore2mud.cli.SaveLoadService"),
            mock.patch("lore2mud.cli.load_content_pack") as mock_load,
            mock.patch("lore2mud.cli.GameSession"),
        ):
            mock_load.return_value = mock.MagicMock()
            main(["--content", str(DEMO_PATH), "--save-dir", "custom-saves"])
        mock_run.assert_called_once()

    def test_legacy_with_all_options(self) -> None:
        """All three legacy flags together."""
        with (
            mock.patch("lore2mud.cli.run_game", return_value=0) as mock_run,
            mock.patch("lore2mud.cli.SaveLoadService"),
            mock.patch("lore2mud.cli.load_content_pack") as mock_load,
            mock.patch("lore2mud.cli.GameSession"),
        ):
            mock_load.return_value = mock.MagicMock()
            main([
                "--content", str(DEMO_PATH),
                "--player-name", "测试者",
                "--save-dir", "custom-saves",
            ])
        mock_run.assert_called_once()

    def test_explicit_play_enters_play(self) -> None:
        with (
            mock.patch("lore2mud.cli.run_game", return_value=0) as mock_run,
            mock.patch("lore2mud.cli.SaveLoadService"),
        ):
            main(["play", "--content", str(DEMO_PATH)])
        mock_run.assert_called_once()

    def test_legacy_without_content_shows_help(self) -> None:
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            exit_code = main([])
        self.assertEqual(exit_code, 0)
        self.assertIn("play", stdout.getvalue())
        self.assertIn("validate", stdout.getvalue())


# -- unknown argument rejection (regression guard) ---------------------------


class UnknownArgumentTests(unittest.TestCase):
    """Unknown flags must always be rejected, never silently ignored."""

    def test_validate_unknown_flag_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["validate", "--content", str(DEMO_PATH), "--typo", "x"])
        self.assertEqual(caught.exception.code, 2)

    def test_play_unknown_flag_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["play", "--content", str(DEMO_PATH), "--typo", "x"])
        self.assertEqual(caught.exception.code, 2)

    def test_legacy_unknown_flag_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["--content", str(DEMO_PATH), "--typo", "x"])
        self.assertEqual(caught.exception.code, 2)


# -- argparse error handling --------------------------------------------------


class ArgparseErrorTests(unittest.TestCase):
    """Argparse-level misuse exits 2."""

    def test_play_missing_content_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["play"])
        self.assertEqual(caught.exception.code, 2)

    def test_validate_missing_content_exits_two(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["validate"])
        self.assertEqual(caught.exception.code, 2)

    def test_top_level_help_shows_both_subcommands(self) -> None:
        """``lore2mud -h`` prints help with both play and validate, exits 0."""
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with mock.patch("sys.stdout", stdout):
                main(["-h"])
        self.assertEqual(caught.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("play", output)
        self.assertIn("validate", output)


if __name__ == "__main__":
    unittest.main()
