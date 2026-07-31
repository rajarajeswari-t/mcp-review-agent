"""Thin wrapper around the Anthropic client for the T1 review pass.

Model choice: this runs on every PR, so it's a high-volume, cost-sensitive workload —
Claude Sonnet 5 gives near-Opus quality on this kind of judgment call at a fraction of
Opus pricing. Override with MCP_REVIEW_MODEL for repos that want the extra headroom.
"""

from __future__ import annotations

import os

import anthropic

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 8192


def get_model() -> str:
    return os.environ.get("MCP_REVIEW_MODEL", DEFAULT_MODEL)


def get_effort() -> str:
    return os.environ.get("MCP_REVIEW_EFFORT", DEFAULT_EFFORT)


def build_client() -> anthropic.Anthropic:
    # Anthropic() resolves ANTHROPIC_API_KEY from the environment on its own.
    return anthropic.Anthropic()
