"""#6 — malformed or colliding tool names.

Spec: tool names SHOULD be 1-128 chars, only [A-Za-z0-9_.-], unique within a server.

A bare `name=...` regex would fire on any unrelated class in the codebase, so this only
looks for a `name=`/`"name":` assignment that appears shortly after a recognizable MCP
primitive declaration marker (Tool(/Prompt(/Resource(/@mcp.tool/@server.tool/etc).
This will still miss some SDK-specific patterns (e.g. FastMCP tools named after the
decorated function) — it's a heuristic, not a parser.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_DECLARATION_MARKER = re.compile(
    r"""(?:
        \btypes\.(?:Tool|Prompt|Resource)\s*\(
        |\b(?:Tool|Prompt|Resource)\s*\(
        |@\w+\.(?:tool|prompt|resource)\s*\(
    )""",
    re.VERBOSE,
)

_NAME_ASSIGNMENT = re.compile(r"""name\s*[:=]\s*["']([^"']*)["']""")

_VALID_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")

_WINDOW_CHARS = 300


class ToolNameRule(StaticRule):
    checklist_id = "malformed-tool-names"

    def __init__(self) -> None:
        self._seen: dict[str, list[tuple[str, int]]] = {}

    def scan(self, file: SourceFile) -> list[Finding]:
        findings: list[Finding] = []
        for marker in _DECLARATION_MARKER.finditer(file.content):
            window = file.content[marker.end() : marker.end() + _WINDOW_CHARS]
            name_match = _NAME_ASSIGNMENT.search(window)
            if not name_match:
                continue

            name = name_match.group(1)
            abs_pos = marker.end() + name_match.start()
            line = file.content.count("\n", 0, abs_pos) + 1

            if not _VALID_NAME.match(name):
                if not name:
                    reason = "is empty"
                elif len(name) > 128:
                    reason = "is too long (>128 chars)"
                else:
                    reason = "contains characters outside [A-Za-z0-9_.-]"
                findings.append(
                    self.make_finding(
                        f"Declared name {name!r} {reason}. "
                        "Spec guidance: 1-128 chars, only letters/digits/underscore/hyphen/dot.",
                        file=file,
                        line=line,
                        snippet=name_match.group(0).strip(),
                    )
                )

            self._seen.setdefault(name, []).append((file.path, line))

        return findings

    def finalize(self) -> list[Finding]:
        findings: list[Finding] = []
        for name, locations in self._seen.items():
            if len(locations) > 1:
                loc_str = ", ".join(f"{path}:{line}" for path, line in locations)
                first_path, first_line = locations[0]
                findings.append(
                    self.make_finding(
                        f"Name {name!r} is declared {len(locations)} times ({loc_str}). "
                        "Spec guidance: tool names SHOULD be unique within a server "
                        "(this heuristic doesn't distinguish tools/prompts/resources, so verify manually).",
                        file=SourceFile(path=first_path, content=""),
                        line=first_line,
                    )
                )
        return findings
