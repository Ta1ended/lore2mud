"""Command-line entry point for lore2mud."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import World


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lore2mud",
        description="运行本地单人文字 MUD。",
    )
    parser.add_argument(
        "--content",
        type=Path,
        required=True,
        help="内容包目录，例如 examples/original_demo",
    )
    parser.add_argument(
        "--player-name",
        default="旅人",
        help="本地玩家显示名称（默认：旅人）",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path("saves"),
        help="存档目录（默认：saves）",
    )
    return parser


def run_game(world: World, save_service: SaveLoadService) -> int:
    processor = CommandProcessor(world, save_service=save_service)
    print(f"欢迎来到 {world.pack_name}。输入 help 查看指令。")
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pack = load_content_pack(args.content)
    except (OSError, ContentValidationError) as exc:
        parser.exit(2, f"内容包加载失败：{exc}\n")

    world = World.from_content_pack(pack, player_name=args.player_name)
    save_service = SaveLoadService(pack, args.save_dir)
    return run_game(world, save_service)


if __name__ == "__main__":
    raise SystemExit(main())
