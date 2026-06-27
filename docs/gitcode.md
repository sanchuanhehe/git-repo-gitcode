# GitCode fork

This is a fork of [git-repo](https://github.com/GerritCodeReview/git-repo)
(based on upstream `v2.64`) with extra commands for working against
[GitCode](https://gitcode.com) instead of Gerrit. Everything from upstream
repo keeps working; the additions below are layered on top.

## What is added

* `repo config <name> [value]` — get/set `repo.*` config on the manifest
  project (token, pull-request toggle, …). Setting `repo.token` clears the
  cached `repo.pushurl` so the fork namespace is re-resolved.
* `repo push` — push local branches to GitCode and open a pull request.
  Auto-forks the project on your account when the push is rejected.
* `repo gitcode-pr --br=<branch>` — print the open pull request opened from
  `<branch>` for each project.

These rely on the GitCode REST API, so the `requests` package is required (it
is declared as a dependency in `pyproject.toml`).

## Configuration

| key                | meaning                                                |
| ------------------ | ------------------------------------------------------ |
| `repo.token`       | GitCode personal access token (fork / PR / user APIs)  |
| `repo.pullrequest` | set to `False` to push without opening a pull request  |
| `repo.pushurl`     | cached fork push url (managed automatically)            |

```sh
repo config repo.token <ACCESS_TOKEN>
repo config repo.pullrequest True
```

The token may also be set in your user git config; the manifest-project value
takes precedence.

## Typical workflow

```sh
repo init -u git@gitcode.com:<namespace>/manifest.git
repo sync
repo start <BRANCH> <project1> <project2>
# ... make changes, commit ...
repo config repo.token <ACCESS_TOKEN>
repo push --br=<BRANCH> --d=<DEST_BRANCH> --new_branch
repo gitcode-pr --br=<BRANCH>
```

`repo push` options:

* `--br=<branch>` branch to push (defaults to the current branch)
* `--d=<dest>` destination branch of the pull request
* `--new_branch` create the feature branch on the server
* `-p`/`--pr_force` open a PR even when `repo.pullrequest` is `False`
* `--title` / `--content` pull request title / body
* `-f`/`--force` push without the rewind check (single project only)

## Install with uv

The standalone `repo` launcher is exposed as a console command:

```sh
uv tool install .
# or, after publishing, uv tool install git+https://github.com/sanchuanhehe/git-repo-gitcode
```

This puts `repo` on your `PATH` (with `requests` available in its
environment). For local development:

```sh
uv venv
uv pip install -e .
```
