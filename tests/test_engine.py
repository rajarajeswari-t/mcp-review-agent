from mcp_review.engine import run_review
from mcp_review.llm.reviewer import LLMReviewer, T1ReviewOutcome
from mcp_review.report import to_json, to_markdown
from mcp_review.static_rules.base import SourceFile


class _StubReviewer(LLMReviewer):
    def __init__(self, outcome: T1ReviewOutcome):
        self._outcome = outcome

    def review_diff(self, diff_text: str) -> T1ReviewOutcome:
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
