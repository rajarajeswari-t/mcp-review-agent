"""Local web UI for the review engine: `mcp-review-ui`.

A single-page app served by the standard library's HTTP server — no extra dependencies.
Reviews run in background threads as "jobs"; the page polls a job for live progress and
the final findings. Two input modes:

- **PR**: same path as the CLI (fetch diff + changed files via `gh`, optional T2 clone).
- **Paste**: source files pasted into the page. T0 scans them directly, T1 reviews a
  synthesized "new file" diff of them, and T2 runs over a temp checkout of just those
  files — so the whole pipeline is usable without `gh` or a real PR.

Binds to 127.0.0.1 by default and rejects cross-origin / foreign-Host requests, since a
local server that can spend the user's Anthropic credits shouldn't be drivable from an
arbitrary web page (the same DNS-rebinding class of bug the checklist itself flags).
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import click

from mcp_review.checklist import CHECKLIST
from mcp_review.engine import run_review
from mcp_review.llm.client import get_effort, get_model
from mcp_review.report import to_markdown
from mcp_review.static_rules.base import SourceFile

_MAX_BODY_BYTES = 5 * 1024 * 1024
_MAX_JOBS_KEPT = 50
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


@dataclass
class Job:
    id: str
    label: str
    mode: str
    options: dict
    status: str = "queued"  # queued | running | done | error
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    log: list[dict] = field(default_factory=list)
    stages: dict = field(default_factory=dict)
    result: dict | None = None
    markdown: str | None = None
    error: str | None = None

    def emit(self, message: str, level: str = "info") -> None:
        self.log.append({"t": time.time(), "level": level, "message": message})

    def summary(self) -> dict:
        findings = (self.result or {}).get("findings", [])
        return {
            "id": self.id,
            "label": self.label,
            "mode": self.mode,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "finding_count": len(findings) if self.result else None,
        }

    def to_dict(self) -> dict:
        return {
            **self.summary(),
            "options": self.options,
            "log": self.log,
            "stages": self.stages,
            "result": self.result,
            "markdown": self.markdown,
            "error": self.error,
        }


class JobStore:
    def __init__(self, max_workers: int = 2):
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mcp-review-job")

    def submit(self, job: Job, work) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            while len(self._jobs) > _MAX_JOBS_KEPT:
                self._jobs.popitem(last=False)
        self._pool.submit(_run_job, job, work)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(reversed(self._jobs.values()))


def _run_job(job: Job, work) -> None:
    job.status = "running"
    try:
        work(job)
        job.status = "done"
        job.emit("Review complete.")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        job.error = f"`{' '.join(map(str, exc.cmd[:3]))}` failed: {detail}"
        job.status = "error"
        job.emit(job.error, "error")
    except FileNotFoundError as exc:
        missing = exc.filename or str(exc)
        job.error = f"Required program not found: {missing}. Is it installed and on PATH?"
        job.status = "error"
        job.emit(job.error, "error")
    except Exception as exc:  # surfaced to the page instead of killing the worker
        job.error = f"{type(exc).__name__}: {exc}"
        job.status = "error"
        job.emit(job.error, "error")
        traceback.print_exc()
    finally:
        job.finished_at = time.time()


def _stage_recorder(job: Job):
    names = {"t0": "T0 static rules", "t1": "T1 Claude review", "t2": "T2 agentic review"}

    def on_stage(stage: str, payload) -> None:
        tier, _, phase = stage.partition(":")
        if phase == "start":
            job.stages[tier] = {"status": "running", "started_at": time.time()}
            job.emit(f"Running {names[tier]}...")
            return

        info = job.stages.setdefault(tier, {})
        info["status"] = "done"
        info["finished_at"] = time.time()
        if tier == "t0":
            info["findings"] = len(payload)
            job.emit(f"{names[tier]}: {len(payload)} finding(s).")
            return

        info["findings"] = len(payload.findings)
        info["input_tokens"] = payload.input_tokens
        info["output_tokens"] = payload.output_tokens
        info["refused"] = payload.refused
        if tier == "t2":
            info["turns"] = payload.turns
            info["hit_max_iterations"] = payload.hit_max_iterations
        if payload.refused:
            job.emit(f"{names[tier]} was refused ({payload.refusal_reason or 'no category'}); no findings from it.", "warn")
        else:
            job.emit(
                f"{names[tier]}: {len(payload.findings)} finding(s), "
                f"{payload.input_tokens:,} in / {payload.output_tokens:,} out tokens."
            )
        if getattr(payload, "hit_max_iterations", False):
            job.emit("T2 hit its iteration limit; findings may be incomplete.", "warn")

    return on_stage


def _finish(job: Job, result) -> None:
    job.result = result.to_dict()
    job.markdown = to_markdown(result)


def _pr_work(pr_ref: str, skip_llm: bool, agentic: bool):
    # Imported lazily so the UI still starts (and paste mode still works) on machines
    # without `gh` — these only shell out when a PR job actually runs.
    from mcp_review.cli import parse_pr_ref
    from mcp_review.diff import fetch_changed_source_files, fetch_pr_diff
    from mcp_review.repo import clone_pr_head

    def work(job: Job) -> None:
        pr = parse_pr_ref(pr_ref)
        job.emit(f"Fetching diff for {pr.slug}#{pr.number}...")
        diff_text = fetch_pr_diff(pr)
        job.emit("Fetching changed source files...")
        changed = fetch_changed_source_files(pr)
        job.emit(f"{len(changed)} changed source file(s) to scan.")
        on_stage = _stage_recorder(job)

        if agentic:
            job.emit("Cloning PR head for the T2 agentic pass...")
            with clone_pr_head(pr) as repo_root:
                result = run_review(
                    diff_text, changed, skip_llm=skip_llm, run_agentic=True, repo_root=repo_root, on_stage=on_stage
                )
        else:
            result = run_review(diff_text, changed, skip_llm=skip_llm, on_stage=on_stage)
        _finish(job, result)

    return work


def _safe_relative_path(raw: str) -> str:
    """Normalize a user-supplied filename to a relative path that can't escape a temp dir."""
    parts = [p for p in PurePosixPath(raw.replace("\\", "/")).parts if p not in ("", ".", "..", "/")]
    if not parts:
        raise ValueError(f"Invalid file path: {raw!r}")
    return "/".join(parts)


def synthesize_diff(files: list[SourceFile]) -> str:
    """A unified diff that adds every pasted file from scratch — T1's input in paste mode."""
    chunks: list[str] = []
    for f in files:
        lines = f.content.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        chunks.append(f"diff --git a/{f.path} b/{f.path}\nnew file mode 100644\n")
        chunks.extend(difflib.unified_diff([], lines, fromfile="/dev/null", tofile=f"b/{f.path}"))
    return "".join(chunks)


def _paste_work(files: list[SourceFile], diff_text: str, skip_llm: bool, agentic: bool):
    def work(job: Job) -> None:
        diff = diff_text.strip() and diff_text or synthesize_diff(files)
        job.emit(f"{len(files)} pasted file(s) to scan.")
        on_stage = _stage_recorder(job)

        if agentic:
            tmpdir = Path(tempfile.mkdtemp(prefix="mcp-review-ui-"))
            try:
                for f in files:
                    target = tmpdir / f.path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(f.content)
                result = run_review(
                    diff, files, skip_llm=skip_llm, run_agentic=True, repo_root=tmpdir, on_stage=on_stage
                )
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            result = run_review(diff, files, skip_llm=skip_llm, on_stage=on_stage)
        _finish(job, result)

    return work


def build_job(payload: dict) -> tuple[Job, object]:
    """Validate a POST /api/reviews body into a Job plus the callable that runs it."""
    mode = payload.get("mode")
    skip_llm = not payload.get("llm", True)
    agentic = bool(payload.get("agentic", False))
    if agentic and skip_llm:
        raise ValueError("The T2 agentic pass needs Claude — enable the T1 Claude pass too.")
    options = {"llm": not skip_llm, "agentic": agentic}
    job_id = uuid.uuid4().hex[:12]

    if mode == "pr":
        pr_ref = str(payload.get("pr_ref", "")).strip()
        if not pr_ref:
            raise ValueError("Enter a GitHub PR URL or owner/repo#number.")
        from mcp_review.cli import parse_pr_ref

        try:
            pr = parse_pr_ref(pr_ref)
        except click.BadParameter as exc:
            raise ValueError(exc.message) from exc
        label = f"{pr.slug}#{pr.number}"
        return Job(job_id, label, mode, options), _pr_work(pr_ref, skip_llm, agentic)

    if mode == "paste":
        raw_files = payload.get("files") or []
        files: list[SourceFile] = []
        for entry in raw_files:
            content = str(entry.get("content", ""))
            if not content.strip():
                continue
            files.append(SourceFile(path=_safe_relative_path(str(entry.get("path", "")) or "server.py"), content=content))
        diff_text = str(payload.get("diff", ""))
        if not files and not diff_text.strip():
            raise ValueError("Paste at least one source file or a diff.")
        label = ", ".join(f.path for f in files[:2]) + (f" +{len(files) - 2}" if len(files) > 2 else "")
        return Job(job_id, label or "pasted diff", mode, options), _paste_work(files, diff_text, skip_llm, agentic)

    raise ValueError(f"Unknown mode {mode!r}; expected 'pr' or 'paste'.")


def environment_status() -> dict:
    return {
        "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gh": shutil.which("gh") is not None,
        "git": shutil.which("git") is not None,
        "model": get_model(),
        "effort": get_effort(),
    }


def checklist_payload() -> list[dict]:
    return [
        {
            "id": item.id,
            "number": item.number,
            "category": item.category,
            "title": item.title,
            "tier": item.tier.value,
            "severity": item.severity.value,
            "confidence": item.confidence.value,
            "spec_ref": item.spec_ref,
            "description": item.description,
        }
        for item in CHECKLIST
    ]


def _index_html() -> bytes:
    return resources.files("mcp_review.web").joinpath("static/index.html").read_bytes()


class ReviewUIHandler(BaseHTTPRequestHandler):
    server_version = "mcp-review-ui"
    jobs: JobStore  # set by make_server

    def log_message(self, format: str, *args) -> None:  # quieter than the default per-request log
        if os.environ.get("MCP_REVIEW_UI_DEBUG"):
            super().log_message(format, *args)

    # --- request guards -------------------------------------------------------------

    def _host_allowed(self) -> bool:
        # Rejecting unknown Host headers is what defeats DNS rebinding against a local port.
        host = urlsplit("//" + (self.headers.get("Host") or "")).hostname or ""
        return host in _LOCAL_HOSTS or host == self.server.server_address[0]

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return urlsplit(origin).netloc == self.headers.get("Host")

    # --- responses ------------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    # --- routes ---------------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._host_allowed():
            return self._error(HTTPStatus.FORBIDDEN, "Host not allowed")
        path = urlsplit(self.path).path

        if path in ("/", "/index.html"):
            return self._send(HTTPStatus.OK, _index_html(), "text/html; charset=utf-8")
        if path == "/api/status":
            return self._json(HTTPStatus.OK, environment_status())
        if path == "/api/checklist":
            return self._json(HTTPStatus.OK, checklist_payload())
        if path == "/api/reviews":
            return self._json(HTTPStatus.OK, [job.summary() for job in self.jobs.list()])
        if path.startswith("/api/reviews/"):
            job = self.jobs.get(path.removeprefix("/api/reviews/"))
            if job is None:
                return self._error(HTTPStatus.NOT_FOUND, "No such review")
            return self._json(HTTPStatus.OK, job.to_dict())
        return self._error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if not self._host_allowed() or not self._origin_allowed():
            return self._error(HTTPStatus.FORBIDDEN, "Cross-origin request rejected")
        if urlsplit(self.path).path != "/api/reviews":
            return self._error(HTTPStatus.NOT_FOUND, "Not found")
        # Requiring a JSON content type means a plain HTML form on another site can't post here.
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Expected application/json")

        length = int(self.headers.get("Content-Length") or 0)
        if length > _MAX_BODY_BYTES:
            return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request too large")
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            job, work = build_job(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))

        self.jobs.submit(job, work)
        return self._json(HTTPStatus.ACCEPTED, job.summary())


def make_server(host: str = "127.0.0.1", port: int = 8765, jobs: JobStore | None = None) -> ThreadingHTTPServer:
    handler = type("BoundReviewUIHandler", (ReviewUIHandler,), {"jobs": jobs or JobStore()})
    return ThreadingHTTPServer((host, port), handler)


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind. Keep this local.")
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--open/--no-open", "open_browser", default=True, help="Open the UI in a browser on start.")
def main(host: str, port: int, open_browser: bool) -> None:
    """Launch the local web UI for the MCP review agent."""
    server = make_server(host, port)
    url = f"http://{'localhost' if host in _LOCAL_HOSTS else host}:{server.server_address[1]}/"
    if host not in _LOCAL_HOSTS:
        click.echo(
            f"Warning: binding to {host} exposes a server that can spend your Anthropic credits.", err=True
        )
    click.echo(f"MCP review UI running at {url}  (Ctrl+C to stop)", err=True)
    if open_browser:
        import webbrowser

        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
