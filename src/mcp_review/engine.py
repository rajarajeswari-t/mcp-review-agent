"""Orchestrates one full review run: T0 static rules + T1 Claude pass, merged.

Takes already-fetched diff text and file contents rather than a PR reference, so it
stays unit-testable without shelling out to `gh` or calling the Anthropic API.
"""

from __future__ import annotations

from mcp_review.findings import ReviewResult
from mcp_review.llm.reviewer import LLMReviewer
from mcp_review.static_rules import SourceFile, run_static_rules


def run_review(
    diff_text: str,
    changed_files: list[SourceFile],
    llm_reviewer: LLMReviewer | None = None,
    skip_llm: bool = False,
) -> ReviewResult:
    result = ReviewResult()

    result.extend(run_static_rules(changed_files))

    if not skip_llm:
        reviewer = llm_reviewer or LLMReviewer()
        outcome = reviewer.review_diff(diff_text)
        result.extend(outcome.findings)

    return result
