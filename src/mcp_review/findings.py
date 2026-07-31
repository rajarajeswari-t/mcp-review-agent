"""The shared data model every rule (static or LLM) produces results in."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tier(str, Enum):
    """Detection cost tier — drives which layer of the engine runs a check."""

    T0 = "T0"  # regex/static, ~0 tokens
    T1 = "T1"  # single Claude call, diff + checklist context, no tools
    T2 = "T2"  # full agentic loop, multi-file reasoning


class Severity(str, Enum):
    SECURITY = "security"
    CORRECTNESS = "correctness"
    SPEC_COMPLIANCE = "spec-compliance"


class Confidence(str, Enum):
    """How authoritative the underlying spec language is, not how sure the detector is."""

    HARD_MUST = "hard-must"  # spec says MUST / MUST NOT — report as a flag
    SOFT_SHOULD = "soft-should"  # spec says SHOULD — report as a suggestion
    SUGGESTION = "suggestion"  # best-practice, no explicit MUST/SHOULD in spec text


@dataclass
class Finding:
    """One concrete result: a specific checklist rule tripped at a specific location."""

    rule_id: str
    title: str
    message: str
    severity: Severity
    confidence: Confidence
    tier: Tier
    file: str | None = None
    line: int | None = None
    snippet: str | None = None
    spec_ref: str | None = None

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "tier": self.tier.value,
            "file": self.file,
            "line": self.line,
            "snippet": self.snippet,
            "spec_ref": self.spec_ref,
        }

    def sort_key(self) -> tuple:
        severity_rank = {Severity.SECURITY: 0, Severity.CORRECTNESS: 1, Severity.SPEC_COMPLIANCE: 2}
        confidence_rank = {Confidence.HARD_MUST: 0, Confidence.SOFT_SHOULD: 1, Confidence.SUGGESTION: 2}
        return (severity_rank[self.severity], confidence_rank[self.confidence], self.file or "", self.line or 0)


@dataclass
class ReviewResult:
    """All findings from a single run of the engine against one diff/repo."""

    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def sorted(self) -> list[Finding]:
        return sorted(self.findings, key=Finding.sort_key)

    def to_dict(self) -> dict:
        return {"findings": [f.to_dict() for f in self.sorted()]}
