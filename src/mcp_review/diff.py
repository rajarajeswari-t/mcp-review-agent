"""Fetches PR data from GitHub via the `gh` CLI.

Kept separate from the engine so the engine itself only deals with already-fetched
diff text + file contents and stays unit-testable without shelling out to `gh`.
"""

from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit

from mcp_review.static_rules.base import SourceFile

# MCP servers are commonly implemented in these languages; T0 rules only know how to
# scan these extensions.
_SOURCE_EXTENSIONS = (".py", ".js", ".ts", ".mjs", ".cjs")


@dataclass(frozen=True)
class PullRequestRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def _run_gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return result.stdout


def fetch_pr_diff(pr: PullRequestRef) -> str:
    """Full unified diff text for the PR — the T1 Claude review's context."""
    return _run_gh(["pr", "diff", str(pr.number), "--repo", pr.slug])


def fetch_changed_source_files(pr: PullRequestRef) -> list[SourceFile]:
    """Full content (not just the diff hunk) of each changed file worth static-scanning.

    T0 rules need full-file context (e.g. "is there an Origin check anywhere in this
    file"), which a diff hunk alone can't answer.
    """
    raw = _run_gh(["api", f"repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/files", "--paginate"])
    entries = json.loads(raw)

    files: list[SourceFile] = []
    for entry in entries:
        filename = entry["filename"]
        if entry.get("status") == "removed":
            continue
        if not filename.endswith(_SOURCE_EXTENSIONS):
            continue

        content = _fetch_file_content(entry["contents_url"])
        if content is not None:
            files.append(SourceFile(path=filename, content=content))

    return files


def _fetch_file_content(contents_url: str) -> str | None:
    split = urlsplit(contents_url)
    endpoint = split.path.lstrip("/")
    if split.query:
        endpoint = f"{endpoint}?{split.query}"

    raw = _run_gh(["api", endpoint, "--jq", ".content"]).strip()
    if not raw:
        return None

    decoded = base64.b64decode(raw.replace("\n", ""))
    return decoded.decode("utf-8", errors="replace")
