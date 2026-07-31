#!/usr/bin/env python3
"""Dry-run backtest: pull a real historical PR and run the engine against it, printing
findings without posting anything. Used to sanity-check detection quality per the
project roadmap ("Backtested against historical PRs before going live").

Usage:
    python scripts/backtest.py <PR URL or owner/repo#number> [--skip-llm] [--agentic]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_review.cli import parse_pr_ref  # noqa: E402
from mcp_review.diff import fetch_changed_source_files, fetch_pr_diff  # noqa: E402
from mcp_review.engine import run_review  # noqa: E402
from mcp_review.report import to_markdown  # noqa: E402
from mcp_review.repo import clone_pr_head  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr_ref", help="GitHub PR URL or owner/repo#number")
    parser.add_argument("--skip-llm", action="store_true", help="Force-skip the Claude T1 pass")
    parser.add_argument(
        "--agentic",
        action="store_true",
        help="Also run the T2 agentic pass (clones the PR head locally; slower and costs more)",
    )
    args = parser.parse_args()

    pr = parse_pr_ref(args.pr_ref)

    skip_llm = args.skip_llm
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if not skip_llm:
            print("No ANTHROPIC_API_KEY set - running T0 static checks only.", file=sys.stderr)
        skip_llm = True
        if args.agentic:
            print("No ANTHROPIC_API_KEY set - cannot run the T2 agentic pass either.", file=sys.stderr)

    print(f"Fetching {pr.slug}#{pr.number}...", file=sys.stderr)
    diff_text = fetch_pr_diff(pr)
    changed_files = fetch_changed_source_files(pr)
    print(
        f"{len(changed_files)} changed source file(s) scanned: {[f.path for f in changed_files]}",
        file=sys.stderr,
    )

    run_agentic = args.agentic and os.environ.get("ANTHROPIC_API_KEY") is not None

    if run_agentic:
        print("Cloning PR head for the T2 agentic pass...", file=sys.stderr)
        with clone_pr_head(pr) as repo_root:
            result = run_review(diff_text, changed_files, skip_llm=skip_llm, run_agentic=True, repo_root=repo_root)
    else:
        result = run_review(diff_text, changed_files, skip_llm=skip_llm)

    print()
    print(to_markdown(result))


if __name__ == "__main__":
    main()
