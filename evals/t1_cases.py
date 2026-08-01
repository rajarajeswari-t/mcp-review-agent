"""One deliberate positive (bug present) and negative (clean) diff per T1 checklist
item. Each is hand-crafted to demonstrate exactly one mistake as unambiguously as
possible — these are not meant to be subtle or adversarial, just a first real check
that each rule can fire at all.
"""

from __future__ import annotations

from evals.models import T1EvalCase

T1_CASES: list[T1EvalCase] = [
    # --- #2 handshake-order-violation ---
    T1EvalCase(
        rule_id="handshake-order-violation",
        name="handshake_order_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/server.py b/server.py
index 1111111..2222222 100644
--- a/server.py
+++ b/server.py
@@ -8,6 +8,11 @@ async def handle_message(msg):
     if msg["method"] == "initialize":
         response = build_initialize_response(msg)
         await send_message(response)
+        # Let the client know about our tools right away, before it has even
+        # sent notifications/initialized back to us
+        await send_message({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
         return
""",
    ),
    T1EvalCase(
        rule_id="handshake-order-violation",
        name="handshake_order_good",
        expect_finding=False,
        diff_text="""\
diff --git a/server.py b/server.py
index 1111111..2222222 100644
--- a/server.py
+++ b/server.py
@@ -8,6 +8,15 @@ async def handle_message(msg):
     if msg["method"] == "initialize":
         response = build_initialize_response(msg)
         await send_message(response)
         return
+
+    if msg["method"] == "notifications/initialized":
+        global client_ready
+        client_ready = True
+        return
+
+    if msg["method"] == "internal/tool_registered" and client_ready:
+        await send_message({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
+        return
""",
    ),
    # --- #5 error-channel-conflation ---
    T1EvalCase(
        rule_id="error-channel-conflation",
        name="error_channel_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/server.py b/server.py
index 1234567..89abcde 100644
--- a/server.py
+++ b/server.py
@@ -10,6 +10,20 @@ async def handle_call_tool(name, arguments):
     if name == "book_flight":
         date = arguments["date"]
         if not is_valid_future_date(date):
-            return {"content": [{"type": "text", "text": "Invalid date"}], "isError": True}
+            raise JSONRPCError(code=-32602, message="Invalid departure date: must be in the future")
         return book_flight(date)
""",
    ),
    T1EvalCase(
        rule_id="error-channel-conflation",
        name="error_channel_good",
        expect_finding=False,
        diff_text="""\
diff --git a/server.py b/server.py
index 1234567..89abcde 100644
--- a/server.py
+++ b/server.py
@@ -10,6 +10,10 @@ async def handle_call_tool(name, arguments):
     if name == "book_flight":
         date = arguments["date"]
         if not is_valid_future_date(date):
-            return {"content": [{"type": "text", "text": "invalid"}], "isError": True}
+            return {
+                "content": [{"type": "text", "text": f"Invalid departure date {date}: must be in the future"}],
+                "isError": True,
+            }
         return book_flight(date)
""",
    ),
    # --- #7 output-schema-drift ---
    T1EvalCase(
        rule_id="output-schema-drift",
        name="output_schema_drift_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/weather_tool.py b/weather_tool.py
index 1111111..2222222 100644
--- a/weather_tool.py
+++ b/weather_tool.py
@@ -1,4 +1,4 @@
-WEATHER_TOOL = Tool(
+WEATHER_TOOL = Tool(
     name="get_weather_data",
     description="Get current weather data for a location",
     inputSchema={
@@ -14,10 +14,10 @@ WEATHER_TOOL = Tool(
         },
         "required": ["temperature", "conditions", "humidity"],
     },
 )

 async def call_weather_tool(args):
     data = fetch_weather(args["location"])
-    return {"structuredContent": {"temperature": data.temp, "conditions": data.desc, "humidity": data.humidity}}
+    return {"structuredContent": {"temperature": data.temp, "conditions": data.desc}}
""",
    ),
    T1EvalCase(
        rule_id="output-schema-drift",
        name="output_schema_drift_good",
        expect_finding=False,
        diff_text="""\
diff --git a/weather_tool.py b/weather_tool.py
index 1111111..2222222 100644
--- a/weather_tool.py
+++ b/weather_tool.py
@@ -14,7 +14,8 @@ WEATHER_TOOL = Tool(

 async def call_weather_tool(args):
     data = fetch_weather(args["location"])
+    humidity = data.humidity if data.humidity is not None else 0
     return {
-        "structuredContent": {"temperature": data.temp, "conditions": data.desc, "humidity": data.humidity}
+        "structuredContent": {"temperature": data.temp, "conditions": data.desc, "humidity": humidity}
     }
""",
    ),
    # --- #12 resource-template-mismatch ---
    T1EvalCase(
        rule_id="resource-template-mismatch",
        name="resource_template_mismatch_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/resources.py b/resources.py
index 1111111..2222222 100644
--- a/resources.py
+++ b/resources.py
@@ -1,6 +1,15 @@
 RESOURCE_TEMPLATES = [
     {
         "uriTemplate": "file:///{path}",
         "name": "Project Files",
+        "description": "Access files in the project directory",
     }
 ]
+
+async def read_resource(uri):
+    # Always serves the same fixed file regardless of the {path} the client asked for
+    with open("/srv/data/default.txt") as f:
+        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f.read()}]}
""",
    ),
    T1EvalCase(
        rule_id="resource-template-mismatch",
        name="resource_template_mismatch_good",
        expect_finding=False,
        diff_text="""\
diff --git a/resources.py b/resources.py
index 1111111..2222222 100644
--- a/resources.py
+++ b/resources.py
@@ -1,6 +1,17 @@
 RESOURCE_TEMPLATES = [
     {
         "uriTemplate": "file:///{path}",
         "name": "Project Files",
+        "description": "Access files in the project directory",
     }
 ]
+
+async def read_resource(uri):
+    path = uri.removeprefix("file://")
+    resolved = safe_resolve_within_project_dir(path)
+    with open(resolved) as f:
+        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f.read()}]}
""",
    ),
    # --- #13 sampling-misuse ---
    T1EvalCase(
        rule_id="sampling-misuse",
        name="sampling_misuse_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/agent_loop.py b/agent_loop.py
index 1111111..2222222 100644
--- a/agent_loop.py
+++ b/agent_loop.py
@@ -0,0 +1,12 @@
+async def run_tool_loop(client_session, messages):
+    while True:
+        result = await client_session.create_message(messages=messages, tools=AVAILABLE_TOOLS)
+        if result.stopReason == "toolUse":
+            tool_output = execute_tool(result.content[0])
+            # Reply doesn't carry a ToolResultContent tagged with the matching
+            # toolUseId, and there's no cap on how many times this loop can run
+            messages.append({"role": "user", "content": [{"type": "text", "text": str(tool_output)}]})
+        else:
+            return result
""",
    ),
    T1EvalCase(
        rule_id="sampling-misuse",
        name="sampling_misuse_good",
        expect_finding=False,
        diff_text="""\
diff --git a/agent_loop.py b/agent_loop.py
index 1111111..2222222 100644
--- a/agent_loop.py
+++ b/agent_loop.py
@@ -0,0 +1,16 @@
+MAX_TOOL_LOOP_ITERATIONS = 10
+
+async def run_tool_loop(client_session, messages):
+    for _ in range(MAX_TOOL_LOOP_ITERATIONS):
+        result = await client_session.create_message(messages=messages, tools=AVAILABLE_TOOLS)
+        if result.stopReason != "toolUse":
+            return result
+        tool_use = result.content[0]
+        tool_output = execute_tool(tool_use)
+        messages.append({
+            "role": "user",
+            "content": [{"type": "toolResult", "toolUseId": tool_use.id, "content": [{"type": "text", "text": str(tool_output)}]}],
+        })
+    raise RuntimeError("tool loop exceeded max iterations")
""",
    ),
    # --- #15 list-changed-not-fired ---
    T1EvalCase(
        rule_id="list-changed-not-fired",
        name="list_changed_not_fired_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/server.py b/server.py
index 1111111..2222222 100644
--- a/server.py
+++ b/server.py
@@ -1,8 +1,13 @@
+CAPABILITIES = {
+    "tools": {"listChanged": True}
+}
+
 REGISTERED_TOOLS = []

+def register_plugin_tool(tool):
+    REGISTERED_TOOLS.append(tool)
+    # New tool is now available immediately, but the client is never told
+    # its tools/list is stale
""",
    ),
    T1EvalCase(
        rule_id="list-changed-not-fired",
        name="list_changed_not_fired_good",
        expect_finding=False,
        diff_text="""\
diff --git a/server.py b/server.py
index 1111111..2222222 100644
--- a/server.py
+++ b/server.py
@@ -1,8 +1,15 @@
+CAPABILITIES = {
+    "tools": {"listChanged": True}
+}
+
 REGISTERED_TOOLS = []

+async def register_plugin_tool(tool):
+    REGISTERED_TOOLS.append(tool)
+    await send_notification({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
""",
    ),
    # --- #19 weak-session-auth ---
    T1EvalCase(
        rule_id="weak-session-auth",
        name="weak_session_auth_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/session.py b/session.py
index 1111111..2222222 100644
--- a/session.py
+++ b/session.py
@@ -1,3 +1,17 @@
+_next_id = 1000
+ACTIVE_SESSIONS = set()
+
+def create_session():
+    global _next_id
+    _next_id += 1
+    session_id = str(_next_id)
+    ACTIVE_SESSIONS.add(session_id)
+    return session_id
+
+def authenticate_request(request):
+    # A request is treated as authenticated purely because it carries a
+    # session ID that happens to be in the active set
+    return request.headers.get("MCP-Session-Id") in ACTIVE_SESSIONS
""",
    ),
    T1EvalCase(
        rule_id="weak-session-auth",
        name="weak_session_auth_good",
        expect_finding=False,
        diff_text="""\
diff --git a/session.py b/session.py
index 1111111..2222222 100644
--- a/session.py
+++ b/session.py
@@ -1,3 +1,18 @@
+import secrets
+
+SESSIONS_BY_USER = {}
+
+def create_session(authenticated_user_id):
+    session_id = secrets.token_urlsafe(32)
+    SESSIONS_BY_USER[session_id] = authenticated_user_id
+    return session_id
+
+def authenticate_request(request):
+    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
+    user = verify_oauth_token(token)
+    session_id = request.headers.get("MCP-Session-Id")
+    return SESSIONS_BY_USER.get(session_id) == user.id
""",
    ),
    # --- #23 non-opaque-cursors ---
    T1EvalCase(
        rule_id="non-opaque-cursors",
        name="non_opaque_cursors_bad",
        expect_finding=True,
        diff_text="""\
diff --git a/pagination.py b/pagination.py
index 1111111..2222222 100644
--- a/pagination.py
+++ b/pagination.py
@@ -0,0 +1,7 @@
+def list_resources(cursor=None):
+    page = int(cursor) if cursor else 0
+    start = page * PAGE_SIZE
+    items = ALL_RESOURCES[start:start + PAGE_SIZE]
+    next_cursor = str(page + 1) if start + PAGE_SIZE < len(ALL_RESOURCES) else None
+    return {"resources": items, "nextCursor": next_cursor}
""",
    ),
    T1EvalCase(
        rule_id="non-opaque-cursors",
        name="non_opaque_cursors_good",
        expect_finding=False,
        diff_text="""\
diff --git a/pagination.py b/pagination.py
index 1111111..2222222 100644
--- a/pagination.py
+++ b/pagination.py
@@ -0,0 +1,16 @@
+from cryptography.fernet import Fernet, InvalidToken
+
+# Symmetric encryption, not just signing -- the cursor's internal structure
+# (a page offset) is not readable by anyone without ENCRYPTION_KEY, unlike a
+# merely-signed value which stays plaintext-visible even though tamper-proof.
+_fernet = Fernet(ENCRYPTION_KEY)
+
+def list_resources(cursor=None):
+    try:
+        offset = int(_fernet.decrypt(cursor.encode()).decode()) if cursor else 0
+    except (InvalidToken, ValueError):
+        raise JSONRPCError(code=-32602, message="Invalid cursor")
+    items = ALL_RESOURCES[offset:offset + PAGE_SIZE]
+    more = offset + PAGE_SIZE < len(ALL_RESOURCES)
+    next_cursor = _fernet.encrypt(str(offset + PAGE_SIZE).encode()).decode() if more else None
+    return {"resources": items, "nextCursor": next_cursor}
""",
    ),
]
