# saskan_lore/tools/utils/file_io.py
"""File I/O utilities for reading, writing, and managing files and directories."""

from __future__ import annotations

import difflib
import json
import shutil
from os import makedirs, remove, symlink
from pathlib import Path


def is_file_or_dir(path: str) -> bool:
    """Return True if the path exists (file or directory)."""
    return Path(path).exists()


def scan_dir(dir_path: str, file_pattern: str = "") -> list[Path]:
    """
    Return a sorted list of Path objects in dir_path matching file_pattern.
    Use '*' as a wildcard in file_pattern (e.g. '*.txt', 'chunk_*').
    Returns an empty list if the directory does not exist.
    """
    parts = file_pattern.split("*") if file_pattern else [""]
    try:
        p = Path(dir_path)
        if p.exists() and p.is_dir():
            return sorted(f for f in p.iterdir() if all(s in f.name for s in parts))
    except Exception as err:
        raise err
    return []


def get_dir(path: str) -> list[str] | None:
    """Return directory contents as a list of strings, or None if not found."""
    try:
        p = Path(path)
        if p.exists() and p.is_dir():
            return [str(f) for f in p.iterdir()]
    except Exception as err:
        raise err
    return None


def get_absolute_path(path: str) -> str:
    """Return the absolute path as a string."""
    return str(Path(path).resolve())


def read_file(path: str) -> str:
    """Read and return the full contents of a text file (stripped)."""
    return Path(path).resolve().read_text(encoding="utf-8").strip()


def read_json_file(path: str) -> dict:
    """Read a JSON file and return its contents as a dict."""
    return json.loads(read_file(path))


def make_dir(path: str) -> None:
    """Create a directory (and any missing parents). No-op if it already exists."""
    makedirs(path, exist_ok=True)


def write_file(path: str, data: str, mode: str = "w") -> None:
    """Write text data to a file. Default mode overwrites; use 'a' to append."""
    try:
        with open(path, mode, encoding="utf-8") as f:
            f.write(data)
    except Exception as err:
        raise Exception(f"Error writing {path}: {err}") from err


def append_file(path: str, text: str) -> None:
    """Append text to a file."""
    write_file(path, text, mode="a")


def write_json_file(path: str, data: dict) -> None:
    """Write a dict to a file as formatted JSON."""
    write_file(path, json.dumps(data, indent=2, ensure_ascii=False))


def delete_file(path: str) -> None:
    """Delete a file."""
    remove(path)


def copy_file(path_from: str, path_to: str) -> None:
    """Copy a single file, preserving metadata."""
    shutil.copy2(path_from, path_to)


def copy_dir(path_from: str, path_to: str) -> None:
    """Recursively copy a directory tree to a destination."""
    shutil.copytree(path_from, path_to, dirs_exist_ok=True)


def rename_file(path: str, new_name: str) -> None:
    """Rename a file, preserving its extension."""
    p = Path(path).resolve()
    p.rename(p.parent / f"{new_name}{p.suffix}")


def make_link(link_from: str, link_to: str) -> None:
    """Create a symbolic link at link_to pointing to link_from."""
    symlink(link_from, link_to)


def diff_files(file_a: str, file_b: str) -> str:
    """Return a unified diff of two text files as a string."""
    text_a = Path(file_a).read_text(encoding="utf-8").splitlines(keepends=True)
    text_b = Path(file_b).read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(text_a, text_b, fromfile=file_a, tofile=file_b))
