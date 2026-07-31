"""Builds the T1 system prompt directly from the checklist — the checklist stays the
single source of truth, so updating checklist.py automatically updates what Claude is
asked to look for.
"""

from __future__ import annotations

from mcp_review.checklist import ChecklistItem, items_for_tier
from mcp_review.findings import Tier

_INTRO = """You are reviewing a pull request to an MCP (Model Context Protocol) server \
repository. Your job is narrow: check the diff below against a fixed list of known \
MCP-specific mistakes, drawn from the official MCP specification. Do not report generic \
code-quality issues, style nits, or anything outside the list below — those are handled \
by other tools.

For each checklist item, only report a finding if the diff gives you concrete evidence \
of that specific mistake. If you're not sure, either omit it or mark confidence "low" — \
do not guess to pad the findings list. It is fine and expected to return an empty \
findings list for a clean diff.

Checklist items to check for:
"""

_ITEM_TEMPLATE = """
### {number}. {title} (`{id}`)
{description}
Spec reference: {spec_ref}
"""

_CLOSING = """
Return your findings as structured JSON matching the provided schema. Each finding's \
`file` must exactly match a file path from the diff, and `line` should be a line number \
in the new (post-change) version of that file when you can determine one from the diff \
context.
"""


def _render_item(item: ChecklistItem) -> str:
    return _ITEM_TEMPLATE.format(
        number=item.number,
        title=item.title,
        id=item.id,
        description=item.description,
        spec_ref=item.spec_ref,
    )


def build_t1_system_prompt() -> str:
    items = items_for_tier(Tier.T1)
    body = "\n".join(_render_item(item) for item in items)
    return _INTRO + body + _CLOSING


def build_user_message(diff_text: str) -> str:
    return f"Here is the PR diff to review (unified diff format):\n\n```diff\n{diff_text}\n```"
