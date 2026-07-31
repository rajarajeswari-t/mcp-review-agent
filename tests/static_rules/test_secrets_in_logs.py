from mcp_review.static_rules.secrets_in_logs import SecretsInLogsRule


def test_bad_fixture_flags_secret_shaped_and_email_logs(load_fixture):
    rule = SecretsInLogsRule()
    findings = rule.scan(load_fixture("secrets_in_logs_bad.py"))

    assert len(findings) == 2
    assert all(f.rule_id == "secrets-in-logs" for f in findings)


def test_good_fixture_has_no_findings(load_fixture):
    rule = SecretsInLogsRule()
    findings = rule.scan(load_fixture("secrets_in_logs_good.py"))

    assert findings == []
