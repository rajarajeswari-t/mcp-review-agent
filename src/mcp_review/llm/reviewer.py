"""Runs the T1 single-call Claude review pass over a diff.

Structured outputs (`output_config.format`) guarantee the response is valid JSON matching
`findings_output_schema()`, including the `rule_id` enum — so a hallucinated rule_id
should be impossible in practice, but we still guard defensively rather than trust that.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from mcp_review.checklist import CHECKLIST_BY_ID
from mcp_review.findings import Finding, Tier
from mcp_review.llm.client import DEFAULT_MAX_TOKENS, build_client, get_effort, get_model
from mcp_review.llm.prompts import build_t1_system_prompt, build_user_message
from mcp_review.llm.schema import findings_output_schema

logger = logging.getLogger(__name__)

# Below this, Claude itself isn't confident it's a real instance — drop it rather than
# add noise. This is the model's per-instance confidence in *this* finding, which is a
# different axis from Finding.confidence (the checklist item's fixed spec authority).
_MIN_CONFIDENCE_TO_REPORT = {"high", "medium"}


@dataclass
class T1ReviewOutcome:
    findings: list[Finding] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None


class LLMReviewer:
    def __init__(self, client=None, model: str | None = None, effort: str | None = None):
        self._client = client or build_client()
        self._model = model or get_model()
        self._effort = effort or get_effort()

    def review_diff(self, diff_text: str) -> T1ReviewOutcome:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=build_t1_system_prompt(),
            messages=[{"role": "user", "content": build_user_message(diff_text)}],
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": findings_output_schema()},
            },
        )

        if response.stop_reason == "refusal":
            reason = getattr(response.stop_details, "category", None) if response.stop_details else None
            logger.warning("T1 review call was refused (category=%s); skipping LLM findings for this diff", reason)
            return T1ReviewOutcome(refused=True, refusal_reason=reason)

        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            return T1ReviewOutcome()

        payload = json.loads(text)
        findings: list[Finding] = []
        for raw in payload.get("findings", []):
            finding = self._to_finding(raw)
            if finding is not None:
                findings.append(finding)
        return T1ReviewOutcome(findings=findings)

    def _to_finding(self, raw: dict) -> Finding | None:
        rule_id = raw.get("rule_id")
        checklist_item = CHECKLIST_BY_ID.get(rule_id)
        if checklist_item is None:
            logger.warning("T1 response referenced unknown rule_id %r; skipping", rule_id)
            return None

        if raw.get("confidence") not in _MIN_CONFIDENCE_TO_REPORT:
            return None

        message = raw.get("message", "")
        if raw.get("confidence") == "medium":
            message = f"{message} (model confidence: medium — verify manually)"

        return Finding(
            rule_id=checklist_item.id,
            title=checklist_item.title,
            message=message,
            severity=checklist_item.severity,
            confidence=checklist_item.confidence,
            tier=Tier.T1,
            file=raw.get("file"),
            line=raw.get("line"),
            spec_ref=checklist_item.spec_ref,
        )
