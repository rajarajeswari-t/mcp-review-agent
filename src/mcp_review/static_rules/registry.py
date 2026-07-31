"""Collects every T0 rule and runs them all against a set of source files."""

from __future__ import annotations

from mcp_review.findings import Finding
from mcp_review.static_rules.audience_validation import AudienceValidationRule
from mcp_review.static_rules.base import SourceFile, StaticRule
from mcp_review.static_rules.bind_address import BindAddressRule
from mcp_review.static_rules.noarg_schema import NoArgSchemaRule
from mcp_review.static_rules.origin_validation import OriginValidationRule
from mcp_review.static_rules.protocol_version import ProtocolVersionRule
from mcp_review.static_rules.secrets_in_logs import SecretsInLogsRule
from mcp_review.static_rules.stdout_pollution import StdoutPollutionRule
from mcp_review.static_rules.tool_names import ToolNameRule


def _rule_factories() -> list[type[StaticRule]]:
    return [
        ProtocolVersionRule,
        ToolNameRule,
        NoArgSchemaRule,
        StdoutPollutionRule,
        OriginValidationRule,
        BindAddressRule,
        AudienceValidationRule,
        SecretsInLogsRule,
    ]


ALL_RULES = _rule_factories()


def run_static_rules(files: list[SourceFile]) -> list[Finding]:
    findings: list[Finding] = []
    rules = [factory() for factory in _rule_factories()]

    for rule in rules:
        for file in files:
            findings.extend(rule.scan(file))

    for rule in rules:
        findings.extend(rule.finalize())

    return findings
