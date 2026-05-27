#!/usr/bin/env python3
"""
Post or update a sticky "PR preview ready" comment on the PR, linking to the
just-published pr-<N> release with a grimoireapp.org magic link that opens the
Add Repository dialog pre-filled.

The marker comment is matched by an HTML-comment sentinel so re-pushes update
the same comment in place rather than spamming the PR.

Reads from env (all required):
  REPO         e.g. "Operation-Grimoire/grimoire-extensions"
  PR           PR number as a string
  MODULES      space-separated Gradle module paths, e.g. ":en-novelfull"
  INDEX_URL    URL of the just-published pr-<N>/index.json
  SERVER_URL   github.com server URL (github.server_url)
  HEAD_SHA     commit the preview was built from (for display)

Calls `gh` (preinstalled on GitHub runners) authenticated with GH_TOKEN /
GITHUB_TOKEN.
"""
import json
import os
import subprocess
import sys
import urllib.parse

MARKER = "<!-- grimoire-ci:pr-preview -->"


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, text=True, capture_output=True
    ).stdout


def main() -> int:
    repo = os.environ["REPO"]
    pr = os.environ["PR"]
    modules = os.environ.get("MODULES", "").split()
    index_url = os.environ["INDEX_URL"]
    server_url = os.environ["SERVER_URL"].rstrip("/")
    head_sha = os.environ.get("HEAD_SHA", "")

    repo_name = repo.split("/")[-1]
    display_name = f"{repo_name} PR #{pr}"
    magic_link = "https://grimoireapp.org/add-repo?" + urllib.parse.urlencode(
        {"name": display_name, "url": index_url}
    )
    release_url = f"{server_url}/{repo}/releases/tag/pr-{pr}"
    mod_list = "\n".join(f"- `{m}`" for m in modules) or "_(no modules)_"
    sha_short = head_sha[:7] if head_sha else "?"

    body = (
        f"{MARKER}\n"
        f"### Grimoire PR preview\n"
        f"\n"
        f"A signed preview repo for this PR has been published. On an Android "
        f"device with Grimoire installed, tap the link to add it:\n"
        f"\n"
        f"**[Add to Grimoire]({magic_link})**\n"
        f"\n"
        f"Or add it manually under Extensions → Add repository:\n"
        f"- Name: `{display_name}`\n"
        f"- URL: `{index_url}`\n"
        f"\n"
        f"Built from `{sha_short}`:\n"
        f"{mod_list}\n"
        f"\n"
        f"[Release assets]({release_url}) — rebuilt on every push, "
        f"cleaned up when the PR closes.\n"
    )

    existing = json.loads(gh(
        "api", f"repos/{repo}/issues/{pr}/comments", "--paginate",
    ))
    mine = next((c for c in existing if c["body"].startswith(MARKER)), None)

    if mine:
        gh("api", "-X", "PATCH",
           f"repos/{repo}/issues/comments/{mine['id']}",
           "-f", f"body={body}")
        print(f"Updated comment {mine['id']}")
    else:
        gh("api", "-X", "POST",
           f"repos/{repo}/issues/{pr}/comments",
           "-f", f"body={body}")
        print("Posted new preview comment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
