"""Orchestrates one full review run: T0 static rules + T1 Claude pass + optional T2
agentic pass, merged.

Takes already-fetched diff text and file contents rather than a PR reference, so it
stays unit-testable without shelling out to `gh`, cloning a repo, or calling the
Anthropic API.
"""

from __future__ import annotations

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
) -> ReviewResult:
    result = ReviewResult()

    result.extend(run_static_rules(changed_files))

    if not skip_llm:
        reviewer = llm_reviewer or LLMReviewer()
        outcome = reviewer.review_diff(diff_text)
        result.extend(outcome.findings)

    if run_agentic:
        if repo_root is None:
            raise ValueError("run_agentic=True requires repo_root (a local checkout of the PR head)")
        reviewer = agentic_reviewer or AgenticReviewer()
        t2_outcome = reviewer.review_repo(repo_root, diff_text)
        result.extend(t2_outcome.findings)

    return result
