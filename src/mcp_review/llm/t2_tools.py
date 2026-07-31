"""T2 tool primitives: list_files, read_file, grep_repo.

The minimal set Claude needs to gather cross-file evidence (token passthrough,
confused-deputy, roots-boundary enforcement, etc.) instead of judging from a diff
alone — mirrors the read/glob/grep primitives a coding agent normally gets.

Every path is resolved against a fixed repo root and verified not to escape it before
use. This is the same discipline checklist item #9 (unvalidated resource URIs) exists to
catch — this code had better not violate it itself.
"""

from __future__ import annotations

import re
from pathlib import Path

_MAX_FILE_CHARS = 50_000
_MAX_GREP_MATCHES = 60
_MAX_FILES_LISTED = 500


def _resolve_within_root(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


class T2ToolSet:
    """Binds list_files/read_file/grep_repo to one repo checkout."""

    def __init__(self, repo_root: Path):
        self._root = repo_root.resolve()

    def list_files(self, glob: str = "**/*") -> str:
        matches = sorted(str(p.relative_to(self._root)) for p in self._root.glob(glob) if p.is_file())
        return "\n".join(matches[:_MAX_FILES_LISTED]) or "(no files matched)"

    def read_file(self, path: str) -> str:
        resolved = _resolve_within_root(self._root, path)
        if resolved is None:
            return f"Error: {path!r} is outside the repository root."
        if not resolved.is_file():
            return f"Error: {path!r} is not a file."
        content = resolved.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_FILE_CHARS:
            content = content[:_MAX_FILE_CHARS] + "\n... (truncated)"
        return content

    def grep_repo(self, pattern: str, glob: str = "**/*") -> str:
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return f"Error: invalid regex: {exc}"

        results: list[str] = []
        for file_path in self._root.glob(glob):
            if not file_path.is_file():
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    rel = file_path.relative_to(self._root)
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= _MAX_GREP_MATCHES:
                        return "\n".join(results)
        return "\n".join(results) or "(no matches)"

    def dispatch(self, name: str, tool_input: dict) -> str:
        if name == "list_files":
            return self.list_files(**tool_input)
        if name == "read_file":
            return self.read_file(**tool_input)
        if name == "grep_repo":
            return self.grep_repo(**tool_input)
        return f"Error: unknown tool {name!r}"

    @staticmethod
    def tool_schemas() -> list[dict]:
        return [
            {
                "name": "list_files",
                "description": "List files in the repository matching a glob pattern.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "glob": {
                            "type": "string",
                            "description": "Glob pattern relative to the repo root, e.g. '**/*.py'. Defaults to all files.",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "read_file",
                "description": "Read the full contents of one file in the repository.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to the repository root.",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "grep_repo",
                "description": "Search for a regex pattern across files in the repository.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression to search for.",
                        },
                        "glob": {
                            "type": "string",
                            "description": "Glob pattern restricting which files are searched. Defaults to all files.",
                        },
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            },
        ]
