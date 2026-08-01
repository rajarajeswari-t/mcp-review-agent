# MCP Server Code-Review Agent

An AI agent that reviews pull requests to MCP ([Model Context Protocol](https://modelcontextprotocol.io)) server repositories, flags security and correctness issues, and eventually becomes a paid AIaaS product.

## Status

**Phase 1 (non-agentic MVP) and Phase 2 (agentic loop) core engines are both built and
have a real eval suite behind them**, not just spot checks. See
[Evaluation results](#evaluation-results) for the full picture and
[Known limitations](#known-limitations) for what's still genuinely untested.

Not yet built: the live GitHub Action workflow that calls this engine on every PR and
posts a review comment — the last piece before this can run unattended on a real repo.

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
   - ✅ Full eval suite: all 8 T1 checklist items, positive + negative control each (16/16 passing) — see [Evaluation results](#evaluation-results)
   - ⬜ Live posting as a GitHub Action PR review comment (core engine is ready; the workflow wiring itself isn't built yet)
3. **Phase 2 — Agentic loop** — Claude tool-use loop for the checklist items that need multi-file reasoning instead of diff-only judgment (OAuth token passthrough, confused-deputy setups, roots-boundary enforcement, and the other T2-tagged items).
   - ✅ Manual tool-use loop (`list_files`, `read_file`, `grep_repo`) over a locally-cloned PR head, bounded by `max_iterations`, with the same refusal-handling and confidence-filtering as T1
   - ✅ Repo cloning (handles forked PRs via `head.repo.clone_url`) verified against a real PR
   - ✅ Full eval suite: all 8 T2 checklist items, positive controls for all 8 + negative controls for 4 of the trickiest ones (12/12 passing) — see [Evaluation results](#evaluation-results)
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

## Evaluation results

`evals/` is a real eval suite, not throwaway scripts — one deliberate positive (bug
present) and, for most items, one negative (clean) hand-crafted example per checklist
item, run against the live reviewers. This is the evidence for "does detection actually
work," which the pytest suite (stubbed responses) can't provide on its own.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python evals/run_evals.py            # ~$0.73, ~4 minutes, all 28 cases
python evals/run_evals.py --t1-only  # ~$0.12, ~45s
python evals/run_evals.py --t2-only  # ~$0.61, ~4 minutes
```

**Latest full run: 28/28 passing** (16 T1 cases across all 8 T1 items, 12 T2 cases
covering all 8 T2 items with negative controls for the 4 most false-positive-prone
ones: tool-input-not-validated, unvalidated-resource-uri, roots-boundary-ignored,
confused-deputy).

| Tier | Cases | Avg cost/case | Avg latency/case | Notes |
|---|---|---|---|---|
| T1 | 16 | $0.0075 | 2.9s | Single call, 1 turn always |
| T2 | 12 | $0.0508 | 16.7s | 3–5 tool-use turns typically; up to 44s and 7 turns on the hardest (confused-deputy) |

**This did not pass on the first try, and that's the actual value of building it.**
Getting to 28/28 took three rounds of fixing — and the fixes were almost all to *my*
hand-written "clean" fixtures, not the model:

- A "good" pagination-cursor example used `itsdangerous.Signer` (signs, doesn't encrypt)
  — Claude correctly pointed out the underlying page offset was still readable, just
  tamper-proof, which isn't genuinely opaque. Fixed by switching to real encryption
  (`Fernet`).
- A "good" roots-boundary check used `uri.startswith(root)` — Claude correctly caught
  that a naive string-prefix check isn't real path containment (`/allowed-root-evil`
  would pass). Fixed with `os.path.realpath` + separator-aware comparison.
- A "good" confused-deputy fixture added per-client consent tracking and local
  `redirect_uri` matching — Claude correctly identified that the deeper issue was
  architectural: the proxy was still forwarding the *dynamic client's* `redirect_uri`
  straight to the third party under a shared static `client_id`. The actual fix (per
  the spec's own documented consent flow) is that the proxy must use its **own** fixed
  callback URL with the third party and only redirect to the client's real
  `redirect_uri` as a separate final step, after its own token exchange.
- A "good" tool-input-validation fixture added path-traversal checks but no
  authorization scoping — Claude correctly noted checklist item #4 covers access
  control and rate limiting too, not just path format, per the spec text it's built
  from.

Every one of these was a real gap in the fixture, confirmed by re-reading the actual
spec language after the fact — not the model being oversensitive. That's a stronger
signal about detection quality than a clean pass on the first attempt would have been.

**Observed non-determinism.** The hardest T2 case (`confused_deputy_good`, on the
architecturally-correct final fixture) was run 5 times total: 4 clean, 1 false-positive.
This is inherent model variance on a genuinely complex multi-file OAuth scenario at
`effort=medium` — Claude 5-family models don't expose a temperature knob to reduce this.
Treat any single eval run as a sample, not a guarantee; for a real go/no-go decision on
a specific finding, re-running once is cheap insurance.

**Real-world broadening.** Beyond the 3 `modelcontextprotocol/servers` PRs, T0 and T1
were run against a real, actively-maintained third-party MCP server with actual
production OAuth code:
[cloudflare/mcp-server-cloudflare#393](https://github.com/cloudflare/mcp-server-cloudflare/pull/393)
("Fix malformed API token auth handling"). T0's `missing-audience-validation` rule (zero
prior real-world exercise) fired on all 5 touched auth files. Manual inspection of the
real source couldn't conclusively resolve whether this is a true or false positive
without deep knowledge of Cloudflare's `workers-oauth-provider` internals — the code
validates tokens by calling back to Cloudflare's own API rather than checking a local
JWT `aud` claim, which may or may not be an equivalent protection. This is exactly the
"weak signal, verify manually" behavior that rule's own docstring warns about — real
evidence the caveat is warranted, not just theoretical. T1 stayed clean (no
hallucinated findings) on the same large, unfamiliar, 28KB diff.

## Known limitations

Honest gaps that remain after the above:

- **Only Claude Sonnet 5 has been tested.** No comparison against Opus or other models
  for detection quality, and no data on whether a cheaper/faster model would do
  noticeably worse.
- **One deliberate case per item, not exhaustive.** Every eval case was written to
  demonstrate its mistake unambiguously. Subtler, more realistic variants (partial
  validation that misses one edge case, a confused-deputy setup spread across 4+ files
  instead of 2) haven't been systematically tried.
- **The `origin-validation` T0 rule (missing Origin header checks) still has zero
  real-world exercise** — none of the real PRs tested so far touched Streamable HTTP
  transport setup code.
- **No large-diff/large-repo stress test.** Every real PR tested so far touched 1–9
  files. Cost, latency, and quality on a PR touching 50+ files, or a T2 investigation
  in a large monorepo, are unknown.
- **Small real-world sample overall**: 4 repos, 4 PRs. 3 of those PRs are from one
  actively-reviewed official repo (a best-case codebase); only 1 PR is from a
  less-curated third-party server.
- **Language coverage is narrow.** T0's static rules only scan `.py`/`.js`/`.ts`/`.mjs`/`.cjs`
  files — no support for Go, Rust, Java, or other languages MCP servers are written in.
- **No adversarial testing against a hostile actor** — everything tested so far is a
  good-faith bug, not an attempt to evade detection (e.g. a tool description or code
  comment crafted to mislead the reviewer itself).

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
tests/                          # pytest suite, incl. fixtures per rule (stubbed responses)
evals/                           # live eval suite against the real API (costs money, see above)
  models.py                        # T1EvalCase/T2EvalCase/EvalResult
  t1_cases.py / t2_cases.py         # one deliberate positive+negative example per checklist item
  run_evals.py                       # runner: pass/fail, cost, latency
```

## License

TBD.
