import json
from types import SimpleNamespace

from mcp_review.llm.reviewer import LLMReviewer


def _fake_response(payload: dict, stop_reason: str = "end_turn", stop_details=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=stop_details,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def test_review_diff_parses_high_and_medium_confidence_findings():
    payload = {
        "findings": [
            {
                "rule_id": "weak-session-auth",
                "file": "server.py",
                "line": 42,
                "message": "Session IDs generated with random.randint, not a CSPRNG.",
                "confidence": "high",
            },
            {
                "rule_id": "error-channel-conflation",
                "file": "tools.py",
                "line": 10,
                "message": "Possible protocol error for a validation failure.",
                "confidence": "medium",
            },
        ]
    }
    client = _FakeClient(_fake_response(payload))
    reviewer = LLMReviewer(client=client, model="claude-sonnet-5", effort="medium")

    outcome = reviewer.review_diff("--- a/server.py\n+++ b/server.py\n...")

    assert not outcome.refused
    assert len(outcome.findings) == 2
    assert outcome.findings[0].rule_id == "weak-session-auth"
    assert outcome.findings[0].file == "server.py"
    assert outcome.findings[0].line == 42
    assert "model confidence" not in outcome.findings[0].message

    assert outcome.findings[1].rule_id == "error-channel-conflation"
    assert "model confidence: medium" in outcome.findings[1].message


def test_review_diff_drops_low_confidence_findings():
    payload = {
        "findings": [
            {
                "rule_id": "non-opaque-cursors",
                "file": "pagination.py",
                "message": "Might be a plain page number, unclear.",
                "confidence": "low",
            }
        ]
    }
    client = _FakeClient(_fake_response(payload))
    reviewer = LLMReviewer(client=client)

    outcome = reviewer.review_diff("some diff")

    assert outcome.findings == []
    assert not outcome.refused


def test_review_diff_skips_unknown_rule_id():
    payload = {
        "findings": [
            {
                "rule_id": "totally-made-up-rule",
                "file": "x.py",
                "message": "hallucinated",
                "confidence": "high",
            }
        ]
    }
    client = _FakeClient(_fake_response(payload))
    reviewer = LLMReviewer(client=client)

    outcome = reviewer.review_diff("some diff")

    assert outcome.findings == []


def test_review_diff_handles_refusal():
    stop_details = SimpleNamespace(category="cyber")
    client = _FakeClient(_fake_response({}, stop_reason="refusal", stop_details=stop_details))
    reviewer = LLMReviewer(client=client)

    outcome = reviewer.review_diff("some diff touching auth code")

    assert outcome.refused
    assert outcome.refusal_reason == "cyber"
    assert outcome.findings == []


def test_review_diff_sends_expected_request_shape():
    client = _FakeClient(_fake_response({"findings": []}))
    reviewer = LLMReviewer(client=client, model="claude-sonnet-5", effort="medium")

    reviewer.review_diff("diff content here")

    kwargs = client.messages.last_call_kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["output_config"]["effort"] == "medium"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "diff content here" in kwargs["messages"][0]["content"]
