"""Renders a ReviewResult as Markdown (for a PR comment) or JSON."""

from __future__ import annotations

import json

from mcp_review.findings import ReviewResult


def to_json(result: ReviewResult) -> str:
    return json.dumps(result.to_dict(), indent=2)


def to_markdown(result: ReviewResult) -> str:
    findings = result.sorted()
    if not findings:
        return "No MCP-specific issues found by the automated checklist review."

    lines = [
        "## MCP checklist review",
        "",
        f"Found **{len(findings)}** potential issue(s) against the MCP mistake checklist.",
        "",
    ]

    for f in findings:
        location = f"`{f.file}`" + (f":{f.line}" if f.line else "")
        lines.append(f"### {location} — {f.title}")
        lines.append(f"- **Severity:** {f.severity.value} · **Confidence:** {f.confidence.value} · **Tier:** {f.tier.value}")
        lines.append(f"- {f.message}")
        if f.spec_ref:
            lines.append(f"- Spec: `{f.spec_ref}`")
        if f.snippet:
            lines.append(f"\n  ```\n  {f.snippet}\n  ```")
        lines.append("")

    return "\n".join(lines)
