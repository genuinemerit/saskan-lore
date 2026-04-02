# saskan_lore/utils/shell.py
"""Shell and system utilities: command execution, hashing, string helpers, system info."""

from __future__ import annotations

import hashlib
import inspect
import platform
import secrets
import subprocess
import traceback
from os import environ
from pathlib import Path


def run_cmd(cmd: str) -> tuple[bool, str]:
    """
    Execute a shell command and return (success, output).

    success is False if the command raises an exception or if the output
    contains the words 'failure' or 'fatal' (case-sensitive).
    """
    if not cmd:
        return False, ""
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output, _ = proc.communicate()
        success = not any(kw in output for kw in (b"failure", b"fatal"))
        return success, output.decode("utf-8").strip()
    except Exception as e:
        return False, str(e)


def get_hash(data_in: str) -> str:
    """Return a SHA-512 hex digest of the input string."""
    h = hashlib.sha512()
    h.update(data_in.encode("utf-8"))
    return h.hexdigest()


def get_sha256(data_in: str) -> str:
    """
    Return a SHA-256 hex digest of the input string.
    Used for DocumentRecord.content_hash to detect duplicate source files.
    """
    h = hashlib.sha256()
    h.update(data_in.encode("utf-8"))
    return h.hexdigest()


def get_uid(uid_length: int = 32) -> str:
    """
    Generate a URL-safe, cryptographically strong random string.
    Minimum length is 32 characters. Excludes shell-unsafe characters.
    """
    uid_length = max(uid_length, 32)
    exclude = {";", ":", "/", '"', "\\", "'", "?", "#", "|"}
    while True:
        uid_val = secrets.token_urlsafe(uid_length)
        if not any(char in uid_val for char in exclude):
            return uid_val


def get_host() -> str:
    """Return the hostname of the current machine."""
    return platform.node()


def get_platform() -> str:
    """Return a platform description string (OS, version, architecture)."""
    return platform.platform()


def get_os_home() -> str:
    """Return the OS home directory from the environment."""
    return environ.get("HOME", "")


def get_cwd_home() -> str:
    """Derive the home directory path from the current working directory."""
    parts = Path.cwd().parts
    return str(Path("/home") / parts[2]) if len(parts) > 2 else ""


def get_substring_exclusive(full_str: str, from_token: str, to_token: str) -> str:
    """
    Return the substring between from_token and to_token, exclusive of both tokens.
    Returns an empty string if either token is not found.
    """
    try:
        start = full_str.index(from_token) + len(from_token)
        end = full_str.index(to_token, start)
        return full_str[start:end]
    except ValueError:
        return ""


def get_substring_inclusive(full_str: str, from_token: str, to_token: str) -> str:
    """
    Return the substring between from_token and to_token, inclusive of both tokens.
    Returns an empty string if either token is not found.
    """
    try:
        start = full_str.index(from_token)
        end = full_str.index(to_token, start) + len(to_token)
        return full_str[start:end]
    except ValueError:
        return ""


def remove_dups(list_in: list) -> list:
    """Remove duplicates from a list, preserving original order."""
    return list(dict.fromkeys(list_in))


def show_trace(e: Exception) -> str:
    """Return a formatted exception traceback as a single string."""
    formatted = traceback.format_exception(type(e), e, e.__traceback__)
    return str(e) + "\n" + "".join(formatted)


def get_method_help(obj: object, method_name: str) -> str:
    """Return the docstring for a named method on an object or class."""
    method = getattr(obj, method_name, None)
    return inspect.getdoc(method) if method else f"Method '{method_name}' not found."


def continue_prompt() -> str:
    """Prompt the user to continue or stop. Loops until 'y' or 'n' is entered."""
    response = ""
    while response not in ("y", "n"):
        response = input("Continue? (y/n): ")
    return response
