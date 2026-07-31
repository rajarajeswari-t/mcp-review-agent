"""Base classes shared by every T0 static rule."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_review.checklist import CHECKLIST_BY_ID
from mcp_review.findings import Finding


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str

    @property
    def lines(self) -> list[str]:
        return self.content.splitlines()


class StaticRule:
    """One T0 regex/heuristic check, tied to exactly one checklist item.

    Subclasses implement `scan`. Tags (severity/confidence/tier/spec_ref/title) are pulled
    from the checklist entry automatically so they can never drift out of sync with it.
    """

    checklist_id: str

    def scan(self, file: SourceFile) -> list[Finding]:
        raise NotImplementedError

    def finalize(self) -> list[Finding]:
        """Override for rules that need whole-run state (e.g. cross-file duplicate names)."""
        return []

    def make_finding(
        self,
        message: str,
        file: SourceFile | None = None,
        line: int | None = None,
        snippet: str | None = None,
    ) -> Finding:
        item = CHECKLIST_BY_ID[self.checklist_id]
        return Finding(
            rule_id=item.id,
            title=item.title,
            message=message,
            severity=item.severity,
            confidence=item.confidence,
            tier=item.tier,
            file=file.path if file else None,
            line=line,
            snippet=snippet,
            spec_ref=item.spec_ref,
        )
