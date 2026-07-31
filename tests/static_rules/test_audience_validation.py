from mcp_review.static_rules.audience_validation import AudienceValidationRule


def test_bad_fixture_flags_missing_audience_check(load_fixture):
    rule = AudienceValidationRule()
    findings = rule.scan(load_fixture("audience_validation_bad.py"))

    assert len(findings) == 1
    assert findings[0].rule_id == "missing-audience-validation"


def test_good_fixture_has_no_findings(load_fixture):
    rule = AudienceValidationRule()
    findings = rule.scan(load_fixture("audience_validation_good.py"))

    assert findings == []
