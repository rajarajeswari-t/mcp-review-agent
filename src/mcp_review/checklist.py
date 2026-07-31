"""The 24-item MCP-specific mistake checklist, sourced from the modelcontextprotocol/modelcontextprotocol
spec (2025-11-25) and its Security Best Practices doc. This is the single source of truth used both by
the T0 static rules (which reference a `ChecklistItem.id` when they fire) and by the T1 Claude prompt
(which is built directly from this list).

Do not restate spec language from memory when editing this file — cross-check against the spec docs
this was derived from before changing severity/confidence tags.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcp_review.findings import Confidence, Severity, Tier


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    number: int
    category: str
    title: str
    tier: Tier
    severity: Severity
    confidence: Confidence
    spec_ref: str
    description: str
    static_detectable: str  # what a regex/AST pass can and can't catch, for T0 rule authors


CHECKLIST: list[ChecklistItem] = [
    ChecklistItem(
        id="capability-not-negotiated",
        number=1,
        category="Protocol & Lifecycle",
        title="Using a capability that was never negotiated",
        tier=Tier.T2,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.HARD_MUST,
        spec_ref="basic/lifecycle#capability-negotiation",
        description=(
            "Server emits a notification or handles a request tied to a capability "
            "(e.g. notifications/resources/updated) that it never declared in its "
            "initialize response capabilities object."
        ),
        static_detectable=(
            "Partial: grep the capabilities object literal vs grep for notification-send call "
            "sites, but confirming intent needs cross-file reasoning."
        ),
    ),
    ChecklistItem(
        id="handshake-order-violation",
        number=2,
        category="Protocol & Lifecycle",
        title="Jumping the handshake",
        tier=Tier.T1,
        severity=Severity.SPEC_COMPLIANCE,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="basic/lifecycle#initialization",
        description=(
            "Server sends requests/notifications other than ping/logging before it has "
            "received the client's notifications/initialized."
        ),
        static_detectable="Weak: needs control-flow tracing of what fires relative to the initialized handler.",
    ),
    ChecklistItem(
        id="protocol-version-ignored",
        number=3,
        category="Protocol & Lifecycle",
        title="Ignoring protocol version negotiation",
        tier=Tier.T0,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.HARD_MUST,
        spec_ref="basic/lifecycle#version-negotiation, basic/transports#protocol-version-header",
        description=(
            "Server doesn't check the client's requested protocolVersion against what it "
            "actually supports, or ignores the MCP-Protocol-Version header on later HTTP requests."
        ),
        static_detectable="Good: grep the initialize handler for unconditional version echo; grep HTTP layer for header validation.",
    ),
    ChecklistItem(
        id="tool-input-not-validated",
        number=4,
        category="Tools",
        title="Trusting model-supplied tool arguments",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/tools#security-considerations",
        description=(
            "tools/call arguments come from the LLM. Server executes them without input "
            "validation, access control, rate limiting, or output sanitization."
        ),
        static_detectable="Weak: presence of an `if` isn't the same as adequate validation; needs judgment.",
    ),
    ChecklistItem(
        id="error-channel-conflation",
        number=5,
        category="Tools",
        title="Conflating protocol errors and tool execution errors",
        tier=Tier.T1,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/tools#error-handling (SEP-1303)",
        description=(
            "Returning a raw JSON-RPC error for a recoverable business-logic failure "
            "(e.g. bad date) instead of isError: true in the tools/call result, denying "
            "the model the readable feedback it needs to self-correct."
        ),
        static_detectable="Partial: grep tool handlers for raised protocol errors around input-validation-shaped messages.",
    ),
    ChecklistItem(
        id="malformed-tool-names",
        number=6,
        category="Tools",
        title="Malformed or colliding tool names",
        tier=Tier.T0,
        severity=Severity.SPEC_COMPLIANCE,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="server/tools#tool-names",
        description=(
            "Tool names should be 1-128 chars, only [A-Za-z0-9_.-], and unique within the server."
        ),
        static_detectable="Good: pure regex against every declared tool name plus a dedupe check.",
    ),
    ChecklistItem(
        id="output-schema-drift",
        number=7,
        category="Tools",
        title="structuredContent not conforming to declared outputSchema",
        tier=Tier.T1,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/tools#output-schema",
        description=(
            "Tool declares an outputSchema but returns structuredContent that doesn't validate "
            "against it."
        ),
        static_detectable="Weak: needs an example call or test execution to actually check conformance.",
    ),
    ChecklistItem(
        id="noarg-schema-sloppiness",
        number=8,
        category="Tools",
        title="Sloppy no-argument input schemas",
        tier=Tier.T0,
        severity=Severity.SPEC_COMPLIANCE,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/tools#tool",
        description=(
            "inputSchema is null/missing (a spec MUST violation), or omits "
            "additionalProperties: false for a no-arg tool (merely the 'Recommended' option)."
        ),
        static_detectable="Good: inspect the inputSchema JSON directly per declared tool.",
    ),
    ChecklistItem(
        id="unvalidated-resource-uri",
        number=9,
        category="Resources & Roots",
        title="Unvalidated resource URIs (path traversal)",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/resources#security-considerations",
        description=(
            "resources/read handler doesn't normalize/boundary-check a file:// URI before "
            "touching disk, allowing e.g. file:///../../etc/passwd."
        ),
        static_detectable="Weak: classic taint-tracking problem, needs reasoning about the actual path-join logic.",
    ),
    ChecklistItem(
        id="roots-boundary-ignored",
        number=10,
        category="Resources & Roots",
        title="Ignoring client-declared roots",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="client/roots#security-considerations",
        description=(
            "Server fetches roots/list but never actually consults it before reading/writing "
            "files outside those boundaries."
        ),
        static_detectable="Weak: needs to confirm the roots result is actually used as a guard, not just fetched.",
    ),
    ChecklistItem(
        id="unnecessary-resource-proxying",
        number=11,
        category="Resources & Roots",
        title="Proxying web content the client could fetch itself",
        tier=Tier.T2,
        severity=Severity.SPEC_COMPLIANCE,
        confidence=Confidence.SUGGESTION,
        spec_ref="server/resources#common-uri-schemes",
        description=(
            "Using https:// resource URIs the client could fetch directly, forcing needless "
            "server-side mediation."
        ),
        static_detectable="None: pure judgment call about whether mediation is actually needed. Report as a suggestion, not a flag.",
    ),
    ChecklistItem(
        id="resource-template-mismatch",
        number=12,
        category="Resources & Roots",
        title="Resource template / read-handler mismatch",
        tier=Tier.T1,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.SUGGESTION,
        spec_ref="server/resources#resource-templates",
        description=(
            "uriTemplate advertises a parameter (e.g. file:///{path}) that the resources/read "
            "handler doesn't actually honor the way the template implies."
        ),
        static_detectable="Partial: match {param} names in the template string against handler parameter extraction.",
    ),
    ChecklistItem(
        id="sampling-misuse",
        number=13,
        category="Sampling",
        title="Servers misusing sampling/createMessage",
        tier=Tier.T1,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="client/sampling#security-considerations",
        description=(
            "Server asks the client's LLM to do unscoped/unbounded sampling, doesn't match "
            "ToolUseContent to ToolResultContent by toolUseId, or has no iteration limit on "
            "tool loops."
        ),
        static_detectable="Partial: grep for toolUseId matching logic and iteration-limit constants.",
    ),
    ChecklistItem(
        id="elicitation-misuse",
        number=14,
        category="Elicitation",
        title="Servers misusing elicitation/create",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="client/elicitation#security-considerations",
        description=(
            "Server doesn't bind elicitation requests to client/user identity, puts PII or a "
            "pre-authenticated URL in a URL-mode elicitation link, requests passwords/API keys "
            "via form mode, or doesn't verify the user who opens a URL-mode link is the same "
            "user who triggered it (phishing/account-takeover risk)."
        ),
        static_detectable="Weak: identity-binding and phishing-flow correctness are semantic judgments.",
    ),
    ChecklistItem(
        id="list-changed-not-fired",
        number=15,
        category="Change Notifications",
        title="listChanged declared but never fired on mutation",
        tier=Tier.T1,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="server/tools#list-changed-notification (and resources/prompts equivalents)",
        description=(
            "Server declares tools.listChanged/resources.listChanged/prompts.listChanged "
            "but its registry mutates at runtime without ever emitting the notification."
        ),
        static_detectable="Partial: heuristic for 'registry mutated here, no adjacent notify call'.",
    ),
    ChecklistItem(
        id="stdout-pollution",
        number=16,
        category="Transport",
        title="Polluting stdout in a stdio server",
        tier=Tier.T0,
        severity=Severity.CORRECTNESS,
        confidence=Confidence.HARD_MUST,
        spec_ref="basic/transports#stdio",
        description=(
            "Debug/log output written to stdout instead of stderr in a stdio-transport server, "
            "corrupting the JSON-RPC message stream."
        ),
        static_detectable="Good: grep for print()/console.log()/System.out writes outside the JSON-RPC write path.",
    ),
    ChecklistItem(
        id="missing-origin-validation",
        number=17,
        category="Transport",
        title="No Origin header validation on Streamable HTTP",
        tier=Tier.T0,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="basic/transports#security-warning",
        description="DNS-rebinding exposure: server doesn't validate the Origin header and reject with 403.",
        static_detectable="Good: check HTTP server setup for Origin-validation middleware.",
    ),
    ChecklistItem(
        id="bind-all-interfaces",
        number=18,
        category="Transport",
        title="Binding a local-only server to 0.0.0.0",
        tier=Tier.T0,
        severity=Severity.SECURITY,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="basic/transports#security-warning",
        description="Local-only HTTP server bound to 0.0.0.0/INADDR_ANY instead of 127.0.0.1.",
        static_detectable="Good: grep bind/listen calls for 0.0.0.0 or INADDR_ANY.",
    ),
    ChecklistItem(
        id="weak-session-auth",
        number=19,
        category="Transport",
        title="Weak or authenticating-by session ID",
        tier=Tier.T1,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="docs/tutorials/security/security_best_practices#session-hijacking",
        description=(
            "Predictable/sequential MCP-Session-Id values, or treating a valid session ID as "
            "sufficient proof of identity instead of real per-request authentication."
        ),
        static_detectable="Partial: RNG source (Math.random() vs CSPRNG) is checkable; 'session as sole auth' needs reasoning.",
    ),
    ChecklistItem(
        id="token-passthrough",
        number=20,
        category="Authorization",
        title="Token passthrough",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="docs/tutorials/security/security_best_practices#token-passthrough",
        description=(
            "Server accepts the client's bearer token and forwards it unmodified to a "
            "downstream API instead of validating its audience and using its own upstream credential."
        ),
        static_detectable="Weak: requires data-flow tracing of the token variable across the trust boundary.",
    ),
    ChecklistItem(
        id="missing-audience-validation",
        number=21,
        category="Authorization",
        title="Skipping token audience validation",
        tier=Tier.T0,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="basic/authorization#token-handling",
        description="Server accepts any token that verifies, without checking it was issued specifically for this server (aud claim).",
        static_detectable="Partial: grep token verification code for an audience/aud check.",
    ),
    ChecklistItem(
        id="confused-deputy",
        number=22,
        category="Authorization",
        title="Confused-deputy proxy setup",
        tier=Tier.T2,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="docs/tutorials/security/security_best_practices#confused-deputy-problem",
        description=(
            "MCP proxy uses one static client_id toward a third-party IdP, allows MCP clients "
            "to dynamically register their own client_ids, and has no per-client consent store "
            "before forwarding to the third-party authorization server."
        ),
        static_detectable="None: architectural pattern spread across multiple files/handlers, not a grep target.",
    ),
    ChecklistItem(
        id="non-opaque-cursors",
        number=23,
        category="Operational Utilities",
        title="Non-opaque pagination cursors",
        tier=Tier.T1,
        severity=Severity.SPEC_COMPLIANCE,
        confidence=Confidence.SOFT_SHOULD,
        spec_ref="server/utilities/pagination",
        description=(
            "Cursors implemented as parseable page numbers instead of opaque tokens, or an "
            "invalid cursor crashes instead of returning -32602."
        ),
        static_detectable="Partial: client-side 'don't parse cursors' is checkable; server-side cursor design is a judgment call.",
    ),
    ChecklistItem(
        id="secrets-in-logs",
        number=24,
        category="Operational Utilities",
        title="Leaking secrets through logging",
        tier=Tier.T0,
        severity=Severity.SECURITY,
        confidence=Confidence.HARD_MUST,
        spec_ref="server/utilities/logging#security",
        description=(
            "notifications/message data field includes credentials, tokens, or PII."
        ),
        static_detectable="Good (partial): regex for password/api_key/token/email-shaped patterns in logging call sites.",
    ),
]

CHECKLIST_BY_ID: dict[str, ChecklistItem] = {item.id: item for item in CHECKLIST}


def items_for_tier(tier: Tier) -> list[ChecklistItem]:
    return [item for item in CHECKLIST if item.tier == tier]
