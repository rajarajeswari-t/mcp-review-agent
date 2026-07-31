"""Structured-output JSON schema for the T1 and T2 review passes.

Built from the checklist itself so the set of valid `rule_id` values can't drift out of
sync with what the prompt actually asks Claude to look for.
"""

from __future__ import annotations

from mcp_review.checklist import items_for_tier
from mcp_review.findings import Tier


def rule_ids_for_tier(tier: Tier) -> list[str]:
    return [item.id for item in items_for_tier(tier)]


def findings_output_schema(tier: Tier) -> dict:
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "enum": rule_ids_for_tier(tier),
                            "description": "Which checklist item this finding matches.",
                        },
                        "file": {
                            "type": "string",
                            "description": "Path of the file this finding applies to, exactly as it appears in the diff.",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Line number in the new version of the file, if determinable.",
                        },
                        "message": {
                            "type": "string",
                            "description": "Specific, concrete explanation of what was found and why it matches this rule.",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "How confident you are this is a real instance of the rule, not a false positive.",
                        },
                    },
                    "required": ["rule_id", "file", "message", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["findings"],
        "additionalProperties": False,
    }
