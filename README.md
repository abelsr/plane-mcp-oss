# Plane MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes the
[Plane](https://plane.so) REST API to AI clients (Claude, Cursor, VS Code,
Codex, …). Built with [FastMCP](https://gofastmcp.com).

It authenticates as a Plane personal access token and acts on a single
workspace, giving the model tools to read and manage projects, work items,
states, labels, cycles, modules, members and comments.

## Requirements

- Python 3.10+
- A Plane account and a **personal access token**:
  *Plane → Profile settings → Personal access tokens → Add personal access token*
- Your **workspace slug** — the segment in your Plane URL:
  `https://app.plane.so/<workspace-slug>/projects/`

## Install

```bash
uv sync            # installs fastmcp + httpx into .venv
# or, without uv:
pip install -e .
```

## Configure

The server targets one Plane **instance** and one **workspace**. Settings are
resolved with the following precedence (highest wins):

1. CLI flags (`--base-url`, `--workspace`, `--api-key`)
2. Process environment variables
3. A `.env` file in the working directory (loaded automatically)
4. Built-in defaults

| Variable | Alias | Required | Default | Purpose |
|---|---|---|---|---|
| `PLANE_API_KEY` | `PLANE_TOKEN` | yes* | — | Personal access token, sent as `X-API-Key`. |
| `PLANE_OAUTH_TOKEN` | — | yes* | — | OAuth access token, sent as `Authorization: Bearer …`. |
| `PLANE_WORKSPACE_SLUG` | `PLANE_WORKSPACE` | yes | — | Target workspace slug. |
| `PLANE_BASE_URL` | `PLANE_URL` | no | `https://api.plane.so` | Plane instance URL. |
| `PLANE_TIMEOUT` | — | no | `30` | Request timeout (seconds). |

\* One of `PLANE_API_KEY` / `PLANE_OAUTH_TOKEN` is required.

### Pointing at a self-hosted instance

`PLANE_BASE_URL` accepts whatever you copy from your browser. The `/api/v1`
suffix is added automatically when needed:

```bash
PLANE_BASE_URL=https://api.plane.so            # Plane Cloud (default)
PLANE_BASE_URL=https://plane.example.com       # self-hosted
PLANE_BASE_URL=https://example.com/plane       # self-hosted behind a subpath
PLANE_BASE_URL=https://plane.example.com/api/v1  # already versioned
```

### CLI flags

```bash
plane-mcp --base-url https://plane.example.com/plane \
          --workspace my-team \
          --api-key plane_api_xxxx
```

Check what the server resolved — without leaking the token:

```bash
$ plane-mcp --show-config --base-url https://plane.example.com/plane --workspace my-team --api-key xxx
{
  "base_url": "https://plane.example.com/plane/api/v1",
  "workspace_slug": "my-team",
  "auth": "api_key",
  "timeout": 30.0
}
```

Copy `.env.example` for a template; a `.env` file is loaded from the working
directory (change it with `--env-file`, or pass `--env-file ''` to skip).


## Run

```bash
# stdio — how MCP clients launch it locally
PLANE_API_KEY=... PLANE_WORKSPACE_SLUG=my-team uv run plane-mcp

# streamable HTTP
PLANE_API_KEY=... PLANE_WORKSPACE_SLUG=my-team uv run plane-mcp --transport http --port 8000
```

`python -m plane_mcp` and `python main.py` are equivalent entry points.

### Add to your MCP client

```json
{
  "mcpServers": {
    "plane": {
      "command": "uv",
      "args": ["--directory", "/path/to/plane-docmost-oss", "run", "plane-mcp"],
      "env": {
        "PLANE_API_KEY": "<your-token>",
        "PLANE_WORKSPACE_SLUG": "<your-workspace-slug>",
        "PLANE_BASE_URL": "https://api.plane.so"
      }
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `get_current_user` | Profile of the token's user. |
| `list_workspace_members` | Workspace members (to resolve assignee UUIDs). |
| `list_projects` / `get_project` | Browse projects (paginated). |
| `create_project` / `update_project` | Create or edit a project. |
| `list_work_items` / `get_work_item` | Browse work items in a project (paginated). |
| `get_work_item_by_identifier` | Look up e.g. `PROJ-123` directly. |
| `search_work_items` | Text search across names/identifiers (works everywhere). |
| `advanced_search_work_items` | Filter-based search; permission-gated, may return 403. |
| `create_work_item` / `update_work_item` / `delete_work_item` | Manage work items. |
| `list_states` | Workflow states — get the UUID before setting `state`. |
| `list_labels` / `create_label` | Project labels. |
| `list_cycles` / `list_modules` | Sprints and modules. |
| `list_comments` / `add_comment` / `update_comment` / `delete_comment` | Work item comments. |
| `list_pages` / `get_page` / `create_page` / `update_page` | Pages — workspace wiki or project (omit/ pass `project_id`). |
| `archive_page` / `restore_page` / `delete_page` | Page lifecycle; delete requires archiving first. |

List tools return `{results, count, total_results, next_cursor}`; pass
`next_cursor` back to page through results.

**Resources:** `plane://me`, `plane://projects`, `plane://projects/{id}/states`.
**Prompts:** `triage_work_items`.

### Notes on the API

- Work item `state`, `assignees` and `labels` take **UUIDs**, not names. Call
  `list_states` / `list_labels` / `list_workspace_members` first.
- `description` is plain text and is converted to the `description_html` the
  API expects; `description_html` overrides it when supplied.
- Priority is one of `urgent`, `high`, `medium`, `low`, `none`.
- The API allows 60 requests/minute per key; the client surfaces `429` as a
  tool error so the model can retry.

## Architecture

```
src/plane_mcp/
├── config.py   # env-driven Settings + validation
├── client.py   # async httpx wrapper: auth, URLs, error translation, pagination
├── server.py   # FastMCP instance, tool/resource/prompt definitions, CLI
└── __main__.py # `python -m plane_mcp`
tests/          # offline: httpx.MockTransport + in-memory FastMCP client
```

`client.py` has no FastMCP dependency, so it is reusable and easy to test; the
server layer only maps tools to client calls and turns `PlaneAPIError` into
`ToolError` for clean MCP error messages.

## Known limitations

- **Pages are Plane Cloud only.** The public Pages REST API is **not part of the
  open-source Community Edition** — it is absent from the API URL routing at
  `v1.3.1`, `v1.4.2` *and* `master` (`apps/api/plane/api/urls/` registers
  asset, cycle, intake, label, member, module, project, state, user, work_item,
  invite and sticky — no pages). On a self-hosted instance, pages exist in the
  UI behind an internal session API (`/api/…`) that rejects `X-API-Key` and
  Bearer tokens, so the page tools will 404 there. They work against Plane
  Cloud, where the documented `/api/v1/…/pages/` routes exist. The page tools
  detect this and return an explanatory error rather than a bare 404.
- **`advanced_search_work_items` is permission-gated** on some workspaces and
  editions and can return `403`. Use `search_work_items` or `list_work_items`
  as a fallback.
- **Not implemented yet:** work item links, attachments, activity feed, and
  custom properties/types, though the Plane API supports them.


## Development

```bash
uv run pytest        # 12 offline tests, no credentials needed
```

## Extending

Add a method to `PlaneClient` for the endpoint you need (see the
[API reference](https://developers.plane.so/api-reference/introduction)), then
register a tool in `server.py`:

```python
@mcp.tool
async def list_pages(project_id: str) -> dict[str, Any]:
    """List a project's pages."""
    client = get_client()
    data = await _call(client.request("GET", client._workspace("projects", project_id, "pages")))
    return summarize_paginated(data)
```

## License

MIT
