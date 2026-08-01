"""One deliberate positive (bug present) diff+repo per T2 checklist item, plus negative
controls for the items most prone to false-positive noise (path/file handling and
consent-flow patterns show up in plenty of legitimate code, so those are worth the
extra API cost to check; the others get a positive case only, to keep this bounded).

Every case is genuinely multi-file — the whole point of T2 is that these can't be
judged from a diff alone, so a single-file case wouldn't actually test anything T1
couldn't already do.
"""

from __future__ import annotations

from evals.models import T2EvalCase

T2_CASES: list[T2EvalCase] = [
    # --- #1 capability-not-negotiated ---
    T2EvalCase(
        rule_id="capability-not-negotiated",
        name="capability_not_negotiated_bad",
        expect_finding=True,
        files={
            "capabilities.py": (
                "SERVER_CAPABILITIES = {\n"
                '    "tools": {"listChanged": True},\n'
                '    "resources": {},  # subscribe is NOT declared here\n'
                "}\n"
            ),
        },
        diff_text="""\
diff --git a/watcher.py b/watcher.py
new file mode 100644
--- /dev/null
+++ b/watcher.py
@@ -0,0 +1,6 @@
+async def on_file_changed(uri, send_notification):
+    # Fires a resource-update notification even though the server's declared
+    # capabilities never turned on resource subscriptions
+    await send_notification("notifications/resources/updated", {"uri": uri})
""",
    ),
    # --- #4 tool-input-not-validated ---
    T2EvalCase(
        rule_id="tool-input-not-validated",
        name="tool_input_not_validated_bad",
        expect_finding=True,
        files={
            "tools.py": (
                "DELETE_FILE_TOOL = Tool(\n"
                '    name="delete_file",\n'
                '    description="Delete a file from the workspace",\n'
                '    inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},\n'
                ")\n"
            ),
        },
        diff_text="""\
diff --git a/handlers.py b/handlers.py
new file mode 100644
--- /dev/null
+++ b/handlers.py
@@ -0,0 +1,7 @@
+import os
+
+def handle_delete_file(arguments):
+    path = arguments["path"]
+    os.remove(path)
+    return {"content": [{"type": "text", "text": f"Deleted {path}"}]}
""",
    ),
    T2EvalCase(
        rule_id="tool-input-not-validated",
        name="tool_input_not_validated_good",
        expect_finding=False,
        files={
            "tools.py": (
                "DELETE_FILE_TOOL = Tool(\n"
                '    name="delete_file",\n'
                '    description="Delete a file from the workspace",\n'
                '    inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},\n'
                ")\n"
            ),
        },
        diff_text="""\
diff --git a/handlers.py b/handlers.py
new file mode 100644
--- /dev/null
+++ b/handlers.py
@@ -0,0 +1,26 @@
+import os
+import time
+
+WORKSPACE_ROOT = "/srv/workspace"
+_recent_deletes_by_session = {}
+RATE_LIMIT_WINDOW_SECONDS = 60
+RATE_LIMIT_MAX_DELETES = 5
+
+def handle_delete_file(arguments, session):
+    path = arguments.get("path")
+    if not isinstance(path, str) or not path:
+        return {"content": [{"type": "text", "text": "Invalid path"}], "isError": True}
+    resolved = os.path.realpath(os.path.join(WORKSPACE_ROOT, path))
+    if not resolved.startswith(os.path.realpath(WORKSPACE_ROOT) + os.sep):
+        return {"content": [{"type": "text", "text": "Path escapes workspace"}], "isError": True}
+    if not session.owns_file(resolved):
+        return {"content": [{"type": "text", "text": "Not authorized to delete this file"}], "isError": True}
+    now = time.time()
+    recent = _recent_deletes_by_session.setdefault(session.id, [])
+    recent[:] = [t for t in recent if now - t < RATE_LIMIT_WINDOW_SECONDS]
+    if len(recent) >= RATE_LIMIT_MAX_DELETES:
+        return {"content": [{"type": "text", "text": "Rate limit exceeded"}], "isError": True}
+    recent.append(now)
+    os.remove(resolved)
+    return {"content": [{"type": "text", "text": f"Deleted {path}"}]}
""",
    ),
    # --- #9 unvalidated-resource-uri ---
    T2EvalCase(
        rule_id="unvalidated-resource-uri",
        name="unvalidated_resource_uri_bad",
        expect_finding=True,
        files={
            "server.py": (
                "BASE_DIR = '/srv/mcp-files'\n"
                "from resources import read_resource\n"
            ),
        },
        diff_text="""\
diff --git a/resources.py b/resources.py
new file mode 100644
--- /dev/null
+++ b/resources.py
@@ -0,0 +1,8 @@
+import os
+from server import BASE_DIR
+
+def read_resource(uri):
+    path = uri.replace("file://", "")
+    full_path = os.path.join(BASE_DIR, path.lstrip("/"))
+    with open(full_path) as f:
+        return f.read()
""",
    ),
    T2EvalCase(
        rule_id="unvalidated-resource-uri",
        name="unvalidated_resource_uri_good",
        expect_finding=False,
        files={
            "server.py": (
                "BASE_DIR = '/srv/mcp-files'\n"
                "from resources import read_resource\n"
            ),
        },
        diff_text="""\
diff --git a/resources.py b/resources.py
new file mode 100644
--- /dev/null
+++ b/resources.py
@@ -0,0 +1,12 @@
+import os
+from server import BASE_DIR
+
+def read_resource(uri):
+    path = uri.replace("file://", "")
+    base = os.path.realpath(BASE_DIR)
+    full_path = os.path.realpath(os.path.join(base, path.lstrip("/")))
+    if not full_path.startswith(base + os.sep):
+        raise ValueError("resource path escapes the allowed directory")
+    with open(full_path) as f:
+        return f.read()
""",
    ),
    # --- #10 roots-boundary-ignored ---
    T2EvalCase(
        rule_id="roots-boundary-ignored",
        name="roots_boundary_ignored_bad",
        expect_finding=True,
        files={
            "startup.py": (
                "ALLOWED_ROOTS = []\n\n"
                "async def initialize_roots(client_session):\n"
                "    global ALLOWED_ROOTS\n"
                "    result = await client_session.list_roots()\n"
                "    ALLOWED_ROOTS = [r.uri for r in result.roots]\n"
            ),
        },
        diff_text="""\
diff --git a/fileserver.py b/fileserver.py
new file mode 100644
--- /dev/null
+++ b/fileserver.py
@@ -0,0 +1,4 @@
+def read_file_resource(path):
+    # Never checks path against ALLOWED_ROOTS (from startup.py) before reading
+    with open(path) as f:
+        return f.read()
""",
    ),
    T2EvalCase(
        rule_id="roots-boundary-ignored",
        name="roots_boundary_ignored_good",
        expect_finding=False,
        files={
            "startup.py": (
                "ALLOWED_ROOTS = []\n\n"
                "async def initialize_roots(client_session):\n"
                "    global ALLOWED_ROOTS\n"
                "    result = await client_session.list_roots()\n"
                "    ALLOWED_ROOTS = [r.uri for r in result.roots]\n\n"
                "async def handle_initialize(client_session, request):\n"
                "    response = build_initialize_response(request)\n"
                "    await initialize_roots(client_session)\n"
                "    return response\n"
            ),
        },
        diff_text="""\
diff --git a/fileserver.py b/fileserver.py
new file mode 100644
--- /dev/null
+++ b/fileserver.py
@@ -0,0 +1,13 @@
+import os
+from startup import ALLOWED_ROOTS
+
+def read_file_resource(path):
+    resolved = os.path.realpath(path)
+    allowed = False
+    for root in ALLOWED_ROOTS:
+        root_path = os.path.realpath(root.removeprefix("file://"))
+        if resolved == root_path or resolved.startswith(root_path + os.sep):
+            allowed = True
+            break
+    if not allowed:
+        raise PermissionError("path is outside the client-declared roots")
+    with open(resolved) as f:
+        return f.read()
""",
    ),
    # --- #11 unnecessary-resource-proxying ---
    T2EvalCase(
        rule_id="unnecessary-resource-proxying",
        name="unnecessary_resource_proxying_bad",
        expect_finding=True,
        files={
            "server.py": "# MCP server exposing public documentation as a resource\n",
        },
        diff_text="""\
diff --git a/web_resources.py b/web_resources.py
new file mode 100644
--- /dev/null
+++ b/web_resources.py
@@ -0,0 +1,7 @@
+import requests
+
+def read_public_doc_resource(uri):
+    # "docs://intro" maps to a plain public webpage the client could fetch
+    # directly on its own -- no auth, no server-side value added
+    resp = requests.get("https://docs.example.com/intro.html")
+    return {"contents": [{"uri": uri, "mimeType": "text/html", "text": resp.text}]}
""",
    ),
    # --- #14 elicitation-misuse ---
    T2EvalCase(
        rule_id="elicitation-misuse",
        name="elicitation_misuse_bad",
        expect_finding=True,
        files={
            "elicitation_builder.py": (
                "def build_connect_url(user_session_token):\n"
                "    # Embeds the live session token directly in the URL sent to the user\n"
                '    return f"https://mcp.example.com/oauth/authorize?session={user_session_token}&client_id=abc"\n'
            ),
        },
        diff_text="""\
diff --git a/handlers.py b/handlers.py
new file mode 100644
--- /dev/null
+++ b/handlers.py
@@ -0,0 +1,5 @@
+from elicitation_builder import build_connect_url
+
+async def request_third_party_auth(client_session, user_session_token):
+    url = build_connect_url(user_session_token)
+    await client_session.elicit(mode="url", url=url)
""",
    ),
    # --- #20 token-passthrough ---
    T2EvalCase(
        rule_id="token-passthrough",
        name="token_passthrough_bad",
        expect_finding=True,
        files={
            "server.py": (
                "from fastapi import Request\n"
                "from upstream.client import call_upstream_api\n\n"
                "async def handle_tool_call(request: Request, tool_name: str, arguments: dict):\n"
                '    auth_header = request.headers.get("Authorization", "")\n'
                '    bearer_token = auth_header.removeprefix("Bearer ").strip()\n\n'
                '    if tool_name == "get_account_balance":\n'
                '        result = call_upstream_api(bearer_token, arguments["account_id"])\n'
                '        return {"content": [{"type": "text", "text": str(result)}]}\n'
            ),
        },
        diff_text="""\
diff --git a/upstream/client.py b/upstream/client.py
new file mode 100644
--- /dev/null
+++ b/upstream/client.py
@@ -0,0 +1,8 @@
+import requests
+
+def call_upstream_api(token: str, account_id: str):
+    resp = requests.get(
+        f"https://bank.example.com/api/accounts/{account_id}",
+        headers={"Authorization": f"Bearer {token}"},
+    )
+    return resp.json()
""",
    ),
    # --- #22 confused-deputy ---
    T2EvalCase(
        rule_id="confused-deputy",
        name="confused_deputy_bad",
        expect_finding=True,
        files={
            "proxy_config.py": (
                'STATIC_CLIENT_ID = "mcp-proxy-static-id"\n'
                'THIRD_PARTY_AUTHORIZE_URL = "https://thirdparty.example.com/authorize"\n'
            ),
        },
        diff_text="""\
diff --git a/auth_handler.py b/auth_handler.py
new file mode 100644
--- /dev/null
+++ b/auth_handler.py
@@ -0,0 +1,13 @@
+from proxy_config import STATIC_CLIENT_ID, THIRD_PARTY_AUTHORIZE_URL
+
+CLIENTS = {}
+
+def register_dynamic_client(redirect_uri):
+    # Any MCP client can dynamically register its own client_id + redirect_uri
+    new_client_id = generate_client_id()
+    CLIENTS[new_client_id] = {"redirect_uri": redirect_uri}
+    return new_client_id
+
+def handle_authorize_request(client_id, redirect_uri):
+    # Forwards straight to the third party using the static client id, with
+    # no per-client consent check before doing so
+    return redirect(f"{THIRD_PARTY_AUTHORIZE_URL}?client_id={STATIC_CLIENT_ID}&redirect_uri={redirect_uri}")
""",
    ),
    T2EvalCase(
        rule_id="confused-deputy",
        name="confused_deputy_good",
        expect_finding=False,
        files={
            "proxy_config.py": (
                'STATIC_CLIENT_ID = "mcp-proxy-static-id"\n'
                'THIRD_PARTY_AUTHORIZE_URL = "https://thirdparty.example.com/authorize"\n'
            ),
        },
        diff_text="""\
diff --git a/auth_handler.py b/auth_handler.py
new file mode 100644
--- /dev/null
+++ b/auth_handler.py
@@ -0,0 +1,40 @@
+from proxy_config import STATIC_CLIENT_ID, THIRD_PARTY_AUTHORIZE_URL
+
+CLIENTS = {}
+CONSENT_GIVEN = set()
+PENDING_THIRD_PARTY_AUTH = {}
+# The proxy's own fixed callback, pre-registered with the third party. The
+# dynamically-registered client's redirect_uri is never sent to the third
+# party at all, so it can never be hijacked at that hop.
+PROXY_OWN_CALLBACK_URL = "https://mcp-proxy.example.com/callback"
+
+def register_dynamic_client(redirect_uri):
+    if not redirect_uri.startswith("https://"):
+        raise ValueError("redirect_uri must use https")
+    new_client_id = generate_client_id()
+    CLIENTS[new_client_id] = {"redirect_uri": redirect_uri}
+    return new_client_id
+
+def handle_authorize_request(user_id, client_id, redirect_uri):
+    if CLIENTS.get(client_id, {}).get("redirect_uri") != redirect_uri:
+        raise ValueError("redirect_uri does not match the one registered for this client_id")
+    if (user_id, client_id) not in CONSENT_GIVEN:
+        return show_consent_screen(client_id, redirect_uri)
+    return _forward_to_third_party(user_id, client_id)
+
+def handle_consent_approval(user_id, client_id, redirect_uri):
+    if CLIENTS.get(client_id, {}).get("redirect_uri") != redirect_uri:
+        raise ValueError("redirect_uri does not match the one registered for this client_id")
+    CONSENT_GIVEN.add((user_id, client_id))
+    return _forward_to_third_party(user_id, client_id)
+
+def _forward_to_third_party(user_id, client_id):
+    state = generate_secure_random_state()
+    PENDING_THIRD_PARTY_AUTH[state] = (user_id, client_id)
+    return redirect(
+        f"{THIRD_PARTY_AUTHORIZE_URL}?client_id={STATIC_CLIENT_ID}"
+        f"&redirect_uri={PROXY_OWN_CALLBACK_URL}&state={state}"
+    )
+
+def handle_third_party_callback(state, third_party_code):
+    user_id, client_id = PENDING_THIRD_PARTY_AUTH.pop(state)
+    third_party_token = exchange_code_for_token(third_party_code)
+    mcp_auth_code = issue_mcp_authorization_code(user_id, third_party_token)
+    client_redirect_uri = CLIENTS[client_id]["redirect_uri"]
+    return redirect(f"{client_redirect_uri}?code={mcp_auth_code}")
""",
    ),
]
