"""Orchestrates one full review run: T0 static rules + T1 Claude pass + optional T2
agentic pass, merged.

Takes already-fetched diff text and file contents rather than a PR reference, so it
stays unit-testable without shelling out to `gh`, cloning a repo, or calling the
Anthropic API.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mcp_review.findings import ReviewResult
from mcp_review.llm.reviewer import LLMReviewer
from mcp_review.llm.t2_reviewer import AgenticReviewer
from mcp_review.static_rules import SourceFile, run_static_rules


def run_review(
    diff_text: str,
    changed_files: list[SourceFile],
    llm_reviewer: LLMReviewer | None = None,
    skip_llm: bool = False,
    run_agentic: bool = False,
    repo_root: Path | None = None,
    agentic_reviewer: AgenticReviewer | None = None,
    on_stage: Callable[[str, object], None] | None = None,
) -> ReviewResult:
    """`on_stage`, if given, is called as each tier starts ("t0:start") and finishes
    ("t0"/"t1"/"t2", with that tier's findings list or outcome object) — used by the web
    UI to show live progress and token usage without re-implementing this orchestration.
    """
    notify = on_stage or (lambda stage, payload: None)
    result = ReviewResult()

    notify("t0:start", None)
    static_findings = run_static_rules(changed_files)
    result.extend(static_findings)
    notify("t0", static_findings)

    if not skip_llm:
        reviewer = llm_reviewer or LLMReviewer()
        notify("t1:start", None)
        outcome = reviewer.review_diff(diff_text)
        result.extend(outcome.findings)
        notify("t1", outcome)

    if run_agentic:
        if repo_root is None:
            raise ValueError("run_agentic=True requires repo_root (a local checkout of the PR head)")
        reviewer = agentic_reviewer or AgenticReviewer()
        notify("t2:start", None)
        t2_outcome = reviewer.review_repo(repo_root, diff_text)
        result.extend(t2_outcome.findings)
        notify("t2", t2_outcome)

    return result
