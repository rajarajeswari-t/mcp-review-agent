from mcp_review.static_rules.origin_validation import OriginValidationRule


def test_bad_fixture_flags_missing_origin_check(load_fixture):
    rule = OriginValidationRule()
    findings = rule.scan(load_fixture("origin_validation_bad.py"))

    assert len(findings) == 1
    assert findings[0].rule_id == "missing-origin-validation"


def test_good_fixture_has_no_findings(load_fixture):
    rule = OriginValidationRule()
    findings = rule.scan(load_fixture("origin_validation_good.py"))

    assert findings == []


def test_non_http_file_is_ignored(load_fixture):
    from mcp_review.static_rules.base import SourceFile

    rule = OriginValidationRule()
    file = SourceFile(path="unrelated.py", content="def add(a, b):\n    return a + b\n")
    assert rule.scan(file) == []
