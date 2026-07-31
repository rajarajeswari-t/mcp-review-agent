"""#21 — skipping token audience validation.

Spec: MCP servers MUST only accept tokens issued specifically for them (aud claim or
equivalent). This is an absence check on token-verification code: fires when a file looks
like it verifies bearer tokens but never references an audience concept anywhere in it.
Genuinely weak signal — high false-negative rate (frameworks that check audience via config
rather than code won't show up at all) and some false-positive rate. Treat as "go verify
manually", not a confirmed finding.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_TOKEN_VERIFICATION_MARKER = re.compile(
    r"jwt\.decode|verify_token|validate_token|jwt\.verify|introspect|Bearer\s",
)

_AUDIENCE_MARKER = re.compile(r"""\baud(?:ience)?\b""", re.IGNORECASE)


class AudienceValidationRule(StaticRule):
    checklist_id = "missing-audience-validation"

    def scan(self, file: SourceFile) -> list[Finding]:
        if not _TOKEN_VERIFICATION_MARKER.search(file.content):
            return []
        if _AUDIENCE_MARKER.search(file.content):
            return []

        return [
            self.make_finding(
                "File appears to verify bearer tokens but never references an audience "
                "('aud') check. Spec: MCP servers MUST validate that access tokens were "
                "issued specifically for them (audience claim) and MUST reject tokens that "
                "aren't. (Heuristic: absence-based, weak signal — verify manually; this "
                "won't catch audience checks done via framework config rather than code.)",
                file=file,
                line=1,
            )
        ]
