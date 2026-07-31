"""Shallow-clones a PR's head ref into a temp directory.

T0/T1 only ever need the diff and the changed files' content, fetched over the GitHub
API. T2 needs to read *arbitrary* files in the repo to trace evidence across files —
that's what a real local checkout is for. Uses head.repo.clone_url (not the base repo)
so this also works correctly for PRs from forks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from mcp_review.diff import PullRequestRef
from mcp_review.gh import run_gh


@contextmanager
def clone_pr_head(pr: PullRequestRef) -> Iterator[Path]:
    raw = run_gh(["api", f"repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"])
    payload = json.loads(raw)
    clone_url = payload["head"]["repo"]["clone_url"]
    ref = payload["head"]["ref"]

    tmpdir = Path(tempfile.mkdtemp(prefix="mcp-review-"))
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", ref, clone_url, str(tmpdir)],
            check=True,
            capture_output=True,
            text=True,
        )
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
