"""Runs the T2 agentic review pass: a manual tool-use loop where Claude can read_file,
grep_repo, and list_files across the checked-out repo to gather cross-file evidence
before reporting findings, instead of judging from the diff alone.

Uses a manual loop rather than the SDK's (beta) Tool Runner: combining custom tools with
output_config.format (structured JSON output) is documented for client.messages.create()
directly, but that combination isn't documented for the Tool Runner helper, and this
codebase's own reference material warns against guessing SDK behavior that isn't shown
in the docs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from mcp_review.findings import Finding, Tier
from mcp_review.llm.client import build_client, get_effort, get_model
from mcp_review.llm.parsing import parse_findings
from mcp_review.llm.schema import findings_output_schema
from mcp_review.llm.t2_prompts import build_t2_system_prompt, build_t2_user_message
from mcp_review.llm.t2_tools import T2ToolSet

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 12
_MAX_TOKENS = 8192


@dataclass
class T2ReviewOutcome:
    findings: list[Finding] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    hit_max_iterations: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0


class AgenticReviewer:
    def __init__(self, client=None, model: str | None = None, effort: str | None = None):
        self._client = client or build_client()
        self._model = model or get_model()
        self._effort = effort or get_effort()

    def review_repo(self, repo_root: Path, diff_text: str) -> T2ReviewOutcome:
        tools = T2ToolSet(repo_root)
        messages: list[dict] = [{"role": "user", "content": build_t2_user_message(diff_text)}]
        input_tokens = 0
        output_tokens = 0

        for turn in range(1, _MAX_ITERATIONS + 1):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=build_t2_system_prompt(),
                tools=T2ToolSet.tool_schemas(),
                messages=messages,
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": findings_output_schema(Tier.T2)},
                },
            )
            if response.usage:
                input_tokens += getattr(response.usage, "input_tokens", 0)
                output_tokens += getattr(response.usage, "output_tokens", 0)

            if response.stop_reason == "refusal":
                reason = getattr(response.stop_details, "category", None) if response.stop_details else None
                logger.warning("T2 review call was refused (category=%s)", reason)
                return T2ReviewOutcome(
                    refused=True,
                    refusal_reason=reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    turns=turn,
                )

            if response.stop_reason != "tool_use":
                outcome = self._parse_final_response(response)
                outcome.input_tokens = input_tokens
                outcome.output_tokens = output_tokens
                outcome.turns = turn
                return outcome

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_text = tools.dispatch(block.name, block.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                    )
            messages.append({"role": "user", "content": tool_results})

        logger.warning("T2 review hit max_iterations (%d) without a final answer", _MAX_ITERATIONS)
        return T2ReviewOutcome(
            hit_max_iterations=True, input_tokens=input_tokens, output_tokens=output_tokens, turns=_MAX_ITERATIONS
        )

    def _parse_final_response(self, response) -> T2ReviewOutcome:
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            return T2ReviewOutcome()

        payload = json.loads(text)
        return T2ReviewOutcome(findings=parse_findings(payload, Tier.T2))
