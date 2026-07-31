"""`mcp-review` CLI entry point."""

from __future__ import annotations

import re

import click

from mcp_review.diff import PullRequestRef, fetch_changed_source_files, fetch_pr_diff
from mcp_review.engine import run_review
from mcp_review.report import to_json, to_markdown
from mcp_review.repo import clone_pr_head

_PR_URL_RE = re.compile(r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)")


def parse_pr_ref(value: str) -> PullRequestRef:
    match = _PR_URL_RE.search(value)
    if match:
        return PullRequestRef(owner=match["owner"], repo=match["repo"], number=int(match["number"]))

    parts = value.split("#")
    if len(parts) == 2 and "/" in parts[0]:
        owner, repo = parts[0].split("/", 1)
        return PullRequestRef(owner=owner, repo=repo, number=int(parts[1]))

    raise click.BadParameter(f"Could not parse {value!r} as a PR reference. Use a GitHub PR URL or owner/repo#number.")


@click.command()
@click.argument("pr_ref")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--skip-llm", is_flag=True, help="Run only the free T0 static checks, skip the Claude call.")
@click.option(
    "--agentic",
    is_flag=True,
    help="Also run the T2 agentic pass (clones the PR head locally; slower and costs more).",
)
def main(pr_ref: str, output_format: str, skip_llm: bool, agentic: bool) -> None:
    """Review a GitHub PR against the MCP mistake checklist.

    PR_REF: a GitHub PR URL, or owner/repo#number (e.g. modelcontextprotocol/servers#123).
    """
    pr = parse_pr_ref(pr_ref)

    click.echo(f"Fetching {pr.slug}#{pr.number}...", err=True)
    diff_text = fetch_pr_diff(pr)
    changed_files = fetch_changed_source_files(pr)
    click.echo(f"{len(changed_files)} changed source file(s) to scan.", err=True)

    if agentic:
        click.echo("Cloning PR head for the T2 agentic pass...", err=True)
        with clone_pr_head(pr) as repo_root:
            result = run_review(diff_text, changed_files, skip_llm=skip_llm, run_agentic=True, repo_root=repo_root)
    else:
        result = run_review(diff_text, changed_files, skip_llm=skip_llm)

    if output_format == "json":
        click.echo(to_json(result))
    else:
        click.echo(to_markdown(result))


if __name__ == "__main__":
    main()
