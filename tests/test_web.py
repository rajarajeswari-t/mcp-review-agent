import http.client
import json
import threading
import time

import pytest

from mcp_review.web.server import JobStore, build_job, make_server, synthesize_diff
from mcp_review.static_rules.base import SourceFile


@pytest.fixture
def server():
    srv = make_server("127.0.0.1", 0, JobStore(max_workers=1))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _request(server, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    hdrs = {"Host": f"127.0.0.1:{server.server_address[1]}", **(headers or {})}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=payload, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def _wait_for(server, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, data = _request(server, "GET", f"/api/reviews/{job_id}")
        job = json.loads(data)
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_index_and_checklist_served(server):
    status, data = _request(server, "GET", "/")
    assert status == 200 and b"<title>MCP Review</title>" in data

    status, data = _request(server, "GET", "/api/checklist")
    items = json.loads(data)
    assert status == 200 and len(items) == 24


def test_paste_review_runs_static_rules(server):
    body = {
        "mode": "paste",
        "llm": False,
        "files": [{"path": "srv.py", "content": 'uvicorn.run(app, host="0.0.0.0")\n'}],
    }
    status, data = _request(server, "POST", "/api/reviews", body)
    assert status == 202

    job = _wait_for(server, json.loads(data)["id"])
    assert job["status"] == "done", job["error"]
    assert any(f["rule_id"] == "bind-all-interfaces" for f in job["result"]["findings"])
    assert job["stages"]["t0"]["status"] == "done"
    assert "t1" not in job["stages"]
    assert job["markdown"].startswith("## MCP checklist review")

    _, data = _request(server, "GET", "/api/reviews")
    assert [j["id"] for j in json.loads(data)] == [job["id"]]


def test_rejects_foreign_host_and_cross_origin(server):
    status, _ = _request(server, "GET", "/api/status", headers={"Host": "evil.example:80"})
    assert status == 403

    body = {"mode": "paste", "llm": False, "files": [{"path": "a.py", "content": "x = 1"}]}
    status, _ = _request(server, "POST", "/api/reviews", body, headers={"Origin": "https://evil.example"})
    assert status == 403


def test_rejects_non_json_post(server):
    status, _ = _request(server, "POST", "/api/reviews", {"mode": "paste"}, headers={"Content-Type": "text/plain"})
    assert status == 415


def test_build_job_validation():
    with pytest.raises(ValueError):
        build_job({"mode": "pr", "pr_ref": "not a pr"})
    with pytest.raises(ValueError):
        build_job({"mode": "paste", "files": []})
    with pytest.raises(ValueError):
        build_job({"mode": "paste", "llm": False, "agentic": True, "files": [{"path": "a.py", "content": "x"}]})

    job, _ = build_job({"mode": "pr", "pr_ref": "https://github.com/o/r/pull/7", "llm": False})
    assert job.label == "o/r#7"


def test_pasted_paths_cannot_escape_temp_dir():
    job, _ = build_job({"mode": "paste", "llm": False, "files": [{"path": "../../etc/passwd", "content": "x"}]})
    assert job.label == "etc/passwd"


def test_synthesize_diff_adds_every_line():
    diff = synthesize_diff([SourceFile(path="a.py", content="one\ntwo")])
    assert "+++ b/a.py" in diff
    assert "+one\n+two\n" in diff
