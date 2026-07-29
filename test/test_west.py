from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

import west
from west import WestProjectNotFoundError

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def west_file(tmp_path: Path) -> Path:
    return tmp_path / 'west.yml'


def copy_fixture(west_file: Path, fixture_name: str) -> None:
    shutil.copy(FIXTURES / fixture_name, west_file)


def read_revision(west_file: Path, index: int) -> str:
    yaml = YAML()
    with west_file.open(encoding='utf-8') as fh:
        data = yaml.load(fh)
    return data['manifest']['projects'][index]['revision']


def test_project_key_by_repo_path_finds_correct_index(west_file: Path) -> None:
    copy_fixture(west_file, 'west-full.yml')
    assert west.project_key_by_repo_path(west_file, 'sdk-nrfxlib-starlight') == 0


def test_project_key_by_name_finds_dragoon(west_file: Path) -> None:
    copy_fixture(west_file, 'west-full.yml')
    assert west.project_key_by_name(west_file, 'dragoon') == 1


def test_project_key_by_name_finds_nrf802154(west_file: Path) -> None:
    copy_fixture(west_file, 'west-full.yml')
    assert west.project_key_by_name(west_file, 'nrf-802154') == 2


def test_project_key_by_name_returns_none_when_project_absent(west_file: Path) -> None:
    copy_fixture(west_file, 'west-no-dragoon.yml')
    assert west.project_key_by_name(west_file, 'dragoon') is None


def test_set_project_revision_updates_revision(west_file: Path) -> None:
    copy_fixture(west_file, 'west-full.yml')
    west.set_project_revision(west_file, 0, 'pull/42/head')
    assert read_revision(west_file, 0) == 'pull/42/head'


def test_parse_revision_from_commit_message() -> None:
    message = 'Update revision d0b7c6f56ef62ae49d4cd4c5befc006621fee5c1 for MPSL'
    assert west.parse_revision_from_commit_message(message) == (
        'd0b7c6f56ef62ae49d4cd4c5befc006621fee5c1'
    )


def test_set_project_revision_by_name_updates_dragoon_when_present(west_file: Path) -> None:
    copy_fixture(west_file, 'west-full.yml')
    west.set_project_revision_by_name(west_file, 'dragoon', 'deadbeef')
    assert read_revision(west_file, 1) == 'deadbeef'


def test_set_project_revision_by_name_raises_when_dragoon_absent(west_file: Path) -> None:
    copy_fixture(west_file, 'west-no-dragoon.yml')
    with pytest.raises(WestProjectNotFoundError):
        west.set_project_revision_by_name(west_file, 'dragoon', 'deadbeef')
