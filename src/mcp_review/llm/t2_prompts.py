"""System prompt for the T2 agentic review pass, built from checklist.py — same pattern
as T1's prompts.py, so updating checklist.py automatically updates what Claude is asked
to investigate.
"""

from __future__ import annotations

from mcp_review.checklist import ChecklistItem, items_for_tier
from mcp_review.findings import Tier

_INTRO = """You are reviewing a pull request to an MCP (Model Context Protocol) server \
repository for a fixed list of MCP-specific mistakes that can't be judged from the diff \
alone — they require reading other files in the repository to confirm.

You have three tools: list_files, read_file, and grep_repo. Use them to gather concrete \
evidence before reporting a finding — read the actual validation logic, trace how a \
variable is used across files, or check whether client-declared roots are actually \
consulted as a guard. Do not report a finding based on the diff alone if the checklist \
item requires cross-file evidence; go look first.

Investigate efficiently: a handful of targeted reads/greps is enough for most items. \
Stop investigating and report once you have enough evidence either way — don't \
exhaustively read the whole repository, and don't re-read a file you've already read.

Checklist items to check for:
"""

_ITEM_TEMPLATE = """
### {number}. {title} (`{id}`)
{description}
Spec reference: {spec_ref}
"""

_CLOSING = """
Once you've gathered enough evidence, respond with your final findings as structured \
JSON matching the provided schema — do not call any more tools once you're ready to \
answer. Each finding's `file` must be a real path you read or observed via grep, and \
`line` a line number in that file where possible.
"""


def _render_item(item: ChecklistItem) -> str:
    return _ITEM_TEMPLATE.format(
        number=item.number,
        title=item.title,
        id=item.id,
        description=item.description,
        spec_ref=item.spec_ref,
    )


def build_t2_system_prompt() -> str:
    items = items_for_tier(Tier.T2)
    body = "\n".join(_render_item(item) for item in items)
    return _INTRO + body + _CLOSING


def build_t2_user_message(diff_text: str) -> str:
    return (
        "Here is the PR diff that changed. Use it to figure out where to start "
        "investigating, then use your tools to gather evidence from the full "
        "repository before concluding anything:\n\n"
        f"```diff\n{diff_text}\n```"
    )
