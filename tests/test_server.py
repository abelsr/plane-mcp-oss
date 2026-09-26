"""Verify the MCP surface is registered correctly.

These run fully in-memory through FastMCP's Client — no network, no creds.
"""

from __future__ import annotations

import os

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from plane_mcp.config import Settings
from plane_mcp.server import _access_code, _apply_cli_overrides, _load_environment, mcp

EXPECTED_TOOLS = {
    "get_current_user",
    "list_workspace_members",
    "list_projects",
    "get_project",
    "create_project",
    "update_project",
    "list_work_items",
    "get_work_item",
    "get_work_item_by_identifier",
    "search_work_items",
    "advanced_search_work_items",
    "create_work_item",
    "update_work_item",
    "delete_work_item",
    "list_states",
    "list_labels",
    "create_label",
    "list_cycles",
    "list_modules",
    "list_comments",
    "add_comment",
    "update_comment",
    "delete_comment",
    "list_pages",
    "get_page",
    "create_page",
    "update_page",
    "archive_page",
    "restore_page",
    "delete_page",
}


async def test_all_tools_are_registered():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert EXPECTED_TOOLS <= names, EXPECTED_TOOLS - names


async def test_tool_schemas_expose_required_arguments():
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    create = tools["create_work_item"]
    schema = create.input_schema if hasattr(create, "input_schema") else create.inputSchema
    required = set(schema.get("required", []))
    assert {"project_id", "name"} <= required

    assert "search the whole workspace" not in tools["list_work_items"].description


async def test_resources_are_registered():
    async with Client(mcp) as client:
        resources = await client.list_resources()
    uris = {str(resource.uri) for resource in resources}
    assert "plane://me" in uris
    assert "plane://projects" in uris


# ------------------------------------------------------------- configuration


def test_cli_overrides_win_over_environment(monkeypatch):
    monkeypatch.setenv("PLANE_BASE_URL", "https://from-env.example.com")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "env-ws")
    monkeypatch.setenv("PLANE_API_KEY", "env-key")

    _apply_cli_overrides("https://from-cli.example.com", "cli-ws", "cli-key")

    settings = Settings.from_env()
    assert settings.base_url == "https://from-cli.example.com/api/v1"
    assert settings.workspace_slug == "cli-ws"
    assert settings.api_key == "cli-key"


def test_env_file_is_loaded_but_not_override_process_env(tmp_path, monkeypatch):
    # Isolate os.environ so load_dotenv's writes are reverted after the test.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    for name in ("PLANE_BASE_URL", "PLANE_WORKSPACE_SLUG", "PLANE_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "PLANE_BASE_URL=https://from-dotenv.example.com\n"
        "PLANE_WORKSPACE_SLUG=dotenv-ws\n"
        "PLANE_API_KEY=dotenv-key\n"
    )

    _load_environment(str(env_file))
    settings = Settings.from_env()
    assert settings.base_url == "https://from-dotenv.example.com/api/v1"
    assert settings.workspace_slug == "dotenv-ws"
    assert settings.api_key == "dotenv-key"

    # A real environment variable must beat the .env file.
    monkeypatch.setenv("PLANE_BASE_URL", "https://from-env.example.com")
    _load_environment(str(env_file))
    assert Settings.from_env().base_url == "https://from-env.example.com/api/v1"


def test_load_environment_ignores_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    for name in ("PLANE_BASE_URL", "PLANE_WORKSPACE_SLUG"):
        monkeypatch.delenv(name, raising=False)

    _load_environment(str(tmp_path / "does-not-exist.env"))

    assert "PLANE_BASE_URL" not in os.environ


def test_redacted_hides_credentials():
    settings = Settings(workspace_slug="ws", base_url="https://api.plane.so/api/v1", api_key="super-secret")
    view = settings.redacted()
    assert view["auth"] == "api_key"
    assert "super-secret" not in str(view)


# ------------------------------------------------------------------- pages


def test_access_code_mapping():
    assert _access_code("public") == 0
    assert _access_code("PRIVATE") == 1
    assert _access_code(" private ") == 1
    assert _access_code(0) == 0
    assert _access_code("1") == 1
    with pytest.raises(ToolError):
        _access_code("secret")


# ------------------------------------------------------- description quality


async def test_every_tool_has_a_description():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    undocumented = [t.name for t in tools if not (t.description or "").strip()]
    assert not undocumented, f"tools without a description: {undocumented}"


async def test_every_tool_parameter_is_documented():
    """LLMs pick arguments from the JSON schema, so each one needs a description.

    FastMCP lifts the docstring's `Args:` block into the schema; a parameter
    missing from that block reaches the model as a bare name.
    """
    async with Client(mcp) as client:
        tools = await client.list_tools()

    undocumented: list[str] = []
    for tool in tools:
        schema = tool.input_schema if hasattr(tool, "input_schema") else tool.inputSchema
        for name, spec in schema.get("properties", {}).items():
            if not spec.get("description"):
                undocumented.append(f"{tool.name}.{name}")

    assert not undocumented, f"parameters without a description: {undocumented}"


async def test_destructive_tools_warn_they_are_irreversible():
    async with Client(mcp) as client:
        tools = {t.name: (t.description or "") for t in await client.list_tools()}

    for name in ("delete_work_item", "delete_comment", "delete_page"):
        assert "cannot be undone" in tools[name].lower(), f"{name} should warn about permanence"


async def test_create_page_requires_a_body():
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="description"):
            await client.call_tool("create_page", {"name": "No body"})


async def test_update_page_requires_a_field():
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="at least one"):
            await client.call_tool("update_page", {"page_id": "pg1"})
