# MCP Server Code-Review Agent

An AI agent that reviews pull requests to MCP ([Model Context Protocol](https://modelcontextprotocol.io)) server repositories, flags security and correctness issues, and eventually becomes a paid AIaaS product.

## Status

**Phase 1 (non-agentic MVP) and Phase 2 (agentic loop) core engines are both built.**
T0 static rules, the T1 single-call Claude reviewer, and the T2 agentic tool-use loop all
work end to end against real PRs (see Backtesting below) — T2's repo-cloning and
tool-execution path has been verified against a real PR; the Claude-call half of T2 is
tested against a stubbed client only, since no `ANTHROPIC_API_KEY` has been available in
the environment this was built in. Not yet built: the live GitHub Action workflow that
calls this engine on every PR and posts a review comment.

Note on the roadmap below: item 2 originally specified a **GitHub App**. The actual build
uses a **GitHub Action** instead (runs in the target repo's own CI on `pull_request`,
posts via the built-in `GITHUB_TOKEN`) — same outcome, no webhook server or app-approval
process required to adopt it. Revisit a full GitHub App only if a hosted, org-wide
install becomes necessary later.

See [modelcontextprotocol/modelcontextprotocol#3101](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3101)
for the original community validation post (no responses yet as of this writing).

## Roadmap

1. **Learn the failure modes** — a 24-item checklist of concrete MCP server mistakes across 7 categories (protocol lifecycle, tools, resources, sampling, elicitation, transport, authorization), each tagged by detection method, severity, spec confidence, and cost tier. ✅ Done — `src/mcp_review/checklist.py`.
2. **Phase 1 — Non-agentic MVP** — fetch PR diffs and run a single Claude API call against the checklist, posting results as a PR review comment. Backtested against historical PRs before going live.
   - ✅ T0 static rule engine (8 rules, regex/heuristic, zero API cost)
   - ✅ T1 single-call Claude reviewer (Sonnet 5, structured JSON output, refusal-handling for security-sensitive diffs)
   - ✅ Diff fetching via `gh` CLI, CLI entry point, Markdown/JSON reporting
   - ✅ Backtested against 3 real PRs on `modelcontextprotocol/servers` — found and fixed one real false positive (a zod-shape `inputSchema` mistaken for a bare no-arg schema)
   - ⬜ Live posting as a GitHub Action PR review comment (core engine is ready; the workflow wiring itself isn't built yet)
3. **Phase 2 — Agentic loop** — Claude tool-use loop for the checklist items that need multi-file reasoning instead of diff-only judgment (OAuth token passthrough, confused-deputy setups, roots-boundary enforcement, and the other T2-tagged items).
   - ✅ Manual tool-use loop (`list_files`, `read_file`, `grep_repo`) over a locally-cloned PR head, bounded by `max_iterations`, with the same refusal-handling and confidence-filtering as T1
   - ✅ Repo cloning (handles forked PRs via `head.repo.clone_url`) and the tool-execution path verified against a real PR
   - ⬜ Not yet backtested against a real PR end-to-end with a live Claude call (no API key available in the build environment) — do this before trusting T2 output on a real repo
4. **Phase 3 — Distribution** — run (with permission) on active open-source MCP server repos, post genuine findings back to the community, track metrics.
5. **Phase 4 — Private pilots** — free scans for a few teams building private MCP servers, in exchange for feedback.
6. **Phase 5 — Business** — convert to a paid product once validated.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...   # only needed for the T1 Claude pass
gh auth login                         # needed for fetching PR diffs
```

## Usage

```bash
# Review a real PR (T0 static + T1 Claude pass)
mcp-review https://github.com/owner/repo/pull/123
mcp-review owner/repo#123 --format json

# Free static-only pass, no API key needed
mcp-review owner/repo#123 --skip-llm

# Also run the T2 agentic pass (clones the PR head locally; slower, costs more)
mcp-review owner/repo#123 --agentic
```

## Backtesting

```bash
python scripts/backtest.py owner/repo#123
python scripts/backtest.py owner/repo#123 --agentic
```

Dry-run only — fetches a real PR and prints findings, never posts anything. Falls back
to `--skip-llm` automatically if `ANTHROPIC_API_KEY` isn't set (which also disables
`--agentic`, since T2 needs a live Claude call).

## Running the test suite

```bash
python -m pytest tests/ -v
```

## Detection architecture

Checklist items are tagged by cost tier, which drives the build order:

- **T0** — regex/static, ~0 tokens. Runs as a linter pass, no LLM call needed.
- **T1** — single Claude call, no tools. Diff + checklist context, one-shot judgment.
- **T2** — agentic loop. Claude gets `list_files`/`read_file`/`grep_repo` over a locally-cloned checkout and decides what to look at; relevant spec text is embedded directly in the prompt per checklist item rather than fetched via a separate search tool.

Ship all T0 items as a static linter pass first (runs on every PR, effectively free). Layer in T1 items once T0 is stable. T2 items — the hardest and highest-value ones, like token passthrough and confused-deputy detection — are the actual justification for the agentic loop.

## Project layout

```
src/mcp_review/
  checklist.py        # the 24-item checklist — single source of truth for tags/prompts
  findings.py          # Finding/ReviewResult data model, Tier/Severity/Confidence enums
  static_rules/         # T0: one file per rule, all pulling tags from checklist.py
  llm/
    client.py            # shared Anthropic client/model/effort config
    schema.py             # structured-output JSON schema, parametrized by tier
    parsing.py             # shared findings-JSON -> Finding parsing (T1 and T2)
    prompts.py / reviewer.py     # T1: single-call prompt + reviewer
    t2_prompts.py / t2_tools.py / t2_reviewer.py  # T2: agentic prompt, tools, manual loop
  gh.py                # shared `gh` CLI wrapper
  diff.py                # gh-CLI-based PR diff/file fetching
  repo.py                 # shallow-clones a PR head for T2's tools to read
  engine.py                 # orchestrates T0 + T1 + optional T2 into one ReviewResult
  report.py                  # Markdown/JSON rendering
  cli.py                       # `mcp-review` entry point
scripts/backtest.py           # dry-run against a real PR, no posting
tests/                          # pytest suite, incl. fixtures per rule
```

## License

TBD.
