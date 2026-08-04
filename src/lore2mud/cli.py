"""Command-line entry point for lore2mud."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from lore2mud.application.session import GameSession
from lore2mud.content.loader import (
    ContentValidationError,
    load_content_pack,
    validate_content_pack,
)
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService


def _configure_output_encoding() -> None:
    """Keep Unicode CLI output stable under frozen and redirected runtimes."""
    if not getattr(sys, "frozen", False) and os.environ.get("LORE2MUD_UTF8_IO") != "1":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def run_game(session: GameSession) -> int:
    """Start the interactive game loop."""
    processor = CommandProcessor.from_session(session)
    print(f"欢迎来到 {session.world.pack_name}。输入 help 查看指令。")
    print(processor.execute("look").text)

    while True:
        try:
            command = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\n游戏结束。")
            return 0

        result = processor.execute(command)
        if result.text:
            print(result.text)
        if result.should_quit:
            return 0


# -- Command handlers --------------------------------------------------------


def _cmd_play(args: argparse.Namespace) -> int:
    """Load a content pack and start the game."""
    try:
        pack = load_content_pack(args.content)
    except (OSError, ContentValidationError) as exc:
        raise SystemExit(2, f"内容包加载失败：{exc}\n") from None

    save_service = SaveLoadService(pack, args.save_dir)
    session = GameSession.from_content_pack(
        pack,
        save_service,
        player_name=args.player_name,
    )
    return run_game(session)


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate a content pack without starting the game."""
    try:
        validate_content_pack(args.content)
    except ContentValidationError as exc:
        print("[ERROR] 内容包校验失败:", file=sys.stderr)
        for issue in exc.issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    except OSError as exc:
        print("[ERROR] 内容包校验失败:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1

    print(f"[OK] 内容包校验通过: {args.content}")
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    """Start the local browser player on an explicit bind address."""
    from lore2mud.web.server import LocalPlayerConfigurationError, serve

    try:
        serve(
            args.content,
            args.save_dir,
            player_name=args.player_name,
            host=args.host,
            port=args.port,
        )
    except (OSError, ContentValidationError, LocalPlayerConfigurationError) as exc:
        print(f"[ERROR] 本地界面启动失败：{exc}", file=sys.stderr)
        return 1
    return 0


# -- Parser ------------------------------------------------------------------

_COMMANDS = frozenset({"play", "validate", "web"})


def _port_number(value: str) -> int:
    """Parse one valid TCP port without argparse listing 65k choices."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("端口必须是 1-65535 的整数") from exc
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError("端口必须是 1-65535 的整数")
    return port


def _inject_legacy_subcommand(argv: list[str]) -> list[str]:
    """If *argv* has no recognised subcommand, prepend ``"play"`` and move
    it before the first flag so that ``parse_args`` sees ``[play, --content,
    ...]`` instead of ``[--content, dir, play, ...]`` (which fails because
    argparse interprets ``dir`` as the positional subcommand value).

    Returns a **new** list; *argv* is not mutated.
    """
    # Help flags should reach the top-level parser directly.
    if argv and argv[0] in ("-h", "--help"):
        return list(argv)

    # Detect whether a recognised subcommand is already present.
    skip_next = False
    has_command = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            if token in ("--content", "--player-name", "--save-dir"):
                skip_next = True
            continue
        # First positional token.
        if token in _COMMANDS:
            has_command = True
        break

    if has_command or not argv:
        return list(argv)

    # Legacy invocation — put "play" at the front so it is consumed as the
    # subcommand before any flags are processed.
    return ["play", *argv]


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with play, validate, and web subcommands."""
    parser = argparse.ArgumentParser(
        prog="lore2mud",
        description="本地单人文字 MUD 引擎。",
    )

    subparsers = parser.add_subparsers(dest="command")

    # -- play subcommand --
    play_parser = subparsers.add_parser(
        "play",
        help="加载内容包并启动游戏",
    )
    play_parser.add_argument(
        "--content",
        type=Path,
        required=True,
        help="内容包目录，例如 examples/original_demo",
    )
    play_parser.add_argument(
        "--player-name",
        default="旅人",
        help="本地玩家显示名称（默认：旅人）",
    )
    play_parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path("saves"),
        help="存档目录（默认：saves）",
    )
    play_parser.set_defaults(func=_cmd_play)

    # -- validate subcommand --
    validate_parser = subparsers.add_parser(
        "validate",
        help="校验内容包（不启动游戏）",
    )
    validate_parser.add_argument(
        "--content",
        type=Path,
        required=True,
        help="要校验的内容包目录",
    )
    validate_parser.set_defaults(func=_cmd_validate)

    # -- web subcommand --
    web_parser = subparsers.add_parser(
        "web",
        help="启动本地浏览器界面",
    )
    web_parser.add_argument(
        "--content",
        type=Path,
        required=True,
        help="内容包目录，例如 examples/original_demo",
    )
    web_parser.add_argument(
        "--player-name",
        default="旅人",
        help="本地玩家显示名称（默认：旅人）",
    )
    web_parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path("saves"),
        help="存档目录（默认：saves）",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址（默认仅本机：127.0.0.1）",
    )
    web_parser.add_argument(
        "--port",
        type=_port_number,
        default=8765,
        metavar="1-65535",
        help="监听端口（默认：8765）",
    )
    web_parser.set_defaults(func=_cmd_web)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the lore2mud CLI."""
    _configure_output_encoding()
    raw = list(argv) if argv is not None else sys.argv[1:]
    effective = _inject_legacy_subcommand(raw)

    parser = _build_parser()

    # parse_args (not parse_known_args) — unknown flags always fail.
    args = parser.parse_args(effective)

    if hasattr(args, "func"):
        return args.func(args)

    # ``lore2mud`` with no arguments → show help.
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
