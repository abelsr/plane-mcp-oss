# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-25

### Added

- FastMCP server exposing the Plane REST API over stdio, HTTP, and SSE.
- Configuration from environment variables, a `.env` file, or CLI flags, with
  precedence and aliases (`PLANE_URL`, `PLANE_WORKSPACE`, `PLANE_TOKEN`); self-hosted
  URL normalization (subpaths, trailing slashes, versioned URLs).
- `--show-config` to print the resolved configuration with secrets redacted.
- Tools for projects, work items, states, labels, cycles, modules, workspace
  members, the current user, and work item comments (create/list/update/delete).
- Tools for pages — workspace wiki and project pages — with the full
  create/update/archive/restore/delete lifecycle.
- `search_work_items` (public search endpoint) and
  `advanced_search_work_items` (permission-gated).
- MCP resources `plane://me`, `plane://projects`,
  `plane://projects/{project_id}/states` and the `triage_work_items` prompt.
- 32 offline tests using `httpx.MockTransport` and an in-memory FastMCP client.

### Notes

- The public Pages REST API is **Plane Cloud only**; it is absent from the
  open-source Community Edition, so the page tools return an explanatory error
  there.
- `advanced_search_work_items` may return 403 depending on workspace permissions.

[Unreleased]: https://github.com/abelsr/plane-mcp-oss/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/abelsr/plane-mcp-oss/releases/tag/v0.1.0
