from mcp_review.checklist import CHECKLIST, items_for_tier
from mcp_review.findings import Tier
from mcp_review.static_rules import ALL_RULES, run_static_rules
from mcp_review.static_rules.base import SourceFile


def test_checklist_has_24_items_covering_1_to_24():
    assert len(CHECKLIST) == 24
    assert sorted(item.number for item in CHECKLIST) == list(range(1, 25))


def test_every_t0_checklist_item_has_a_registered_rule():
    t0_ids = {item.id for item in items_for_tier(Tier.T0)}
    registered_ids = {rule_cls().checklist_id for rule_cls in ALL_RULES}
    assert t0_ids == registered_ids, (
        f"Mismatch between T0 checklist items and registered static rules: "
        f"missing rules for {t0_ids - registered_ids}, "
        f"stray rules for {registered_ids - t0_ids}"
    )


def test_run_static_rules_across_multiple_files_merges_findings():
    files = [
        SourceFile(path="a.py", content='uvicorn.run(app, host="0.0.0.0")'),
        SourceFile(path="b.py", content='logger.info(f"password={pw}")'),
    ]
    findings = run_static_rules(files)
    rule_ids = {f.rule_id for f in findings}
    assert "bind-all-interfaces" in rule_ids
    assert "secrets-in-logs" in rule_ids
