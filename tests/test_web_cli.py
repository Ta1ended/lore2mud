"""CLI and package-data integration tests for the local Web player."""

from __future__ import annotations

import io
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from lore2mud.cli import _inject_legacy_subcommand, main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class WebCommandTests(unittest.TestCase):
    def test_web_dispatches_all_server_arguments(self) -> None:
        with mock.patch("lore2mud.web.server.serve") as serve:
            exit_code = main([
                "web",
                "--content", str(DEMO_PATH),
                "--save-dir", "local-saves",
                "--player-name", "界面旅人",
                "--host", "127.0.0.1",
                "--port", "9988",
            ])

        self.assertEqual(exit_code, 0)
        serve.assert_called_once_with(
            DEMO_PATH,
            Path("local-saves"),
            player_name="界面旅人",
            host="127.0.0.1",
            port=9988,
        )

    def test_web_defaults_to_loopback(self) -> None:
        with mock.patch("lore2mud.web.server.serve") as serve:
            main(["web", "--content", str(DEMO_PATH)])

        self.assertEqual(serve.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(serve.call_args.kwargs["port"], 8765)

    def test_web_startup_error_is_reported_without_traceback(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch("lore2mud.web.server.serve", side_effect=OSError("busy")),
            mock.patch("sys.stderr", stderr),
        ):
            exit_code = main(["web", "--content", str(DEMO_PATH)])

        self.assertEqual(exit_code, 1)
        self.assertIn("本地界面启动失败", stderr.getvalue())
        self.assertIn("busy", stderr.getvalue())

    def test_web_rejects_invalid_port(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["web", "--content", str(DEMO_PATH), "--port", "70000"])
        self.assertEqual(caught.exception.code, 2)

    def test_explicit_web_is_not_rewritten_to_legacy_play(self) -> None:
        arguments = ["web", "--content", str(DEMO_PATH)]
        self.assertEqual(_inject_legacy_subcommand(arguments), arguments)

    def test_legacy_play_arguments_remain_compatible(self) -> None:
        arguments = ["--content", str(DEMO_PATH), "--save-dir", "saves"]
        self.assertEqual(
            _inject_legacy_subcommand(arguments),
            ["play", *arguments],
        )

    def test_top_level_help_lists_all_three_commands(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as caught:
            with mock.patch("sys.stdout", stdout):
                main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        for command in ("play", "validate", "web"):
            self.assertIn(command, stdout.getvalue())


class WebPackageDataTests(unittest.TestCase):
    def test_pyproject_includes_every_static_asset_kind(self) -> None:
        project = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = project["tool"]["setuptools"]["package-data"]["lore2mud.web"]
        self.assertEqual(
            patterns,
            ["static/*.html", "static/*.css", "static/*.js"],
        )

        static_root = PROJECT_ROOT / "src" / "lore2mud" / "web" / "static"
        for filename in ("index.html", "styles.css", "app.js"):
            self.assertTrue((static_root / filename).is_file())


if __name__ == "__main__":
    unittest.main()
