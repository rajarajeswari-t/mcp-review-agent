from pathlib import Path

from mcp_review.llm.t2_tools import T2ToolSet


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.py").write_text("def handle():\n    pass\n")
    (tmp_path / "src" / "auth.py").write_text(
        "def validate(token):\n    return jwt.decode(token, PUBLIC_KEY)\n"
    )
    (tmp_path / "README.md").write_text("# demo\n")
    return tmp_path


def test_list_files_returns_relative_paths(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    listing = tools.list_files("**/*.py")

    assert "src/server.py" in listing
    assert "src/auth.py" in listing
    assert "README.md" not in listing


def test_read_file_returns_content(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    content = tools.read_file("src/auth.py")

    assert "jwt.decode" in content


def test_read_file_blocks_path_traversal(tmp_path):
    repo = _make_repo(tmp_path)
    # A real secret living just outside the "repo" — the tool must never read it.
    (tmp_path.parent / "outside_secret.txt").write_text("super-secret-value")

    tools = T2ToolSet(repo)
    result = tools.read_file("../outside_secret.txt")

    assert "outside the repository root" in result
    assert "super-secret-value" not in result


def test_read_file_missing_file_returns_error(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    result = tools.read_file("does/not/exist.py")

    assert "not a file" in result


def test_grep_repo_finds_matches_with_line_numbers(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    result = tools.grep_repo(r"jwt\.decode")

    assert "src/auth.py:2:" in result


def test_grep_repo_invalid_regex_returns_error(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    result = tools.grep_repo(r"(unclosed[")

    assert "invalid regex" in result.lower()


def test_dispatch_routes_to_the_right_tool(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    result = tools.dispatch("read_file", {"path": "src/auth.py"})

    assert "jwt.decode" in result


def test_dispatch_unknown_tool_name(tmp_path):
    repo = _make_repo(tmp_path)
    tools = T2ToolSet(repo)

    result = tools.dispatch("delete_everything", {})

    assert "unknown tool" in result.lower()


def test_tool_schemas_match_dispatch_names():
    names = {schema["name"] for schema in T2ToolSet.tool_schemas()}
    assert names == {"list_files", "read_file", "grep_repo"}
