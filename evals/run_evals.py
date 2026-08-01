#!/usr/bin/env python3
"""Live eval suite: runs one deliberate positive/negative example per checklist item
against the real reviewers and reports pass/fail plus cost/latency.

Requires ANTHROPIC_API_KEY. Costs real money and makes real API calls — this is meant
to be run deliberately when checking detection quality, not on every commit.

Usage:
    python evals/run_evals.py            # run everything
    python evals/run_evals.py --t1-only
    python evals/run_evals.py --t2-only
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.models import EvalResult, T1EvalCase, T2EvalCase  # noqa: E402
from evals.t1_cases import T1_CASES  # noqa: E402
from evals.t2_cases import T2_CASES  # noqa: E402
from mcp_review.llm.reviewer import LLMReviewer  # noqa: E402
from mcp_review.llm.t2_reviewer import AgenticReviewer  # noqa: E402

# Sonnet 5 pricing (see claude-api skill): $3/$15 standard, $2/$10 intro through 2026-08-31.
INPUT_PRICE_PER_MTOK = 3.00
OUTPUT_PRICE_PER_MTOK = 15.00


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000 * INPUT_PRICE_PER_MTOK) + (output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MTOK)


def run_t1_case(case: T1EvalCase, reviewer: LLMReviewer) -> EvalResult:
    start = time.monotonic()
    outcome = reviewer.review_diff(case.diff_text)
    latency = time.monotonic() - start

    matched = [f.rule_id for f in outcome.findings if f.rule_id == case.rule_id]
    fired = bool(matched)
    notes = "REFUSED" if outcome.refused else ""

    return EvalResult(
        tier="T1",
        rule_id=case.rule_id,
        name=case.name,
        expected=case.expect_finding,
        actual=fired,
        passed=(fired == case.expect_finding) and not outcome.refused,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        latency_s=latency,
        cost_usd=_cost(outcome.input_tokens, outcome.output_tokens),
        notes=notes,
        matched_findings=[f.message for f in outcome.findings if f.rule_id == case.rule_id],
    )


def run_t2_case(case: T2EvalCase, reviewer: AgenticReviewer) -> EvalResult:
    tmpdir = Path(tempfile.mkdtemp(prefix="mcp-eval-"))
    try:
        for rel_path, content in case.files.items():
            full = tmpdir / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)

        start = time.monotonic()
        outcome = reviewer.review_repo(tmpdir, case.diff_text)
        latency = time.monotonic() - start
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    matched = [f for f in outcome.findings if f.rule_id == case.rule_id]
    fired = bool(matched)
    notes = "REFUSED" if outcome.refused else ("MAX_ITERATIONS" if outcome.hit_max_iterations else "")

    return EvalResult(
        tier="T2",
        rule_id=case.rule_id,
        name=case.name,
        expected=case.expect_finding,
        actual=fired,
        passed=(fired == case.expect_finding) and not outcome.refused and not outcome.hit_max_iterations,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        latency_s=latency,
        cost_usd=_cost(outcome.input_tokens, outcome.output_tokens),
        turns=outcome.turns,
        notes=notes,
        matched_findings=[f.message for f in matched],
    )


def print_result(result: EvalResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(
        f"[{status}] {result.tier} {result.name:45s} "
        f"expected={result.expected!s:5s} actual={result.actual!s:5s} "
        f"turns={result.turns} {result.input_tokens}in/{result.output_tokens}out "
        f"${result.cost_usd:.4f} {result.latency_s:.1f}s {result.notes}"
    )
    if result.matched_findings:
        for msg in result.matched_findings:
            print(f"         -> {msg[:160]}")


def print_summary(results: list[EvalResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    total_cost = sum(r.cost_usd for r in results)
    total_time = sum(r.latency_s for r in results)

    print()
    print("=" * 70)
    print(f"SUMMARY: {passed}/{total} passed")
    print(f"Total cost: ${total_cost:.4f}   Total wall-clock time: {total_time:.1f}s")
    failures = [r for r in results if not r.passed]
    if failures:
        print()
        print("Failures:")
        for r in failures:
            print(f"  - {r.tier} {r.name}: expected={r.expected} actual={r.actual} notes={r.notes}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t1-only", action="store_true")
    parser.add_argument("--t2-only", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set — the eval suite needs a live API key.", file=sys.stderr)
        sys.exit(1)

    results: list[EvalResult] = []

    if not args.t2_only:
        t1_reviewer = LLMReviewer()
        for case in T1_CASES:
            result = run_t1_case(case, t1_reviewer)
            print_result(result)
            results.append(result)

    if not args.t1_only:
        t2_reviewer = AgenticReviewer()
        for case in T2_CASES:
            result = run_t2_case(case, t2_reviewer)
            print_result(result)
            results.append(result)

    print_summary(results)
    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
