# action-manifest-pr
GitHub action to automatically create Pull Requests in the manifest repo when updating revisions.

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

## manifest file location:
By default the action modifies `west.yml` in the root of the target repository. Use the `manifest-file-path` input to point to a different manifest file, e.g. `manifest-file-path: submanifests/custom.yml`.

## nrfxlib manifest PR side-effect updates

When this action runs from **sdk-nrfxlib** (or another triggering repo), the manifest PR normally updates only that repo's `west.yml` entry. For certain nrfxlib PR titles, the action also updates additional manifest projects—**but only if those projects are present in the target branch's `west.yml`**.

| Triggering PR title prefix | `west.yml` project updated | Notes |
|---|---|---|
| `Update MPSL and SoftDevice Controller` | `dragoon` | Revision is taken from the third word of the triggering PR's latest commit message. Skipped when `dragoon` is not in `west.yml` (e.g. some starlight branches). |
| `Update revision of nrf_802154` | `nrf-802154` (802.15.4) | Same commit-message parsing as dragoon. Skipped when `nrf-802154` is not in `west.yml`. |

In all cases the action still updates the triggering repository's own `repo-path` entry to `pull/<nr>/head` as usual.
