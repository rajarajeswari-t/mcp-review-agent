from mcp_review.static_rules.tool_names import ToolNameRule


def test_bad_fixture_flags_invalid_name_and_duplicate(load_fixture):
    rule = ToolNameRule()
    file = load_fixture("tool_names_bad.py")
    findings = rule.scan(file)
    findings += rule.finalize()

    messages = " ".join(f.message for f in findings)
    assert any("contains characters outside" in f.message for f in findings)
    assert any("declared 2 times" in f.message for f in findings)
    assert all(f.rule_id == "malformed-tool-names" for f in findings)


def test_good_fixture_has_no_findings(load_fixture):
    rule = ToolNameRule()
    file = load_fixture("tool_names_good.py")
    findings = rule.scan(file)
    findings += rule.finalize()

    assert findings == []
