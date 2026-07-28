"""Reject private material, likely credentials, unsafe files, and unsafe Git history.

This is a deliberately limited repository guard, not a replacement for a secret
manager or a rights review.  It scans commit candidates (including files that
were force-added despite ``.gitignore``) and, with ``--history``, every
reachable Git tree and blob.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_MAX_SIZE = 2 * 1024 * 1024
FORBIDDEN_DIRECTORY_PREFIXES = (
    "novel/raw",
    "novel/chapters",
    "novel/summaries",
    "novel/canon",
    "novel/extractions",
    "private_novels",
    "private_content",
    "generated_content",
    "saves",
    "logs",
    "models",
    "vector_store",
    "rag_index",
    "faiss_index",
    "chroma",
)
FORBIDDEN_EXTENSIONS = {
    ".epub",
    ".mobi",
    ".azw",
    ".azw3",
    ".pdf",
    ".key",
    ".pem",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
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
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "私钥",
        re.compile(br"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    ),
    (
        "GitHub 令牌",
        re.compile(br"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "AWS 访问密钥 ID",
        re.compile(br"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "AWS 密钥配置",
        re.compile(
            br"(?im)^\s*aws_secret_access_key\s*[:=]\s*[^\s#]{40}"
        ),
    ),
    (
        "Slack 令牌",
        re.compile(br"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
)


@dataclass(frozen=True, slots=True)
class SafetyViolation:
    path: str
    reason: str


def normalize_relative_path(path: Path | PurePosixPath) -> str:
    return PurePosixPath(*path.parts).as_posix()


def _path_violations(
    normalized: str,
    *,
    size: int | None,
    max_size: int,
) -> list[SafetyViolation]:
    lowered = normalized.casefold()
    violations: list[SafetyViolation] = []
    for prefix in FORBIDDEN_DIRECTORY_PREFIXES:
        if lowered == prefix or lowered.startswith(f"{prefix}/"):
            violations.append(SafetyViolation(normalized, f"禁止提交私有内容目录 {prefix}"))
            break
    if lowered.startswith("content_packs/private_"):
        violations.append(SafetyViolation(normalized, "禁止提交 private_ 内容包"))
    if lowered.startswith("config/local."):
        violations.append(SafetyViolation(normalized, "禁止提交本地配置文件"))

    suffix = PurePosixPath(normalized).suffix.casefold()
    if suffix in FORBIDDEN_EXTENSIONS:
        violations.append(SafetyViolation(normalized, f"禁止提交文件类型 {suffix}"))

    name = PurePosixPath(normalized).name.casefold()
    if name == ".env" or name.startswith(".env."):
        violations.append(SafetyViolation(normalized, "禁止提交环境变量或密钥文件"))
    if size is not None and size > max_size:
        violations.append(
            SafetyViolation(
                normalized,
                f"文件大小 {size} 字节超过限制 {max_size} 字节",
            )
        )
    return violations


def _content_violations(normalized: str, content: bytes) -> list[SafetyViolation]:
    return [
        SafetyViolation(normalized, f"检测到疑似{label}模式")
        for label, pattern in SECRET_PATTERNS
        if pattern.search(content)
    ]


def inspect_candidate(
    root: Path,
    relative_path: Path,
    *,
    max_size: int = DEFAULT_MAX_SIZE,
) -> list[SafetyViolation]:
    """Inspect one current filesystem candidate without exposing its content."""
    normalized = normalize_relative_path(relative_path)
    absolute_path = root / relative_path
    try:
        size = absolute_path.stat().st_size
    except OSError as exc:
        return [SafetyViolation(normalized, f"无法读取文件元数据：{exc}")]

    violations = _path_violations(normalized, size=size, max_size=max_size)
    if size > max_size:
        return violations
    try:
        violations.extend(_content_violations(normalized, absolute_path.read_bytes()))
    except OSError as exc:
        violations.append(SafetyViolation(normalized, f"无法读取文件内容：{exc}"))
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
            name for name in dirnames if name not in FALLBACK_EXCLUDED_DIRECTORIES
        ]
        current = Path(current_root)
        for filename in filenames:
            yield (current / filename).relative_to(root)


def find_candidates(root: Path) -> list[Path]:
    """Return tracked and non-ignored candidates; force-added files are tracked."""
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
        violations.extend(inspect_candidate(root, relative_path, max_size=max_size))
    return violations


def _run_git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _history_entries(root: Path) -> Iterable[tuple[str, str, int]]:
    commits = _run_git(root, ["rev-list", "--all"]).stdout.splitlines()
    for raw_commit in commits:
        commit = raw_commit.decode("ascii")
        tree = _run_git(root, ["ls-tree", "-r", "-z", "-l", commit]).stdout
        for raw_entry in tree.split(b"\0"):
            if not raw_entry:
                continue
            metadata, separator, raw_path = raw_entry.partition(b"\t")
            if not separator:
                continue
            mode, object_type, object_id, raw_size = metadata.split(b" ", 3)
            del mode
            if object_type != b"blob":
                continue
            yield (
                object_id.decode("ascii"),
                raw_path.decode("utf-8", errors="surrogateescape"),
                int(raw_size),
            )


def scan_history(root: Path, *, max_size: int = DEFAULT_MAX_SIZE) -> list[SafetyViolation]:
    """Scan every path and blob reachable from every local Git ref."""
    root = root.resolve()
    if not (root / ".git").exists():
        return [SafetyViolation(".", "无法扫描 Git 历史：目录不是 Git 仓库")]
    violations: list[SafetyViolation] = []
    scanned_blobs: set[str] = set()
    try:
        for object_id, raw_path, size in _history_entries(root):
            normalized = normalize_relative_path(PurePosixPath(raw_path))
            violations.extend(
                _path_violations(normalized, size=size, max_size=max_size)
            )
            if object_id in scanned_blobs or size > max_size:
                continue
            scanned_blobs.add(object_id)
            content = _run_git(root, ["cat-file", "blob", object_id]).stdout
            violations.extend(_content_violations(normalized, content))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        violations.append(SafetyViolation(".", f"无法扫描 Git 历史：{exc}"))
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
    parser.add_argument(
        "--history",
        action="store_true",
        help="扫描所有可达 Git 历史树和 blob",
    )
    args = parser.parse_args(argv)
    violations = scan_repository(args.root, max_size=args.max_size)
    if args.history:
        violations.extend(scan_history(args.root, max_size=args.max_size))
    if violations:
        print("仓库安全检查失败：")
        for violation in violations:
            print(f"- {violation.path}: {violation.reason}")
        return 1
    print("仓库安全检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
