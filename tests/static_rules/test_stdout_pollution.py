from mcp_review.static_rules.stdout_pollution import StdoutPollutionRule


def test_bad_fixture_flags_print_to_stdout(load_fixture):
    rule = StdoutPollutionRule()
    findings = rule.scan(load_fixture("stdout_pollution_bad.py"))

    assert len(findings) == 1
    assert findings[0].rule_id == "stdout-pollution"


def test_good_fixture_has_no_findings(load_fixture):
    rule = StdoutPollutionRule()
    findings = rule.scan(load_fixture("stdout_pollution_good.py"))

    assert findings == []


def test_unrelated_file_without_stdio_marker_is_ignored(load_fixture):
    # A file with a bare print() but no stdio-transport marker shouldn't be flagged —
    # this rule only makes sense in the context of an actual stdio server.
    from mcp_review.static_rules.base import SourceFile

    rule = StdoutPollutionRule()
    file = SourceFile(path="unrelated.py", content='print("just a normal script")\n')
    assert rule.scan(file) == []
