from mcp_review.static_rules.noarg_schema import NoArgSchemaRule


def test_bad_fixture_flags_null_schema_and_loose_object(load_fixture):
    rule = NoArgSchemaRule()
    findings = rule.scan(load_fixture("noarg_schema_bad.py"))

    assert any("null/None" in f.message for f in findings)
    assert any("additionalProperties: false" in f.message for f in findings)


def test_good_fixture_has_no_findings(load_fixture):
    rule = NoArgSchemaRule()
    findings = rule.scan(load_fixture("noarg_schema_good.py"))

    assert findings == []


def test_zod_shape_schema_with_real_fields_is_not_flagged(load_fixture):
    # Regression test for a real false positive found backtesting against
    # modelcontextprotocol/servers PR #4510: a zod raw-shape inputSchema with actual
    # declared fields has no literal "properties" key, so it must not be mistaken for
    # a bare no-arg schema.
    rule = NoArgSchemaRule()
    findings = rule.scan(load_fixture("noarg_schema_good_zod.ts"))

    assert findings == []
