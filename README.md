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

### multiple manifest files
If the target repository contains more than one manifest file, pass a comma separated list. Every listed
file is updated and all changes end up in a **single commit and a single pull request**:

```yaml
      - name: Create manifest PR
        uses: nrfconnect/action-manifest-pr@main
        with:
          token: ${{ secrets.NCS_GITHUB_TOKEN }}
          manifest-file-path: west.yml,submanifests/custom.yml
```

Do not put spaces around the commas - the value is split on `,` only, so `west.yml, submanifests/custom.yml`
would be interpreted as a file named ` submanifests/custom.yml`. Each file must contain a project matching
the triggering repository's `repo-path`, otherwise the action fails. The side-effect updates below are
applied per file, and skipped for files that do not contain the project.

## nrfxlib manifest PR side-effect updates

When this action runs from **sdk-nrfxlib** (or another triggering repo), the manifest PR normally updates only that repo's `west.yml` entry. For certain nrfxlib PR titles, the action also updates additional manifest projects—**but only if those projects are present in the target branch's `west.yml`**.

| Triggering PR title prefix | `west.yml` project updated | Notes |
|---|---|---|
| `Update MPSL and SoftDevice Controller` | `dragoon` | Revision is taken from the third word of the triggering PR's latest commit message. Skipped when `dragoon` is not in `west.yml` (e.g. some starlight branches). |
| `Update revision of nrf_802154` | `nrf-802154` (802.15.4) | Same commit-message parsing as dragoon. Skipped when `nrf-802154` is not in `west.yml`. |

In all cases the action still updates the triggering repository's own `repo-path` entry to `pull/<nr>/head` as usual.

## development

The manifest editing logic lives in [`scripts/update_manifest.py`](scripts/update_manifest.py) and is
invoked by the action. It edits the manifest in place with `ruamel.yaml` round-trip mode, so comments,
quoting and ordering are preserved and the resulting diff only touches the changed `revision` lines.

The script can also be run standalone:

```bash
python scripts/update_manifest.py \
  --manifest-file west.yml \
  --repo-name sdk-nrfxlib \
  --pr-number 1234 \
  --pr-title "Update revision of nrf_802154" \
  --commit-message "nrf_802154: revision <sha>"
```

### running the tests

```bash
pip install -r requirements.txt
pytest
```

Tests run automatically on every pull request via the [Tests workflow](.github/workflows/test.yml) on Python 3.12.


