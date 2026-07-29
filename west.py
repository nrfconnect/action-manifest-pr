# Copyright (c) 2025 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096


class WestProjectNotFoundError(LookupError):
    pass


def _load(west_file: Path) -> dict:
    with west_file.open(encoding='utf-8') as fh:
        data = _yaml.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f'{west_file} is not a mapping')
    return data


def _save(west_file: Path, data: dict) -> None:
    with west_file.open('w', encoding='utf-8') as fh:
        _yaml.dump(data, fh)


def _projects(west_file: Path) -> list:
    return _load(west_file)['manifest']['projects']


def project_key_by_name(west_file: Path, name: str) -> int | None:
    for index, project in enumerate(_projects(west_file)):
        if project.get('name') == name:
            return index
    return None


def project_key_by_repo_path(west_file: Path, repo_path: str) -> int:
    for index, project in enumerate(_projects(west_file)):
        if project.get('repo-path') == repo_path:
            return index
    raise WestProjectNotFoundError(f'repo-path {repo_path!r} not found in {west_file}')


def set_project_revision(west_file: Path, project_key: int, revision: str) -> None:
    data = _load(west_file)
    data['manifest']['projects'][project_key]['revision'] = revision
    _save(west_file, data)


def set_project_revision_by_name(west_file: Path, name: str, revision: str) -> None:
    project_key = project_key_by_name(west_file, name)
    if project_key is None:
        raise WestProjectNotFoundError(f'project {name!r} not found in {west_file}')
    set_project_revision(west_file, project_key, revision)


def parse_revision_from_commit_message(message: str) -> str:
    return message.split('\n', maxsplit=1)[0].split()[2]
