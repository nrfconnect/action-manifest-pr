from pathlib import Path

import pytest
from ruamel.yaml import YAML

from update_manifest import (
    ManifestError,
    find_project,
    main,
    revision_from_commit_message,
    update_manifest,
)

MANIFEST_TEMPLATE = """\
# Sample west manifest used by the tests.
manifest:
  remotes:
    - name: ncs
      url-base: https://github.com/nrfconnect

  projects:
    # nrfxlib is the triggering repository
    - name: nrfxlib
      repo-path: sdk-nrfxlib
      remote: ncs
      revision: abcdef1234567890
      path: nrfxlib
{extra_projects}
  self:
    path: nrf
"""

DRAGOON_REVISION = "d1d1d1d1d1d1d1d1"
NRF_802154_REVISION = "e2e2e2e2e2e2e2e2"

DRAGOON_PROJECT = f"""\
    - name: dragoon
      remote: ncs
      revision: {DRAGOON_REVISION}
      path: dragoon
"""

NRF_802154_PROJECT = f"""\
    - name: nrf-802154
      remote: ncs
      revision: {NRF_802154_REVISION}
      path: nrf-802154
"""


def write_manifest(tmp_path: Path, *extra_projects: str) -> Path:
    manifest = tmp_path / "west.yml"
    manifest.write_text(
        MANIFEST_TEMPLATE.format(extra_projects="".join(extra_projects)),
        encoding="utf-8",
    )
    return manifest


def load(manifest: Path):
    yaml = YAML()
    with manifest.open(encoding="utf-8") as manifest_file:
        return yaml.load(manifest_file)


def revision_of(manifest: Path, name: str) -> str:
    return find_project(load(manifest), name=name)["revision"]


@pytest.fixture
def plain_manifest(tmp_path: Path) -> Path:
    return write_manifest(tmp_path)


@pytest.fixture
def dragoon_manifest(tmp_path: Path) -> Path:
    return write_manifest(tmp_path, DRAGOON_PROJECT)


@pytest.fixture
def nrf_802154_manifest(tmp_path: Path) -> Path:
    return write_manifest(tmp_path, NRF_802154_PROJECT)


class TestRevisionFromCommitMessage:
    def test_takes_third_word(self):
        assert revision_from_commit_message(
            "dragoon: update deadbeefcafe") == "deadbeefcafe"

    def test_uses_only_first_line_words(self):
        message = "nrf_802154: revision 1234abcd\n\nSigned-off-by: someone"
        assert revision_from_commit_message(message) == "1234abcd"

    @pytest.mark.parametrize("message", [None, "", "   ", "too short"])
    def test_returns_none_for_unusable_messages(self, message):
        assert revision_from_commit_message(message) is None


class TestPrRevision:
    def test_sets_pull_head_revision(self, plain_manifest):
        update_manifest(plain_manifest, repo_name="sdk-nrfxlib", pr_number="42")

        data = load(plain_manifest)
        project = find_project(data, repo_path="sdk-nrfxlib")
        assert project["revision"] == "pull/42/head"

    def test_preserves_comments_and_other_fields(self, plain_manifest):
        update_manifest(plain_manifest, repo_name="sdk-nrfxlib", pr_number="42")

        content = plain_manifest.read_text(encoding="utf-8")
        assert "# Sample west manifest used by the tests." in content
        assert "# nrfxlib is the triggering repository" in content
        assert "url-base: https://github.com/nrfconnect" in content
        assert "path: nrf" in content

    def test_unknown_repo_path_raises(self, plain_manifest):
        with pytest.raises(ManifestError, match="sdk-unknown"):
            update_manifest(plain_manifest, repo_name="sdk-unknown", pr_number="42")

    def test_missing_projects_key_raises(self, tmp_path):
        manifest = tmp_path / "west.yml"
        manifest.write_text("manifest:\n  self:\n    path: nrf\n", encoding="utf-8")

        with pytest.raises(ManifestError, match="manifest.projects"):
            update_manifest(manifest, repo_name="sdk-nrfxlib", pr_number="1")


class TestDragoonRevision:
    TITLE = "Update MPSL and SoftDevice Controller to v1.2.3"

    def test_updates_dragoon_when_present(self, dragoon_manifest):
        update_manifest(
            dragoon_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="7",
            pr_title=self.TITLE,
            commit_message="dragoon: revision 0badc0de",
        )

        assert revision_of(dragoon_manifest, "dragoon") == "0badc0de"
        assert revision_of(dragoon_manifest, "nrfxlib") == "pull/7/head"

    def test_skipped_when_dragoon_absent(self, plain_manifest):
        messages = update_manifest(
            plain_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="7",
            pr_title=self.TITLE,
            commit_message="dragoon: revision 0badc0de",
        )

        assert find_project(load(plain_manifest), name="dragoon") is None
        assert any("not present" in message for message in messages)

    def test_not_updated_for_other_title(self, dragoon_manifest):
        update_manifest(
            dragoon_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="7",
            pr_title="Some unrelated change",
            commit_message="dragoon: revision 0badc0de",
        )

        assert revision_of(dragoon_manifest, "dragoon") == DRAGOON_REVISION

    def test_missing_commit_message_raises(self, dragoon_manifest):
        with pytest.raises(ManifestError, match="dragoon"):
            update_manifest(
                dragoon_manifest,
                repo_name="sdk-nrfxlib",
                pr_number="7",
                pr_title=self.TITLE,
                commit_message=None,
            )


class TestNrf802154Revision:
    TITLE = "Update revision of nrf_802154 to latest"

    def test_updates_nrf_802154_when_present(self, nrf_802154_manifest):
        update_manifest(
            nrf_802154_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="9",
            pr_title=self.TITLE,
            commit_message="nrf_802154: revision feedface",
        )

        assert revision_of(nrf_802154_manifest, "nrf-802154") == "feedface"
        assert revision_of(nrf_802154_manifest, "nrfxlib") == "pull/9/head"

    def test_skipped_when_absent(self, plain_manifest):
        messages = update_manifest(
            plain_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="9",
            pr_title=self.TITLE,
            commit_message="nrf_802154: revision feedface",
        )

        assert find_project(load(plain_manifest), name="nrf-802154") is None
        assert any("not present" in message for message in messages)

    def test_not_updated_for_other_title(self, nrf_802154_manifest):
        update_manifest(
            nrf_802154_manifest,
            repo_name="sdk-nrfxlib",
            pr_number="9",
            pr_title="Update MPSL and SoftDevice Controller",
            commit_message="nrf_802154: revision feedface",
        )

        assert revision_of(nrf_802154_manifest, "nrf-802154") == NRF_802154_REVISION


class TestCli:
    def test_main_updates_manifest(self, nrf_802154_manifest, capsys):
        exit_code = main([
            "--manifest-file", str(nrf_802154_manifest),
            "--repo-name", "sdk-nrfxlib",
            "--pr-number", "11",
            "--pr-title", "Update revision of nrf_802154",
            "--commit-message", "nrf_802154: revision cafebabe",
        ])

        assert exit_code == 0
        assert revision_of(nrf_802154_manifest, "nrf-802154") == "cafebabe"
        assert revision_of(nrf_802154_manifest, "nrfxlib") == "pull/11/head"
        assert "cafebabe" in capsys.readouterr().out

    def test_main_returns_error_code(self, plain_manifest, capsys):
        exit_code = main([
            "--manifest-file", str(plain_manifest),
            "--repo-name", "sdk-unknown",
            "--pr-number", "11",
        ])

        assert exit_code == 1
        assert "error:" in capsys.readouterr().err

