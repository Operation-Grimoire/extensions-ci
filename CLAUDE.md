# CLAUDE.md — Agent guide for extensions-ci

Reusable CI for every Grimoire-extensions-shaped repo: composite actions +
Python scripts that detect changed extensions and build the `index.json` the
app's extension browser reads. Consumed by `grimoire-extensions`,
`grimoire-extensions-x`, and any sibling repo via thin workflow stubs that pin a
rolling major tag (`@v2`). Read this with [`README.md`](./README.md) (the public
contract) before editing.

## Layout

```
.github/workflows/   pr-build.yml · pr-cleanup.yml · release.yml  (all on: workflow_call)
.github/actions/     detect-pr-changes · detect-changes · generate-index · comment-pr-preview
scripts/             detect_pr_changes.py · detect_changes.py · generate_index.py · comment_pr_preview.py
```

Each composite action just runs its matching script
(`${{ github.action_path }}/../../../scripts/<x>.py`); the scripts honor
`REPO_ROOT` (set by the actions to the caller's `github.workspace`) so they
operate on the *consumer* repo's checkout.

## ⚠️ The self-reference trap (this bit us once — don't repeat it)

The reusable workflows call our own composite actions **by pinned ref**, e.g.
`release.yml` contains `uses: operation-grimoire/extensions-ci/.github/actions/generate-index@v2`.
Two consequences that are easy to miss:

1. **A composite action runs its scripts relative to its *own* checkout ref**,
   not the workflow's. So editing `scripts/generate_index.py` only reaches a
   pipeline whose workflow references that action **at a ref that includes the
   edit**. Pushing the script to `main` / tagging it is *not* enough — the
   `@vN` on the `uses:` line is what decides which script actually runs.

2. **When you cut a new major (or change a script), every workflow must point
   its internal `@vN` self-references at the ref carrying the change — and they
   must all agree.** The original v2 cut bumped `pr-build.yml` to `@v2` but left
   `release.yml` on `@v1`, so the release pipeline silently ran v1's old
   generator: `index.json` rebuilt with bumped versions but missing the new
   field. Symptom to recognize: a script change that works in PR previews
   (`pr-build.yml`) but never appears in the published release.

**Rule:** internal `extensions-ci/.github/{actions,workflows}/…@vN` refs must
match the major you're releasing. After any change, verify there are no stale
refs:

```bash
grep -rnE 'operation-grimoire/extensions-ci/\.github/(actions|workflows)/[^@]+@v[0-9]' .github/workflows
# every hit must be the current major
```

## Versioning & releasing

Tag-pinned with a rolling major (see README "Versioning"):

1. Push the immutable `vX.Y.Z` at the merge commit.
2. Non-breaking → move the rolling major: `git tag -f vN vX.Y.Z && git push -f origin vN`.
   (The rolling tag is what consumers pin; nothing ships until it moves.)

Bumping a script behind an already-`@vN`-referenced action is a **PATCH** when
the workflow contract is unchanged — but only ships once `vN` is moved to the
commit *and* the workflows reference that action at `@vN` (see the trap above).

Major-bump criteria (from README): removing/renaming a workflow input, changing
an output's shape, or tightening the assumed consumer repo layout.

## `index.json` regeneration gotcha (force_all)

`detect-changes` diffs each extension's `versionCode` against the **published**
`index.json` and only rebuilds the bumped ones; `generate_index.py` then updates
entries **only for extensions rebuilt this run** (those with an APK under
`repo/`) and keeps prior entries for the rest.

So a fix that should re-emit a field for *already-published* versions rebuilds
nothing on its own — the versions already match the published index. Re-run the
caller's release with **`force_all: true`** (release.yml input, exposed on the
consumer stub's `workflow_dispatch`) to rebuild every extension through the
generator. A `lib/`-tree change also forces a full rebuild.

## Don'ts

- **Don't edit a script and assume it ships.** Confirm which `@vN` the consuming
  workflow pins, and that the ref includes your change.
- **Don't leave mismatched internal `@vN` refs across workflows** when cutting a
  major — grep them all (command above).
- **Don't move a rolling major onto a commit that also carries breaking
  changes** for that major's consumers; that's what a new major is for.
- **Don't expect a field/format change to appear in a release without a rebuild**
  of the affected extensions (`force_all` or a real versionCode bump).
