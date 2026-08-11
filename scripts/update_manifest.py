#!/usr/bin/env python3
"""Update revisions of projects in a west manifest file.

This script replaces the inline ``yq``/``diff``/``patch`` logic that used to live
in ``action.yml`` for the following steps:

* ``Change manifest file PR revision``
* ``Check dragoon project in manifest file`` / ``Change manifest file Dragoon revision``
* ``Check nrf-802154 project in manifest file`` / ``Change manifest file nrf-802154 revision``

The manifest is edited in place using ruamel.yaml round-trip mode so comments,
quoting style and ordering are preserved.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML

#: PR title prefix that triggers the ``dragoon`` project update.
DRAGOON_TITLE_PREFIX = "Update MPSL and SoftDevice Controller"
DRAGOON_PROJECT_NAME = "dragoon"

#: PR title prefix that triggers the ``nrf-802154`` project update.
NRF_802154_TITLE_PREFIX = "Update revision of nrf_802154"
NRF_802154_PROJECT_NAME = "nrf-802154"


class ManifestError(Exception):
    """Raised when the manifest cannot be processed as expected."""


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    # Keep the original indentation style used by west manifests.
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    return yaml


def load_manifest(path: Path) -> Any:
    """Load a manifest file preserving formatting."""
    with path.open(encoding="utf-8") as manifest_file:
        return _yaml().load(manifest_file)


def dump_manifest(data: Any, path: Path) -> None:
    """Write the manifest back to ``path``."""
    with path.open("w", encoding="utf-8") as manifest_file:
        _yaml().dump(data, manifest_file)


def get_projects(data: Any) -> list:
    """Return the list of projects declared in the manifest."""
    try:
        projects = data["manifest"]["projects"]
    except (TypeError, KeyError) as err:
        raise ManifestError("Manifest does not contain 'manifest.projects'") from err

    if not isinstance(projects, list):
        raise ManifestError("'manifest.projects' is not a list")

    return projects


def find_project(data: Any, *, name: Optional[str] = None,
                 repo_path: Optional[str] = None) -> Optional[dict]:
    """Find a project by ``name`` or by ``repo-path``.

    Returns ``None`` when no matching project exists.
    """
    if (name is None) == (repo_path is None):
        raise ValueError("Exactly one of 'name' or 'repo_path' must be given")

    key = "name" if name is not None else "repo-path"
    value = name if name is not None else repo_path

    for project in get_projects(data):
        if isinstance(project, dict) and project.get(key) == value:
            return project

    return None


def set_revision(data: Any, revision: str, *, name: Optional[str] = None,
                 repo_path: Optional[str] = None) -> bool:
    """Set the revision of a project.

    Returns ``True`` when the project was found and updated, ``False`` otherwise.
    """
    project = find_project(data, name=name, repo_path=repo_path)
    if project is None:
        return False

    project["revision"] = revision
    return True


def revision_from_commit_message(message: Optional[str]) -> Optional[str]:
    """Extract a revision from a commit message.

    Mirrors the original ``echo $LAST_MSG | awk 'NR==1 {print $3}'`` behaviour:
    the revision is the third whitespace separated word of the message.
    """
    if not message:
        return None

    words = message.split()
    if len(words) < 3:
        return None

    return words[2]


def update_manifest(manifest_path: Path, *, repo_name: str, pr_number: str,
                    pr_title: str = "", commit_message: Optional[str] = None) -> list[str]:
    """Apply all manifest updates and write the result back to disk.

    Returns a list of human readable messages describing what was done.
    """
    data = load_manifest(manifest_path)
    messages: list[str] = []

    pr_revision = f"pull/{pr_number}/head"
    if not set_revision(data, pr_revision, repo_path=repo_name):
        raise ManifestError(
            f"No project with repo-path '{repo_name}' found in {manifest_path}")
    messages.append(f"Set '{repo_name}' revision to {pr_revision}")

    side_effects = (
        (DRAGOON_TITLE_PREFIX, DRAGOON_PROJECT_NAME),
        (NRF_802154_TITLE_PREFIX, NRF_802154_PROJECT_NAME),
    )

    for title_prefix, project_name in side_effects:
        if not pr_title.startswith(title_prefix):
            continue

        if find_project(data, name=project_name) is None:
            messages.append(
                f"Project '{project_name}' not present in manifest, skipping")
            continue

        revision = revision_from_commit_message(commit_message)
        if revision is None:
            raise ManifestError(
                f"Could not determine '{project_name}' revision from commit "
                f"message: {commit_message!r}")

        set_revision(data, revision, name=project_name)
        messages.append(f"Set '{project_name}' revision to {revision}")

    dump_manifest(data, manifest_path)
    return messages


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-file", required=True, type=Path,
                        help="path to the manifest file to update")
    parser.add_argument("--repo-name", required=True,
                        help="repo-path of the triggering repository")
    parser.add_argument("--pr-number", required=True,
                        help="number of the triggering pull request")
    parser.add_argument("--pr-title", default="",
                        help="title of the triggering pull request")
    parser.add_argument("--commit-message", default=None,
                        help="latest commit message of the triggering pull request")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    try:
        messages = update_manifest(
            args.manifest_file,
            repo_name=args.repo_name,
            pr_number=args.pr_number,
            pr_title=args.pr_title,
            commit_message=args.commit_message,
        )
    except ManifestError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    for message in messages:
        print(message)

    return 0


if __name__ == "__main__":
    sys.exit(main())

