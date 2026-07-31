"""#17 — no Origin header validation on Streamable HTTP.

Spec: servers MUST validate the Origin header on all incoming connections to prevent DNS
rebinding attacks, and respond 403 if it's present and invalid.

This is an absence check: only fires on files that look like they implement the Streamable
HTTP transport (strong positive markers), and then only if there's no sign of an Origin
check anywhere in that same file. Absence-based heuristics are inherently noisier than
presence-based ones — treat a hit here as "go look", not proof.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_HTTP_TRANSPORT_MARKER = re.compile(
    r"StreamableHTTP|streamable_http|text/event-stream|mcp[-_]session[-_]id",
    re.IGNORECASE,
)

_ORIGIN_CHECK_MARKER = re.compile(r"""origin""", re.IGNORECASE)


class OriginValidationRule(StaticRule):
    checklist_id = "missing-origin-validation"

    def scan(self, file: SourceFile) -> list[Finding]:
        if not _HTTP_TRANSPORT_MARKER.search(file.content):
            return []
        if _ORIGIN_CHECK_MARKER.search(file.content):
            return []

        return [
            self.make_finding(
                "File appears to implement the Streamable HTTP transport but has no "
                "reference to an Origin header check anywhere in it. Spec: servers MUST "
                "validate the Origin header on incoming connections and respond 403 if "
                "invalid, to prevent DNS-rebinding attacks. (Heuristic: absence-based — "
                "verify manually before treating as confirmed.)",
                file=file,
                line=1,
            )
        ]
