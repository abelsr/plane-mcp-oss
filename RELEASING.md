# Releasing

This project publishes to PyPI automatically using
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). No API
token is stored in the repository or in CI secrets.

Publishing a GitHub Release triggers
[`.github/workflows/publish.yml`](.github/workflows/publish.yml), which runs the
tests, builds the sdist and wheel, and uploads them.

## One-time setup (already configured)

On PyPI, under *Account → Publishing → Trusted publishers*, the project
`plane-mcp-oss` is linked to:

| Field | Value |
|---|---|
| Owner | `abelsr` |
| Repository | `plane-mcp-oss` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

If any of those change (workflow renamed, repo transferred), update the
publisher or the upload will fail with an OIDC/`400` error.

## Release checklist

1. **Make sure `main` is green** — `gh run list --workflow ci.yml --limit 1`.

2. **Choose the version** (see [Versioning](#versioning) below).

3. **Bump the version** in `pyproject.toml`:

   ```toml
   version = "0.2.0"
   ```

4. **Refresh the lockfile** so it picks up the new version:

   ```bash
   uv lock
   ```

5. **Promote the changelog.** In `CHANGELOG.md`, move the entries under
   `## [Unreleased]` into a new dated section, and update the link definitions at
   the bottom:

   ```markdown
   ## [Unreleased]

   ## [0.2.0] - 2026-10-01

   ### Added
   - ...

   [Unreleased]: https://github.com/abelsr/plane-mcp-oss/compare/v0.2.0...HEAD
   [0.2.0]: https://github.com/abelsr/plane-mcp-oss/releases/tag/v0.2.0
   ```

6. **Verify the build locally:**

   ```bash
   uv sync --extra dev
   uv run pytest
   rm -rf dist && uv build
   uvx twine check dist/*
   ```

   Confirm the version in the artifact name and metadata:

   ```bash
   python - <<'PY'
   import glob, zipfile
   whl = sorted(glob.glob("dist/*.whl"))[-1]
   z = zipfile.ZipFile(whl)
   meta = z.read([n for n in z.namelist() if n.endswith("METADATA")][0]).decode()
   print("\n".join(l for l in meta.splitlines() if l.startswith(("Name:", "Version:"))))
   PY
   ```

7. **Commit and push:**

   ```bash
   git add -A
   git commit -m "Release 0.2.0"
   git push origin main
   ```

8. **Create the GitHub Release.** Publishing it is what triggers the upload:

   ```bash
   gh release create v0.2.0 --target main --title "v0.2.0" --notes "See CHANGELOG.md"
   ```

9. **Watch the publish run:**

   ```bash
   gh run list --workflow publish.yml --limit 1
   gh run watch "$(gh run list --workflow publish.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

10. **Verify on PyPI** (see below).

## Verifying a release

```bash
# 1. The release exists with both files
curl -s https://pypi.org/pypi/plane-mcp-oss/json \
  | python -c "import sys,json;d=json.load(sys.stdin);v=d['info']['version'];print(v,[f['filename'] for f in d['releases'][v]])"

# 2. Install it in a clean environment — from PyPI, not from the working tree
uv venv /tmp/verify && uv pip install --python /tmp/verify 'plane-mcp-oss==0.2.0'
/tmp/verify/bin/plane-mcp-oss --help
```

> ### Gotcha: PyPI / uv index cache lag
>
> Right after publishing, `uv` can still report
> `no version of plane-mcp-oss==X.Y.Z` for a minute or two even though the
> upload succeeded, because its package index cache is stale. Force a refresh:
>
> ```bash
> uv pip install --refresh plane-mcp-oss==X.Y.Z
> # or
> uvx --refresh plane-mcp-oss@X.Y.Z
> ```
>
> The PyPI JSON API can lag the same way. Confirm against the **publish workflow
> log** (`Uploading plane_mcp_oss-X.Y.Z.tar.gz` → `200 OK` → `View at: …`) before
> assuming a failure.

## Re-running a failed or partial publish

The upload step sets `skip-existing: true`, so re-running is safe: files that
already exist are skipped instead of erroring.

```bash
# Manually dispatch the workflow (also useful if the Release trigger was missed)
gh workflow run publish.yml --ref main
```

It builds from `main` at that moment, so only do this when `main` is on the
version you intend to publish.

If it fails on OIDC, the usual causes are a mismatched **environment name**,
**workflow filename**, or **repository** versus the PyPI trusted publisher
settings above.

## Versioning

[Semantic Versioning](https://semver.org/spec/v2.0.0.html), with pre-1.0
leniency:

| Change | Bump |
|---|---|
| Bug fix, docs, tool **descriptions** | patch (`0.1.0` → `0.1.1`) |
| New tool or non-breaking feature | minor (`0.1.1` → `0.2.0`) |
| Breaking change to a tool name, signature, or output shape | minor while `<1.0.0`, then major |

Notes:

- **A version can never be reused.** PyPI rejects re-uploading an existing
  filename, so a mistake means yanking and releasing the next patch.
- Tool descriptions ship inside the package and are what an LLM reads, so
  documentation-only changes to them are still worth a patch release.
- Keep the Git tag, the `pyproject.toml` version, and the changelog heading in
  agreement — `vX.Y.Z`.

## Yanking a bad release

If a published version is broken, **do not** delete and re-publish the same
version — that is impossible on PyPI. Instead:

1. PyPI → *Your projects* → `plane-mcp-oss` → *Manage* → *Releases* → **Yank** the
   version. Yanked releases are skipped by installers that do not pin a version,
   but remain available to anyone who pinned it.
2. Add a changelog entry explaining why.
3. Release the next patch version with the fix.
