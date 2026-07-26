# MCP Server Code-Review Agent

An AI agent that reviews pull requests to MCP ([Model Context Protocol](https://modelcontextprotocol.io)) server repositories, flags security and correctness issues, and eventually becomes a paid AIaaS product.

## Status

**Phase 0 — Validating demand.** See [modelcontextprotocol/modelcontextprotocol#3101](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3101) for the community validation post. No code yet.

## Roadmap

1. **Learn the failure modes** — a 24-item checklist of concrete MCP server mistakes across 7 categories (protocol lifecycle, tools, resources, sampling, elicitation, transport, authorization), each tagged by detection method, severity, spec confidence, and cost tier.
2. **Phase 1 — Non-agentic MVP** — GitHub App that fetches PR diffs and runs a single Claude API call against the checklist, posting results as a PR review comment. Backtested against historical PRs before going live.
3. **Phase 2 — Agentic loop** — Claude tool-use loop (`read_file`, `get_tool_schema`, `check_auth_flow`, `search_mcp_spec`) for the checklist items that need multi-file reasoning instead of diff-only judgment (e.g. OAuth token passthrough, confused-deputy setups).
4. **Phase 3 — Distribution** — run (with permission) on active open-source MCP server repos, post genuine findings back to the community, track metrics.
5. **Phase 4 — Private pilots** — free scans for a few teams building private MCP servers, in exchange for feedback.
6. **Phase 5 — Business** — convert to a paid product once validated.

## Detection architecture

Checklist items are tagged by cost tier, which drives the build order:

- **T0** — regex/static, ~0 tokens. Runs as a linter pass, no LLM call needed.
- **T1** — single Claude call, no tools. Diff + checklist context, one-shot judgment.
- **T2** — full agentic loop. Needs `read_file`, `search_mcp_spec`, and/or multi-file reasoning to resolve.

Ship all T0 items as a static linter pass first (runs on every PR, effectively free). Layer in T1 items once T0 is stable. T2 items — the hardest and highest-value ones, like token passthrough and confused-deputy detection — are the actual justification for building the agentic loop in Phase 2.

## License

TBD.
