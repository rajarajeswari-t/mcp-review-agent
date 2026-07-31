"""#8 — sloppy no-argument input schemas.

Spec: inputSchema MUST be a valid JSON Schema object (not null). For no-arg tools, the
recommended (but not mandatory) shape is {"type": "object", "additionalProperties": false}.

Real-world false positive this guards against: the TypeScript MCP SDK's raw zod-shape
style (`inputSchema: { field: z.string()... }`) never contains a literal "properties"
key — that's only true of JSON-Schema-literal or Python-dict-literal schemas. A schema
with real zod-declared fields must not be mistaken for a bare no-arg schema.
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_NULL_SCHEMA = re.compile(r"""(?:inputSchema|input_schema)\s*[:=]\s*(None|null)\b""")
_SCHEMA_START = re.compile(r"""(?:inputSchema|input_schema)\s*[:=]\s*\{""")
_ZOD_FIELD = re.compile(r"""\w+\s*:\s*z\.""")


def _extract_balanced_braces(text: str, open_brace_index: int) -> str | None:
    """Given the index of a `{`, return the substring through its matching `}`."""
    depth = 0
    for i in range(open_brace_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace_index : i + 1]
    return None


class NoArgSchemaRule(StaticRule):
    checklist_id = "noarg-schema-sloppiness"

    def scan(self, file: SourceFile) -> list[Finding]:
        findings: list[Finding] = []

        for match in _NULL_SCHEMA.finditer(file.content):
            line = file.content.count("\n", 0, match.start()) + 1
            findings.append(
                self.make_finding(
                    "inputSchema is null/None. Spec: inputSchema MUST be a valid JSON Schema "
                    "object, not null — even a no-arg tool needs an explicit "
                    '{"type": "object", "additionalProperties": false}.',
                    file=file,
                    line=line,
                    snippet=match.group(0),
                )
            )

        for match in _SCHEMA_START.finditer(file.content):
            brace_start = match.end() - 1
            block = _extract_balanced_braces(file.content, brace_start)
            if block is None:
                continue
            has_properties = (
                '"properties"' in block
                or "'properties'" in block
                or "properties=" in block
                or bool(_ZOD_FIELD.search(block))
            )
            has_additional_properties_false = re.search(
                r"""additionalProperties["']?\s*[:=]\s*(false|False)""", block
            )
            looks_like_object_type = "object" in block

            if looks_like_object_type and not has_properties and not has_additional_properties_false:
                line = file.content.count("\n", 0, match.start()) + 1
                findings.append(
                    self.make_finding(
                        "inputSchema looks like a no-argument schema but doesn't set "
                        'additionalProperties: false. Recommended (not mandatory) shape: '
                        '{"type": "object", "additionalProperties": false} so it explicitly '
                        "rejects unexpected arguments.",
                        file=file,
                        line=line,
                        snippet=block[:120],
                    )
                )

        return findings
