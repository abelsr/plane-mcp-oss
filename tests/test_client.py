"""Offline tests for the Plane client, config and helpers.

Network is stubbed with httpx.MockTransport, so no credentials are required.
"""

from __future__ import annotations

import httpx
import pytest

from plane_mcp.client import PlaneAPIError, PlaneClient, summarize_paginated
from plane_mcp.config import ConfigError, Settings, normalize_base_url


def make_settings(**overrides) -> Settings:
    base = {
        "api_key": "plane_api_test",
        "workspace_slug": "my-team",
        "base_url": "https://api.plane.so/api/v1",
    }
    base.update(overrides)
    return Settings(**base)


def attach_transport(client: PlaneClient, handler) -> None:
    client._http = httpx.AsyncClient(
        base_url=client.settings.base_url,
        transport=httpx.MockTransport(handler),
        headers={"X-API-Key": client.settings.api_key or ""},
    )


# --------------------------------------------------------------------- config


def test_normalize_base_url_adds_api_v1():
    assert normalize_base_url("https://api.plane.so") == "https://api.plane.so/api/v1"
    assert normalize_base_url("https://api.plane.so/") == "https://api.plane.so/api/v1"
    assert normalize_base_url("https://api.plane.so/api/v1") == "https://api.plane.so/api/v1"
    assert normalize_base_url("plane.example.com") == "https://plane.example.com/api/v1"


def test_normalize_base_url_handles_self_hosted_shapes():
    # bare self-hosted host
    assert normalize_base_url("https://plane.example.com") == "https://plane.example.com/api/v1"
    # subpath install (Plane served under /plane)
    assert normalize_base_url("https://example.com/plane") == "https://example.com/plane/api/v1"
    assert normalize_base_url("https://example.com/plane/") == "https://example.com/plane/api/v1"
    # already versioned, with a trailing slash
    assert normalize_base_url("https://plane.example.com/api/v1/") == "https://plane.example.com/api/v1"
    # empty falls back to the default
    assert normalize_base_url("") == "https://api.plane.so/api/v1"


def test_settings_env_aliases():
    settings = Settings.from_env(
        {
            "PLANE_TOKEN": "alias-key",
            "PLANE_WORKSPACE": "alias-ws",
            "PLANE_URL": "https://plane.example.com",
        }
    )
    assert settings.api_key == "alias-key"
    assert settings.workspace_slug == "alias-ws"
    assert settings.base_url == "https://plane.example.com/api/v1"


def test_primary_env_names_win_over_aliases():
    settings = Settings.from_env(
        {"PLANE_API_KEY": "primary", "PLANE_TOKEN": "alias", "PLANE_WORKSPACE_SLUG": "ws"}
    )
    assert settings.api_key == "primary"


def test_settings_validate_requires_credentials():
    settings = Settings(workspace_slug="my-team", base_url="https://api.plane.so/api/v1")
    with pytest.raises(ConfigError, match="No Plane credentials"):
        settings.validate()


def test_settings_validate_requires_workspace():
    settings = Settings(workspace_slug="", base_url="https://api.plane.so/api/v1", api_key="k")
    with pytest.raises(ConfigError, match="PLANE_WORKSPACE_SLUG"):
        settings.validate()


def test_settings_from_env_defaults():
    settings = Settings.from_env({"PLANE_API_KEY": "k", "PLANE_WORKSPACE_SLUG": "ws"})
    assert settings.base_url == "https://api.plane.so/api/v1"
    assert settings.timeout == 30.0


# --------------------------------------------------------------------- client


async def test_list_projects_builds_request_and_summarizes():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["key"] = request.headers.get("X-API-Key")
        return httpx.Response(
            200,
            json={
                "count": 1,
                "total_results": 1,
                "next_cursor": "20:1:0",
                "results": [{"id": "p1", "name": "Website"}],
            },
        )

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    data = await client.list_projects(per_page=20, cursor=None)
    result = summarize_paginated(data)

    assert seen["method"] == "GET"
    assert seen["url"].endswith("/workspaces/my-team/projects/?per_page=20")
    assert seen["key"] == "plane_api_test"
    assert result["results"] == [{"id": "p1", "name": "Website"}]
    assert result["next_cursor"] == "20:1:0"
    await client.aclose()


async def test_create_work_item_wraps_plain_description():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "wi1"})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.create_work_item("p1", name="Fix login", description="Steps\nmore")

    assert captured["body"]["name"] == "Fix login"
    assert captured["body"]["description_html"] == "<p>Steps<br>more</p>"
    assert "description" not in captured["body"]
    await client.aclose()


async def test_oauth_token_uses_bearer_header():
    client = PlaneClient(make_settings(api_key=None, oauth_token="tok"))
    headers = client.http.headers
    assert headers["Authorization"] == "Bearer tok"
    assert "X-API-Key" not in headers
    await client.aclose()


async def test_self_hosted_subpath_is_used_in_requests():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"results": []})

    client = PlaneClient(make_settings(base_url="https://example.com/plane/api/v1"))
    attach_transport(client, handler)

    await client.list_projects()

    assert seen["url"].startswith("https://example.com/plane/api/v1/workspaces/my-team/projects/")
    await client.aclose()


async def test_search_work_items_uses_get_endpoint_with_query_params():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"issues": [{"id": "wi1", "name": "Logotipo"}]})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    data = await client.search_work_items(search="Logotipo", limit=5, workspace_search=True)

    assert seen["method"] == "GET"
    assert "/workspaces/my-team/work-items/search/" in seen["url"]
    assert "search=Logotipo" in seen["url"]
    assert "limit=5" in seen["url"]
    assert data["issues"][0]["name"] == "Logotipo"
    await client.aclose()


async def test_advanced_search_work_items_posts_filters():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[[]])

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.advanced_search_work_items(query="login", filters={"priority": "urgent"}, limit=10)

    assert captured["method"] == "POST"
    assert "/workspaces/my-team/work-items/advanced-search/" in captured["url"]
    assert captured["body"]["filters"] == {"priority": "urgent"}
    await client.aclose()


async def test_project_pages_use_project_scoped_paths():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"results": [{"id": "pg1", "name": "Docs"}]})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.list_pages(project_id="p1", page_type="public")

    assert seen["method"] == "GET"
    assert "/workspaces/my-team/projects/p1/pages/" in seen["url"]
    assert "type=public" in seen["url"]
    await client.aclose()


async def test_workspace_pages_omit_project_segment():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"results": []})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.list_pages(search="welcome")

    assert "/workspaces/my-team/pages/" in seen["url"]
    assert "/projects/" not in seen["url"]
    assert "search=welcome" in seen["url"]
    await client.aclose()


async def test_update_page_uses_put():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "pg1"})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.update_page("pg1", project_id="p1", name="Renamed")

    assert seen["method"] == "PUT"
    assert seen["url"].endswith("/workspaces/my-team/projects/p1/pages/pg1/")
    assert seen["body"] == {"name": "Renamed"}
    await client.aclose()


async def test_page_archive_restore_and_delete_paths():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        return httpx.Response(204)

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.archive_page("pg1", project_id="p1")
    await client.restore_page("pg1", project_id="p1")
    await client.delete_page("pg1", project_id="p1")

    assert calls[0] == ("POST", "https://api.plane.so/api/v1/workspaces/my-team/projects/p1/pages/pg1/archive/")
    assert calls[1] == ("DELETE", "https://api.plane.so/api/v1/workspaces/my-team/projects/p1/pages/pg1/archive/")
    assert calls[2] == ("DELETE", "https://api.plane.so/api/v1/workspaces/my-team/projects/p1/pages/pg1/")
    await client.aclose()


async def test_create_page_wraps_plain_description():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "pg1"})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.create_page(name="Spec", description="Hello\nworld", project_id="p1", access=0)

    assert captured["url"].endswith("/workspaces/my-team/projects/p1/pages/")
    assert captured["body"]["description_html"] == "<p>Hello<br>world</p>"
    assert captured["body"]["access"] == 0
    await client.aclose()


async def test_update_comment_uses_patch():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"id": "c1"})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.update_comment("p1", "wi1", "c1", comment="edited")

    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/workspaces/my-team/projects/p1/work-items/wi1/comments/c1/")
    assert "edited" in captured["body"]
    await client.aclose()


async def test_delete_comment_uses_delete():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        return httpx.Response(204)

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    await client.delete_comment("p1", "wi1", "c1")

    assert calls[0][0] == "DELETE"
    assert calls[0][1].endswith("/workspaces/my-team/projects/p1/work-items/wi1/comments/c1/")
    await client.aclose()


async def test_error_response_is_translated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid API key"})

    client = PlaneClient(make_settings())
    attach_transport(client, handler)

    with pytest.raises(PlaneAPIError) as excinfo:
        await client.me()

    assert excinfo.value.status_code == 401
    assert "Invalid API key" in str(excinfo.value)
    await client.aclose()


# -------------------------------------------------------------------- helpers


def test_summarize_paginated_handles_bare_list():
    assert summarize_paginated([1, 2, 3])["count"] == 3
