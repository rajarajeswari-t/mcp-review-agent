"""Thin shell-out wrapper around the `gh` CLI, shared by diff.py and repo.py."""

from __future__ import annotations

import subprocess


def run_gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return result.stdout
