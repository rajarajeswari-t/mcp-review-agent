"""Shared parsing of Claude's structured findings-list JSON output into Finding
objects. Used by both the T1 (single-call) and T2 (agentic) reviewers so the
confidence-filtering and unknown-rule-id handling can't drift between them.
"""

from __future__ import annotations

import logging

from mcp_review.checklist import CHECKLIST_BY_ID
from mcp_review.findings import Finding, Tier

logger = logging.getLogger(__name__)

# Below this, Claude itself isn't confident it's a real instance — drop it rather than
# add noise. This is the model's per-instance confidence in *this* finding, a different
# axis from Finding.confidence (the checklist item's fixed spec authority).
_MIN_CONFIDENCE_TO_REPORT = {"high", "medium"}


def parse_findings(payload: dict, tier: Tier) -> list[Finding]:
    findings: list[Finding] = []
    for raw in payload.get("findings", []):
        finding = _to_finding(raw, tier)
        if finding is not None:
            findings.append(finding)
    return findings


def _to_finding(raw: dict, tier: Tier) -> Finding | None:
    checklist_item = CHECKLIST_BY_ID.get(raw.get("rule_id"))
    if checklist_item is None:
        logger.warning("Response referenced unknown rule_id %r; skipping", raw.get("rule_id"))
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
        tier=tier,
        file=raw.get("file"),
        line=raw.get("line"),
        spec_ref=checklist_item.spec_ref,
    )
