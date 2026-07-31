from mcp_review.static_rules.protocol_version import ProtocolVersionRule


def test_bad_fixture_flags_blind_echo(load_fixture):
    rule = ProtocolVersionRule()
    findings = rule.scan(load_fixture("protocol_version_bad.py"))

    assert len(findings) == 1
    assert findings[0].rule_id == "protocol-version-ignored"


def test_good_fixture_has_no_findings(load_fixture):
    rule = ProtocolVersionRule()
    findings = rule.scan(load_fixture("protocol_version_good.py"))

    assert findings == []
