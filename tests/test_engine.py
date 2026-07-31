import pytest

from mcp_review.engine import run_review
from mcp_review.findings import Confidence, Finding, Severity, Tier
from mcp_review.llm.reviewer import LLMReviewer, T1ReviewOutcome
from mcp_review.llm.t2_reviewer import AgenticReviewer, T2ReviewOutcome
from mcp_review.report import to_json, to_markdown
from mcp_review.static_rules.base import SourceFile


class _StubReviewer(LLMReviewer):
    def __init__(self, outcome: T1ReviewOutcome):
        self._outcome = outcome

    def review_diff(self, diff_text: str) -> T1ReviewOutcome:
        return self._outcome


class _StubAgenticReviewer(AgenticReviewer):
    def __init__(self, outcome: T2ReviewOutcome):
        self._outcome = outcome

    def review_repo(self, repo_root, diff_text: str) -> T2ReviewOutcome:
        return self._outcome


def test_run_review_merges_t0_and_t1_findings():
    files = [SourceFile(path="a.py", content='uvicorn.run(app, host="0.0.0.0")')]
    stub = _StubReviewer(T1ReviewOutcome(findings=[]))

    result = run_review("some diff", files, llm_reviewer=stub)

    rule_ids = {f.rule_id for f in result.findings}
    assert "bind-all-interfaces" in rule_ids


def test_run_review_skip_llm_does_not_touch_reviewer():
    files = [SourceFile(path="a.py", content='uvicorn.run(app, host="0.0.0.0")')]

    class ExplodingReviewer(LLMReviewer):
        def __init__(self):
            pass

        def review_diff(self, diff_text: str) -> T1ReviewOutcome:
            raise AssertionError("should not be called when skip_llm=True")

    result = run_review("some diff", files, llm_reviewer=ExplodingReviewer(), skip_llm=True)
    assert any(f.rule_id == "bind-all-interfaces" for f in result.findings)


def test_report_markdown_and_json_render_something_sensible():
    files = [SourceFile(path="a.py", content='uvicorn.run(app, host="0.0.0.0")')]
    stub = _StubReviewer(T1ReviewOutcome(findings=[]))
    result = run_review("diff", files, llm_reviewer=stub)

    md = to_markdown(result)
    assert "bind-all-interfaces" not in md  # rule_id isn't shown; title is
    assert "0.0.0.0" in md or "localhost" in md.lower() or "interfaces" in md.lower()

    js = to_json(result)
    assert '"rule_id": "bind-all-interfaces"' in js


def test_report_markdown_clean_diff():
    stub = _StubReviewer(T1ReviewOutcome(findings=[]))
    result = run_review("diff", [], llm_reviewer=stub)
    assert "No MCP-specific issues found" in to_markdown(result)


def test_run_agentic_requires_repo_root():
    stub = _StubReviewer(T1ReviewOutcome(findings=[]))
    with pytest.raises(ValueError, match="repo_root"):
        run_review("diff", [], llm_reviewer=stub, run_agentic=True)


def test_run_agentic_merges_t2_findings(tmp_path):
    stub_t1 = _StubReviewer(T1ReviewOutcome(findings=[]))
    t2_finding = Finding(
        rule_id="token-passthrough",
        title="Token passthrough",
        message="Client bearer token forwarded unmodified to the upstream API.",
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        tier=Tier.T2,
        file="proxy.py",
        line=10,
    )
    stub_t2 = _StubAgenticReviewer(T2ReviewOutcome(findings=[t2_finding]))

    result = run_review(
        "diff",
        [],
        llm_reviewer=stub_t1,
        run_agentic=True,
        repo_root=tmp_path,
        agentic_reviewer=stub_t2,
    )

    rule_ids = {f.rule_id for f in result.findings}
    assert "token-passthrough" in rule_ids
