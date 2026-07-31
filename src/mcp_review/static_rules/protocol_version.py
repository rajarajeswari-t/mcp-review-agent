"""#3 — ignoring protocol version negotiation.

Spec: the server MUST respond with the same protocolVersion if it supports it, otherwise
another version it supports — not just blindly echo whatever the client sent. Over HTTP,
the server MUST also handle the MCP-Protocol-Version header.

Two narrow, best-effort sub-checks:
1. An `initialize` handler that assigns protocolVersion straight from the incoming request
   with no visible comparison/branching nearby.
2. An HTTP MCP endpoint file with no reference to the MCP-Protocol-Version header at all.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_LHS_TARGETS_PROTOCOL_VERSION = re.compile(r"""protocolVersion|protocol_version""", re.IGNORECASE)

# RHS reads protocolVersion off something that looks like the incoming request/message
_RHS_READS_FROM_REQUEST = re.compile(
    r"""(?:request|req|params|message|msg|client\w*)\s*"""
    r"""(?:\[["']protocol[_]?[Vv]ersion["']\]|\.protocol_?[Vv]ersion)""",
)

_ASSIGNMENT_LINE = re.compile(r"""^(?P<lhs>[^=]*)=(?!=)(?P<rhs>.*)$""")

_HTTP_TRANSPORT_MARKER = re.compile(
    r"StreamableHTTP|streamable_http|text/event-stream|mcp[-_]session[-_]id",
    re.IGNORECASE,
)

_VERSION_HEADER_MARKER = re.compile(r"MCP-Protocol-Version", re.IGNORECASE)


class ProtocolVersionRule(StaticRule):
    checklist_id = "protocol-version-ignored"

    def scan(self, file: SourceFile) -> list[Finding]:
        findings: list[Finding] = []

        for i, raw_line in enumerate(file.lines, start=1):
            assignment = _ASSIGNMENT_LINE.match(raw_line.strip())
            if not assignment:
                continue
            lhs, rhs = assignment.group("lhs"), assignment.group("rhs")
            if _LHS_TARGETS_PROTOCOL_VERSION.search(lhs) and _RHS_READS_FROM_REQUEST.search(rhs):
                findings.append(
                    self.make_finding(
                        "initialize handler appears to echo the client's protocolVersion "
                        "straight back with no visible comparison against supported versions. "
                        "Spec: if the server supports the requested version it MUST respond with "
                        "that version; otherwise it MUST respond with another version it actually "
                        "supports — never just echo unconditionally.",
                        file=file,
                        line=i,
                        snippet=raw_line.strip(),
                    )
                )

        if _HTTP_TRANSPORT_MARKER.search(file.content) and not _VERSION_HEADER_MARKER.search(file.content):
            findings.append(
                self.make_finding(
                    "File appears to implement the Streamable HTTP transport but never "
                    "references the MCP-Protocol-Version header. Spec: the server MUST "
                    "handle this header on requests after initialization. (Heuristic: "
                    "absence-based — verify manually.)",
                    file=file,
                    line=1,
                )
            )

        return findings
