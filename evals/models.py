"""Data model for the live eval suite.

One case = one deliberate, hand-crafted example demonstrating (or deliberately not
demonstrating) a single checklist item, run against the real reviewer. This is the
"does detection actually work" evidence the rest of the test suite can't provide —
the pytest suite only proves the plumbing is wired correctly with stubbed responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class T1EvalCase:
    rule_id: str
    name: str
    diff_text: str
    expect_finding: bool  # True: this rule_id should fire. False: it should NOT (negative control).


@dataclass(frozen=True)
class T2EvalCase:
    rule_id: str
    name: str
    files: dict[str, str]  # relative path -> content, builds a temp repo
    diff_text: str
    expect_finding: bool


@dataclass
class EvalResult:
    tier: str
    rule_id: str
    name: str
    expected: bool
    actual: bool
    passed: bool
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    turns: int = 1
    notes: str = ""
    matched_findings: list[str] = field(default_factory=list)
