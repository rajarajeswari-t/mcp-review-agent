"""#16 — polluting stdout in a stdio-transport server.

Spec: over stdio, the server MUST NOT write anything to stdout that is not a valid MCP
message. Debug/log output must go to stderr instead.

Scope: only fires in files that look like they implement the stdio transport, to avoid
flagging print()/console.log() in ordinary application code that has nothing to do with MCP.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_STDIO_TRANSPORT_MARKER = re.compile(
    r"stdio_server|StdioServerTransport|stdio_client|run_stdio|StdioServerParameters",
    re.IGNORECASE,
)

# print(...) not routed to stderr
_PY_PRINT = re.compile(r"""\bprint\s*\((?![^)]*(?:file\s*=\s*sys\.stderr|file\s*=\s*stderr))[^)]*\)""")

# console.log (not .error/.warn, which Node routes to stderr)
_JS_CONSOLE_LOG = re.compile(r"""\bconsole\.log\s*\(""")


class StdoutPollutionRule(StaticRule):
    checklist_id = "stdout-pollution"

    def scan(self, file: SourceFile) -> list[Finding]:
        if not _STDIO_TRANSPORT_MARKER.search(file.content):
            return []

        findings: list[Finding] = []

        if file.path.endswith(".py"):
            for match in _PY_PRINT.finditer(file.content):
                line = file.content.count("\n", 0, match.start()) + 1
                findings.append(
                    self.make_finding(
                        "print() call in a file that sets up the stdio transport, without "
                        "routing to stderr. Over stdio, stdout MUST contain only valid MCP "
                        "JSON-RPC messages — use `print(..., file=sys.stderr)` or a logger "
                        "configured to write to stderr instead.",
                        file=file,
                        line=line,
                        snippet=file.lines[line - 1].strip() if line - 1 < len(file.lines) else None,
                    )
                )
        elif file.path.endswith((".js", ".ts", ".mjs", ".cjs")):
            for match in _JS_CONSOLE_LOG.finditer(file.content):
                line = file.content.count("\n", 0, match.start()) + 1
                findings.append(
                    self.make_finding(
                        "console.log() call in a file that sets up the stdio transport. "
                        "console.log writes to stdout, which MUST contain only valid MCP "
                        "JSON-RPC messages over stdio — use console.error() (stderr) instead.",
                        file=file,
                        line=line,
                        snippet=file.lines[line - 1].strip() if line - 1 < len(file.lines) else None,
                    )
                )

        return findings
