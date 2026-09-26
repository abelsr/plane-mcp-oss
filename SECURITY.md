# Security Policy

## Supported versions

The latest release on the `main` branch is supported. Fixes are applied there.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately using GitHub's
[Report a vulnerability](https://github.com/abelsr/plane-mcp-oss/security/advisories/new)
form, or email **abelsantillanrdz@gmail.com** with:

- a description of the issue and its impact,
- steps to reproduce (a tool call sequence is ideal),
- affected version/commit and your Plane edition if relevant.

You can expect an acknowledgement within a few days. Please allow time for a fix
and release before public disclosure.

## Scope

This project is an MCP server that talks to the Plane REST API. Relevant issues
include, for example:

- credential leakage (tokens, `.env`, logs),
- injection or unsafe handling of data returned by Plane,
- path/URL construction that could be redirected to an unintended host,
- denial of service through a crafted tool call.

Issues in Plane itself, or in the FastMCP/MCP stack, should be reported to those
projects upstream.

## Handling credentials

- Do **not** commit API keys or OAuth tokens. `.env` is git-ignored for this
  reason; keep it that way. `git check-ignore .env` should print the path.
- Prefer a personal access token scoped to a single workspace, and rotate it if
  it may have been exposed.
- `plane-mcp --show-config` prints the resolved configuration with the token
  redacted; it is safe to paste into a bug report.
