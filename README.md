# action-manifest-pr
GitHub action to automatically create Pull Requests in the manifest repo when updating revisions.

Implementation follows the same pattern as [zephyrproject-rtos/action-manifest](https://github.com/zephyrproject-rtos/action-manifest): a composite action that installs Python dependencies and runs `action.py`.

## usage
Please call this action from triggering repo to create manifest PRs automatically (e.g. sdk-nrfxlib)
```yaml
name: handle manifest PR
on:
  pull_request_target:
    types: [opened, synchronize, closed]
    branches:
      - main

jobs:
  create-manifest-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Create manifest PR
        uses: nrfconnect/action-manifest-pr@main
        with:
          token: ${{ secrets.NCS_GITHUB_TOKEN }}
```

## skipping manifest PR creation:
There is default skip string define in: https://github.com/nrfconnect/action-manifest-pr/blob/main/action.yml#L17

Action is self-cancelling itself in case of this string is found from PR title or from PR body.

## draft PR:
By default, the manifest PR is created as a ready-for-review PR. To create it as a draft PR, set the `draft-pr` input to `true`.

## nrfxlib manifest PR side-effect updates

When this action runs from **sdk-nrfxlib** (or another triggering repo), the manifest PR normally updates only that repo's `west.yml` entry. For certain nrfxlib PR titles, the action also updates additional manifest projects—**but only if those projects are present in the target branch's `west.yml`**.

| Triggering PR title prefix | `west.yml` project updated | Notes |
|---|---|---|
| `Update MPSL and SoftDevice Controller` | `dragoon` | Revision is taken from the third word of the triggering PR's latest commit message. Skipped when `dragoon` is not in `west.yml` (e.g. some starlight branches). |
| `Update revision of nrf_802154` | `nrf-802154` (802.15.4) | Same commit-message parsing as dragoon. Skipped when `nrf-802154` is not in `west.yml`. |

In all cases the action still updates the triggering repository's own `repo-path` entry to `pull/<nr>/head` as usual.

## implementation

| File | Role |
|---|---|
| `action.yml` | Composite wrapper: external-label check, `pip install`, run `action.py` |
| `action.py` | Entry point: reads the GitHub event, orchestrates git/gh operations |
| `west.py` | `west.yml` lookup and revision updates |
| `requirements.txt` | Runtime Python dependencies |

Event handling in `action.py`:

- **opened** — check out the manifest repo, update `west.yml`, push a branch to the fork, open a manifest PR
- **synchronize** — rebase the manifest PR branch to retrigger CI
- **closed** (merged) — replace `pull/N/head` with the merge commit SHA
- **closed** (not merged) — close the manifest PR
- **reopened** — reopen the manifest PR

## development

```bash
pip install -r requirements.txt
pip install -r .github/requirements.in
pytest test/
ruff check .
mypy .
```

CI runs ruff, mypy, and pytest on every push and pull request (see `.github/workflows/ci.yaml`).
