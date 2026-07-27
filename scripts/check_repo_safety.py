"""Reject private novel material, secrets, ebooks, and oversized files."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_MAX_SIZE = 2 * 1024 * 1024
FORBIDDEN_DIRECTORY_PREFIXES = (
    "novel/raw",
    "novel/chapters",
    "private_novels",
    "private_content",
    "generated_content",
)
FORBIDDEN_EXTENSIONS = {
    ".epub",
    ".mobi",
    ".azw",
    ".azw3",
    ".pdf",
    ".key",
    ".pem",
}
FALLBACK_EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
}


@dataclass(frozen=True, slots=True)
class SafetyViolation:
    path: str
    reason: str


def normalize_relative_path(path: Path) -> str:
    return PurePosixPath(*path.parts).as_posix()


def inspect_candidate(
    root: Path,
    relative_path: Path,
    *,
    max_size: int = DEFAULT_MAX_SIZE,
) -> list[SafetyViolation]:
    normalized = normalize_relative_path(relative_path)
    lowered = normalized.casefold()
    violations: list[SafetyViolation] = []

    for prefix in FORBIDDEN_DIRECTORY_PREFIXES:
        if lowered == prefix or lowered.startswith(f"{prefix}/"):
            violations.append(
                SafetyViolation(normalized, f"禁止提交私有内容目录 {prefix}")
            )
            break
    if lowered.startswith("content_packs/private_"):
        violations.append(
            SafetyViolation(normalized, "禁止提交 private_ 内容包")
        )

    suffix = relative_path.suffix.casefold()
    if suffix in FORBIDDEN_EXTENSIONS:
        violations.append(
            SafetyViolation(normalized, f"禁止提交文件类型 {suffix}")
        )

    name = relative_path.name.casefold()
    if name == ".env" or name.startswith(".env."):
        violations.append(
            SafetyViolation(normalized, "禁止提交环境变量或密钥文件")
        )

    absolute_path = root / relative_path
    try:
        size = absolute_path.stat().st_size
    except OSError as exc:
        violations.append(
            SafetyViolation(normalized, f"无法读取文件元数据：{exc}")
        )
    else:
        if size > max_size:
            violations.append(
                SafetyViolation(
                    normalized,
                    f"文件大小 {size} 字节超过限制 {max_size} 字节",
                )
            )
    return violations


def _git_candidates(root: Path) -> list[Path] | None:
    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    raw_paths = completed.stdout.decode("utf-8", errors="surrogateescape")
    return [
        Path(entry)
        for entry in raw_paths.split("\0")
        if entry and (root / entry).is_file()
    ]


def _filesystem_candidates(root: Path) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in FALLBACK_EXCLUDED_DIRECTORIES
        ]
        current = Path(current_root)
        for filename in filenames:
            yield (current / filename).relative_to(root)


def find_candidates(root: Path) -> list[Path]:
    git_paths = _git_candidates(root)
    if git_paths is not None:
        return git_paths
    return list(_filesystem_candidates(root))


def scan_repository(
    root: Path,
    *,
    max_size: int = DEFAULT_MAX_SIZE,
    candidates: Iterable[Path] | None = None,
) -> list[SafetyViolation]:
    root = root.resolve()
    selected = list(candidates) if candidates is not None else find_candidates(root)
    violations: list[SafetyViolation] = []
    for relative_path in selected:
        violations.extend(
            inspect_candidate(root, relative_path, max_size=max_size)
        )
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="仓库根目录（默认当前目录）",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_SIZE,
        help=f"单文件最大字节数（默认 {DEFAULT_MAX_SIZE}）",
    )
    args = parser.parse_args(argv)
    violations = scan_repository(args.root, max_size=args.max_size)
    if violations:
        print("仓库安全检查失败：")
        for violation in violations:
            print(f"- {violation.path}: {violation.reason}")
        return 1
    print("仓库安全检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
