# Contributing

Thanks for your interest in improving the Plane MCP server! This project is
small and friendly — issues and pull requests are welcome.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — open an issue; include your Plane edition/version
  (`GET /api/instances/` reports it) and the exact tool call.
- **Request an operation** — the server covers a subset of the Plane API. If a
  tool is missing, say which endpoint you need.
- **Add a tool** — see [Adding a tool](#adding-a-tool) below.
- **Improve docs** — corrections to the README, examples, and error messages.

## Development setup

Requirements: Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/abelsr/plane-mcp-oss.git
cd plane-mcp
uv sync --extra dev
```

Run the tests (they are fully offline — no Plane account required):

```bash
uv run pytest
```

Try the server against a workspace:

```bash
cp .env.example .env        # then fill in PLANE_API_KEY / PLANE_WORKSPACE_SLUG
uv run plane-mcp --show-config
uv run plane-mcp            # stdio; Ctrl-C to stop
```

> **Never commit real credentials.** `.env` is git-ignored; keep it that way.
> Tests use dummy tokens and `httpx.MockTransport`, so they never touch the
> network.

## Project layout

```
src/plane_mcp/
├── config.py    # env/.env/CLI settings + validation
├── client.py    # async httpx wrapper: auth, URLs, errors, pagination (no FastMCP)
├── server.py    # FastMCP tools/resources/prompts + CLI
└── __main__.py
tests/           # offline: httpx.MockTransport + in-memory FastMCP client
```

The split matters: `client.py` must not import FastMCP, so it stays reusable
and unit-testable. Keep API concerns there and tool wiring in `server.py`.

## Adding a tool

1. Add a method to `PlaneClient` in `client.py` using the helper that builds
   workspace paths, and raise-through `PlaneAPIError` (do not import FastMCP).

   ```python
   async def list_pages(self, *, project_id: str | None = None) -> dict[str, Any]:
       return await self.request("GET", self._pages_root(project_id))
   ```

2. Register the tool in `server.py`, wrapping the call with `_call` so failures
   become clean `ToolError`s, and write a docstring with an `Args:` section —
   MCP clients surface it directly to the model.

   ```python
   @mcp.tool
   async def list_pages(project_id: str | None = None) -> dict[str, Any]:
       """List pages.

       Args:
           project_id: Project UUID, or omit for workspace wiki pages.
       """
       client = get_client()
       data = await _call(client.list_pages(project_id=project_id))
       return summarize_paginated(data)
   ```

3. Add the tool name to `EXPECTED_TOOLS` in `tests/test_server.py`.
4. Add an offline test in `tests/test_client.py` that stubs the HTTP call and
   asserts the method, path, and body — see existing tests for the pattern.
5. Update the tool table in `README.md` and add a `CHANGELOG.md` entry.

## Style

- Keep the `ruff` defaults in mind (line length ~100, imports sorted); no
  formatter is enforced yet, so match the surrounding code.
- Prefer stdlib and the two runtime dependencies (`fastmcp`, `httpx`) over new
  packages. Discuss in an issue before adding a dependency.
- Public functions and tools get type hints and a docstring.

## Commit and PR guidelines

- Branch from `main`; keep pull requests focused on one change.
- Write imperative, descriptive commits (e.g. `Add cycle work item tools`).
- Ensure `uv run pytest` passes and CI is green.
- Describe **what** and **why** in the PR; reference the Plane endpoint you used.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
