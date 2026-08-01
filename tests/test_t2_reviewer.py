import json
from pathlib import Path
from types import SimpleNamespace

from mcp_review.findings import Tier
from mcp_review.llm.t2_reviewer import AgenticReviewer, _MAX_ITERATIONS


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_id: str, name: str, tool_input: dict):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def _response(content, stop_reason="end_turn", stop_details=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=stop_details,
        content=content,
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


class _QueuedMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _QueuedMessages(responses)


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "auth.py").write_text("def validate(token):\n    return jwt.decode(token, PUBLIC_KEY)\n")
    return tmp_path


def test_agentic_review_dispatches_tool_call_then_parses_final_answer(tmp_path):
    repo = _make_repo(tmp_path)

    tool_use_response = _response(
        [
            _text_block("Let me check the auth code."),
            _tool_use_block("tu_1", "read_file", {"path": "auth.py"}),
        ],
        stop_reason="tool_use",
    )
    final_payload = {
        "findings": [
            {
                "rule_id": "missing-audience-validation",
                "file": "auth.py",
                "line": 2,
                "message": "jwt.decode has no audience check.",
                "confidence": "high",
            }
        ]
    }
    final_response = _response([_text_block(json.dumps(final_payload))], stop_reason="end_turn")

    client = _FakeClient([tool_use_response, final_response])
    reviewer = AgenticReviewer(client=client, model="claude-sonnet-5", effort="medium")

    outcome = reviewer.review_repo(repo, "some diff")

    assert not outcome.refused
    assert not outcome.hit_max_iterations
    assert len(outcome.findings) == 1
    assert outcome.findings[0].rule_id == "missing-audience-validation"
    assert outcome.findings[0].tier == Tier.T2

    # Two API calls: one that triggered the tool call, one with the tool result fed back.
    assert len(client.messages.calls) == 2
    second_call_messages = client.messages.calls[1]["messages"]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    tool_result_block = tool_result_message["content"][0]
    assert tool_result_block["tool_use_id"] == "tu_1"
    assert "jwt.decode" in tool_result_block["content"]


def test_agentic_review_handles_refusal_immediately(tmp_path):
    repo = _make_repo(tmp_path)
    stop_details = SimpleNamespace(category="cyber")
    client = _FakeClient([_response([], stop_reason="refusal", stop_details=stop_details)])
    reviewer = AgenticReviewer(client=client)

    outcome = reviewer.review_repo(repo, "diff touching auth")

    assert outcome.refused
    assert outcome.refusal_reason == "cyber"
    assert outcome.findings == []
    assert len(client.messages.calls) == 1


def test_agentic_review_stops_at_max_iterations(tmp_path):
    repo = _make_repo(tmp_path)
    # Always asks for another tool call — never gives a final answer.
    endless_tool_use = _response(
        [_tool_use_block("tu_x", "list_files", {})],
        stop_reason="tool_use",
    )
    client = _FakeClient([endless_tool_use] * _MAX_ITERATIONS)
    reviewer = AgenticReviewer(client=client)

    outcome = reviewer.review_repo(repo, "diff")

    assert outcome.hit_max_iterations
    assert outcome.findings == []
    assert len(client.messages.calls) == _MAX_ITERATIONS


def test_agentic_review_empty_findings_on_clean_repo(tmp_path):
    repo = _make_repo(tmp_path)
    final_response = _response([_text_block(json.dumps({"findings": []}))], stop_reason="end_turn")
    client = _FakeClient([final_response])
    reviewer = AgenticReviewer(client=client)

    outcome = reviewer.review_repo(repo, "diff")

    assert outcome.findings == []
    assert not outcome.refused
