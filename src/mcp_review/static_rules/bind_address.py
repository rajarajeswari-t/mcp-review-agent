"""#18 — binding a local-only server to 0.0.0.0 instead of 127.0.0.1."""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_BIND_ALL = re.compile(r"""["']0\.0\.0\.0["']|\bINADDR_ANY\b""")


class BindAddressRule(StaticRule):
    checklist_id = "bind-all-interfaces"

    def scan(self, file: SourceFile) -> list[Finding]:
        findings: list[Finding] = []
        for match in _BIND_ALL.finditer(file.content):
            line = file.content.count("\n", 0, match.start()) + 1
            findings.append(
                self.make_finding(
                    "Server binds to 0.0.0.0 (all interfaces). Spec: when running locally, "
                    "servers SHOULD bind only to localhost (127.0.0.1) rather than all "
                    "network interfaces. If this is meant to be reachable from other hosts "
                    "(e.g. a container behind a reverse proxy), this may be intentional — verify.",
                    file=file,
                    line=line,
                    snippet=file.lines[line - 1].strip() if line - 1 < len(file.lines) else None,
                )
            )
        return findings
