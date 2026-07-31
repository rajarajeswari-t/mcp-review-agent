"""#24 — leaking secrets through logging.

Spec: log messages MUST NOT contain credentials/secrets, PII, or internal system details
that could aid attacks. Fires when a logging call site's own line textually references a
narrow list of secret-shaped identifiers, to keep false positives down (a generic word like
"token" alone is too noisy — e.g. "token count" — so this list favors more specific names).
"""

from __future__ import annotations

import re

from mcp_review.findings import Finding
from mcp_review.static_rules.base import SourceFile, StaticRule

_LOG_CALL = re.compile(
    r"""\b(?:log(?:ger)?\.\w+|console\.(?:log|error|warn|info|debug)|print)\s*\(""",
    re.IGNORECASE,
)

_SECRET_SHAPED = re.compile(
    r"""password|api[_-]?key|access[_-]?token|secret[_-]?key|private[_-]?key|"""
    r"""client[_-]?secret|bearer\s+["'{]|authorization\s*[:=]""",
    re.IGNORECASE,
)

_EMAIL_LIKE = re.compile(r"""[\w.+-]+@[\w-]+\.[\w.-]+""")


class SecretsInLogsRule(StaticRule):
    checklist_id = "secrets-in-logs"

    def scan(self, file: SourceFile) -> list[Finding]:
        findings: list[Finding] = []
        for i, line in enumerate(file.lines, start=1):
            if not _LOG_CALL.search(line):
                continue

            secret_match = _SECRET_SHAPED.search(line)
            email_match = _EMAIL_LIKE.search(line)
            if not secret_match and not email_match:
                continue

            reason = (
                f"references a secret-shaped identifier ({secret_match.group(0)!r})"
                if secret_match
                else "includes what looks like a hardcoded/literal email address"
            )
            findings.append(
                self.make_finding(
                    f"Logging call {reason}. Spec: log messages MUST NOT contain credentials, "
                    "secrets, or personal identifying information. (Heuristic: keyword match on "
                    "the log line — verify whether the actual value logged is sensitive.)",
                    file=file,
                    line=i,
                    snippet=line.strip(),
                )
            )
        return findings
