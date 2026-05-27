# extensions-ci

Shared CI infrastructure for Grimoire extension repositories. Provides reusable
GitHub Actions workflows and composite actions that any repo shaped like
`grimoire-extensions` (i.e. `src/{lang}/{name}/build.gradle.kts` per extension,
optional `lib/`) can consume.

This repo is a peer of the extension repos that consume it — not a parent.
There are intentionally no consumer-specific values baked in; everything that
varies is inferred from the caller's `github.*` context or passed via inputs.

## What's here

```
.github/workflows/
  pr-build.yml         on: workflow_call  — build + sign + publish PR preview release
  pr-cleanup.yml       on: workflow_call  — delete pr-<N> release when the PR closes
  release.yml          on: workflow_call  — build, sign, release on push to main
.github/actions/
  detect-pr-changes/   composite — diff a PR, emit affected modules
  detect-changes/      composite — diff vs published index.json, emit matrix
  generate-index/      composite — produce merged index.json from built APKs
  comment-pr-preview/  composite — post/update the sticky magic-link PR comment
scripts/
  detect_pr_changes.py
  detect_changes.py
  generate_index.py
  comment_pr_preview.py
```

The Python scripts honor `REPO_ROOT` (set by the composite actions to
`${{ github.workspace }}`), so they operate on the *caller's* checkout. Without
`REPO_ROOT` they fall back to their on-disk parent — local invocations from a
checkout of an extensions repo still work the way they always have.

## v1 contract

### Calling the PR workflow

```yaml
# .github/workflows/pr-build.yml (in your extensions repo)
name: PR Build (preview)
on:
  pull_request:
    branches: [main]
jobs:
  pr-build:
    uses: operation-grimoire/extensions-ci/.github/workflows/pr-build.yml@v1
    secrets: inherit
    permissions:
      contents: write        # publish the pr-<N> prerelease
      packages: read         # pull `lib/` from GitHub Packages
      pull-requests: write   # post the sticky magic-link comment
```

Each PR push runs the same build/sign recipe as `release.yml` on the modules
the PR touches, then:

1. Publishes the signed APKs + a merged `index.json` to a `pr-<N>` prerelease
   (rebuilt on every push, so the assets always reflect the PR head).
2. Posts (or updates) a sticky comment on the PR with a
   `https://grimoireapp.org/add-repo?...` magic link — tap it on Android and
   Grimoire opens with the Add Repository dialog pre-filled with the
   preview's `index.json` URL.

The preview's `index.json` only lists the PR-touched extensions — reviewers
already have the production repo added, and merging in every production
entry would just spawn phantom "update available" prompts on extensions
installed from production.

Inputs (all optional): `java-version` (default `"17"`), `runs-on` (default
`ubuntu-latest`).

Required secrets (passed via `secrets: inherit`): `SIGNING_KEY`,
`KEY_STORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`. PRs from forks don't
receive these secrets and so don't get a preview — only same-repo PRs do.

### Calling the PR cleanup workflow

Pair `pr-build.yml` with `pr-cleanup.yml` so closed PRs don't leave stale
preview releases lying around:

```yaml
# .github/workflows/pr-cleanup.yml (in your extensions repo)
name: PR preview cleanup
on:
  pull_request:
    types: [closed]
    branches: [main]
jobs:
  pr-cleanup:
    uses: operation-grimoire/extensions-ci/.github/workflows/pr-cleanup.yml@v1
    secrets: inherit
    permissions:
      contents: write
```

### Calling the release workflow

```yaml
# .github/workflows/release.yml (in your extensions repo)
name: Build & Release Extensions
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      chunk_size:
        required: false
        default: "4"
      force_all:
        required: false
        type: boolean
        default: false
jobs:
  release:
    uses: operation-grimoire/extensions-ci/.github/workflows/release.yml@v1
    secrets: inherit
    permissions:
      contents: write
      packages: read
    with:
      chunk_size: ${{ inputs.chunk_size || '4' }}
      force_all:  ${{ inputs.force_all  || false }}
```

Inputs: `chunk_size` (string, default `"4"`), `force_all` (boolean, default
`false`), `java-version`, `runs-on`.

Required secrets (passed via `secrets: inherit`): `SIGNING_KEY`,
`KEY_STORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`. `GITHUB_TOKEN` is provided
automatically.

### Repo shape the consumers must satisfy

- `src/{lang}/{name}/build.gradle.kts` per extension, with `applicationId`,
  `versionCode`, `versionName` declared in `defaultConfig`. `settings.gradle.kts`
  must include each one as `:{lang}-{name}`.
- An `@SourceInfo(name = ..., lang = ..., baseUrl = ...)` annotation somewhere
  under each extension's Kotlin source.
- A `repo/{lang}-{name}.apk` lands after `assembleRelease` and signing — the
  release job collects from `src/{lang}/{name}/build/outputs/apk/release/`.
- The `latest` GitHub Release tag is reserved for the auto-generated extension
  index.

## Versioning

Tag-pinned, with a rolling major tag:

- Immutable releases live at `vX.Y.Z` (e.g. `v1.0.0`, `v1.0.1`, `v2.0.0`).
- A rolling tag `v1`, `v2`, ... points at the latest non-breaking release in
  that major. Consumers pin `@v1` and pick up bug fixes automatically;
  breaking changes ship a new major and consumers opt in by bumping to `@v2`.

To cut a release:

1. Push `vX.Y.Z` (e.g. `git tag -a v1.0.1 <sha> -m "..." && git push origin v1.0.1`).
2. If non-breaking: move the rolling major — `git tag -f v1 v1.0.1 && git push -f origin v1`.

Breaking-change criteria for a major bump:

- Removing or renaming an input on a reusable workflow / composite action.
- Changing the shape of an existing output.
- Tightening the assumed consumer repo layout in a way existing repos don't
  already satisfy.
