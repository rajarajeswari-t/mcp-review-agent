from mcp_review.static_rules.bind_address import BindAddressRule


def test_bad_fixture_flags_bind_all_interfaces(load_fixture):
    rule = BindAddressRule()
    findings = rule.scan(load_fixture("bind_address_bad.py"))

    assert len(findings) == 1
    assert findings[0].rule_id == "bind-all-interfaces"


def test_good_fixture_has_no_findings(load_fixture):
    rule = BindAddressRule()
    findings = rule.scan(load_fixture("bind_address_good.py"))

    assert findings == []
