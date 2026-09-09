"""Read and create prompt files (prompts/*.md).

Prompts are the text an agent is launched with. The UI lists them, reads them,
and creates new ones inline during an agent save. It never edits or deletes them.
"""
from __future__ import annotations

import datetime
import glob
import os
import re
import tempfile

import config

_FILENAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*\.md$")


class PromptValidationError(ValueError):
    """A prompt filename or content failed validation."""


def _prompts_dir() -> str:
    return config.PROMPTS_DIR


def _path(filename: str) -> str:
    return os.path.join(_prompts_dir(), filename)


def _iso(mtime: float) -> str:
    return datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_prompts() -> list[dict]:
    """Every prompt file with its size and UTC modified time, sorted by filename."""
    out = []
    for path in sorted(glob.glob(os.path.join(_prompts_dir(), "*.md"))):
        stat = os.stat(path)
        out.append({
            "filename": os.path.basename(path),
            "size": stat.st_size,
            "modified": _iso(stat.st_mtime),
        })
    return out


def prompt_names() -> list[str]:
    """Just the filenames, for the schema payload and prompt_file validation."""
    return [p["filename"] for p in list_prompts()]


def exists(filename: str) -> bool:
    if not filename or not _safe(filename):
        return False
    return os.path.isfile(_path(filename))


def read_prompt(filename: str) -> str:
    """The content of a prompt file. Raises FileNotFoundError if absent."""
    if not _safe(filename):
        raise PromptValidationError("invalid filename")
    with open(_path(filename), encoding="utf-8") as f:
        return f.read()


def _safe(filename: str) -> bool:
    """Reject path traversal and separators before touching the filesystem."""
    return not ("/" in filename or "\\" in filename or ".." in filename)


def create_prompt(filename: str, content: str) -> str:
    """Create a new prompt file, returning its final filename.

    Auto-appends ``.md``. Rejects traversal, invalid names, and empty content.
    Creates the prompts directory if missing. Raises FileExistsError on collision.
    """
    if not filename or not filename.strip():
        raise PromptValidationError("filename is required")
    filename = filename.strip()
    if not filename.endswith(".md"):
        filename += ".md"
    if not _safe(filename):
        raise PromptValidationError("filename must not contain / \\ or ..")
    if not _FILENAME_RE.match(filename):
        raise PromptValidationError(
            "filename must be lowercase letters/digits, then letters/digits/._-, ending in .md"
        )
    if content is None or content.strip() == "":
        raise PromptValidationError("prompt content must not be empty")

    directory = _prompts_dir()
    os.makedirs(directory, exist_ok=True)
    path = _path(filename)
    if os.path.exists(path):
        raise FileExistsError(f"prompts/{filename} already exists")

    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{filename}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        # exclusive create guards against a race between the check above and rename
        os.link(tmp, path)
    except FileExistsError:
        os.remove(tmp)
        raise FileExistsError(f"prompts/{filename} already exists")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return filename
