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
