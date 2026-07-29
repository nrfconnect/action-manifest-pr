#!/usr/bin/env python3
# Copyright (c) 2025 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

import requests

import west as west_mod

DRAGOON_TITLE_PREFIX = 'Update MPSL and SoftDevice Controller'
NRF802154_TITLE_PREFIX = 'Update revision of nrf_802154'
WEST_FILE = 'west.yml'

_logging = 0


def log(message: str) -> None:
    if _logging:
        print(message, file=sys.stdout)


def die(message: str) -> NoReturn:
    print(f'ERROR: {message}', file=sys.stderr)
    sys.exit(1)


def cmd2str(cmd: tuple[str, ...]) -> str:
    return ' '.join(shlex.quote(word) for word in cmd)


def git(*args: str, cwd: Path | None = None) -> str:
    git_cmd = ('git',) + args
    log(f'Executing git cmd {git_cmd}')
    try:
        process = subprocess.Popen(
            git_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
    except OSError as exc:
        raise RuntimeError(f"failed to run '{cmd2str(git_cmd)}': {exc}") from exc

    stdout, stderr = process.communicate()
    stdout_text = stdout.decode('utf-8')
    stderr_text = stderr.decode('utf-8')
    if process.returncode or stderr_text:
        die(
            f"'{cmd2str(git_cmd)}' exited with status {process.returncode} and/or wrote "
            f'to stderr.\n==stdout==\n{stdout_text}\n==stderr==\n{stderr_text}'
        )
    return stdout_text.rstrip()


def gh(*args: str, cwd: Path | None = None) -> str:
    gh_cmd = ('gh',) + args
    log(f'Executing gh cmd {gh_cmd}')
    try:
        process = subprocess.run(
            gh_cmd,
            capture_output=True,
            cwd=cwd,
            check=False,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"failed to run '{cmd2str(gh_cmd)}': {exc}") from exc

    if process.returncode:
        die(
            f"'{cmd2str(gh_cmd)}' exited with status {process.returncode}.\n"
            f'==stdout==\n{process.stdout}\n==stderr==\n{process.stderr}'
        )
    return process.stdout.rstrip()


def require_token() -> str:
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        die('GITHUB_TOKEN or GH_TOKEN is required')
    return token


def load_event() -> dict:
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path:
        die('GITHUB_EVENT_PATH is not set')
    path = Path(event_path)
    with path.open(encoding='utf-8') as fh:
        return json.load(fh)


def skip_string_detected(event: dict, skip_string: str) -> bool:
    pull_request = event.get('pull_request', {})
    title = pull_request.get('title', '')
    body = pull_request.get('body') or ''
    return skip_string in title or skip_string in body


def check_external_contribution(token: str, repository: str, pr_number: int) -> None:
    labels = gh(
        'pr',
        'view',
        str(pr_number),
        '--repo',
        repository,
        '--json',
        'labels',
        '--jq',
        '.labels[].name',
    )
    if 'external' not in labels.splitlines():
        return

    author_json = gh(
        'pr',
        'view',
        str(pr_number),
        '--repo',
        repository,
        '--json',
        'author',
        '--jq',
        '.author',
    )
    author = json.loads(author_json)
    if author.get('login') == 'app/github-actions' and author.get('is_bot'):
        log('Author is GitHub Actions bot, skipping external contribution check.')
        return

    die(
        'External contribution detected. Automatic creation of manifest PR failed.\n'
        'To test your changes, please create PR in the sdk-nrf repository.'
    )


def setup_git() -> None:
    git('config', '--global', 'user.email', 'pylon@nordicsemi.no')
    git('config', '--global', 'user.name', 'Nordic Builder')


def clone_repo(token: str, repo: str, destination: Path, branch: str | None = None) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    url = f'https://x-access-token:{token}@github.com/{repo}.git'
    git('clone', url, str(destination))
    if branch is not None:
        git('checkout', branch, cwd=destination)
    return destination


def manifest_branch_name(repo_name: str, pr_number: int) -> str:
    return f'auto-manifest-{repo_name}-{pr_number}'


def pr_body(source_repository: str, pr_number: int) -> str:
    return (
        'Automatically created by action-manifest-pr GH action from PR:\n'
        f'https://github.com/{source_repository}/pull/{pr_number}'
    )


def fetch_last_commit_message(token: str, commits_url: str | None) -> str:
    if not commits_url:
        die('commits_url is missing from pull request event')
    response = requests.get(
        f'{commits_url}?per_page=3',
        headers={'Authorization': f'token {token}'},
        timeout=60,
    )
    response.raise_for_status()
    commits = response.json()
    if not commits:
        die('No commits found on pull request')
    return commits[-1]['commit']['message']


def update_west_for_opened(
    west_file: Path,
    event: dict,
    token: str,
) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    pr_number = pull_request['number']
    title = pull_request['title']

    project_key = west_mod.project_key_by_repo_path(west_file, repo_name)
    west_mod.set_project_revision(west_file, project_key, f'pull/{pr_number}/head')

    if title.startswith(DRAGOON_TITLE_PREFIX):
        if west_mod.has_project(west_file, 'dragoon'):
            message = fetch_last_commit_message(token, pull_request.get('commits_url'))
            dragoon_rev = west_mod.parse_revision_from_commit_message(message)
            log(f'DRAGOON_REV is {dragoon_rev}')
            west_mod.set_project_revision_by_name(west_file, 'dragoon', dragoon_rev)
        else:
            log('dragoon not found in west.yml, skipping revision update')

    if title.startswith(NRF802154_TITLE_PREFIX):
        if west_mod.has_project(west_file, 'nrf-802154'):
            message = fetch_last_commit_message(token, pull_request.get('commits_url'))
            nrf_rev = west_mod.parse_revision_from_commit_message(message)
            log(f'NRF_802154_REV is {nrf_rev}')
            west_mod.set_project_revision_by_name(west_file, 'nrf-802154', nrf_rev)
        else:
            log('nrf-802154 not found in west.yml, skipping revision update')


def handle_opened(args: argparse.Namespace, event: dict, token: str) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    source_repository = event['repository']['full_name']
    pr_number = pull_request['number']
    fork_username = args.forked_repo.split('/', maxsplit=1)[0]
    branch_name = manifest_branch_name(repo_name, pr_number)
    body = pr_body(source_repository, pr_number)

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = clone_repo(token, args.target_repo, Path(tmp) / 'manifest', args.base_branch)
        west_file = repo_dir / WEST_FILE
        update_west_for_opened(west_file, event, token)

        git('checkout', '-b', 'manifest_pr', cwd=repo_dir)
        git('add', WEST_FILE, cwd=repo_dir)
        git(
            'commit',
            '-m',
            f'manifest: Update {repo_name} revision (auto-manifest PR)',
            '-m',
            body,
            '--signoff',
            cwd=repo_dir,
        )
        fork_url = f'https://x-access-token:{token}@github.com/{args.forked_repo}'
        git('remote', 'add', 'fork', fork_url, cwd=repo_dir)
        git('push', '-u', 'fork', f'manifest_pr:{branch_name}', cwd=repo_dir)

    draft_args = ('--draft',) if args.draft_pr else ()
    gh(
        'pr',
        'create',
        '--head',
        f'{fork_username}:{branch_name}',
        '--base',
        args.base_branch,
        '--repo',
        args.target_repo,
        '--title',
        f'manifest: {repo_name}: {args.manifest_pr_title_details}',
        '--body',
        body,
        *draft_args,
    )


def handle_synchronize(args: argparse.Namespace, event: dict, token: str) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    pr_number = pull_request['number']
    branch_name = manifest_branch_name(repo_name, pr_number)

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = clone_repo(token, args.forked_repo, Path(tmp) / 'fork', branch_name)
        git('remote', 'add', 'upstream', f'https://github.com/{args.target_repo}.git', cwd=repo_dir)
        git('fetch', 'upstream', cwd=repo_dir)
        git('rebase', f'upstream/{args.base_branch}', '-X', 'theirs', cwd=repo_dir)
        git('commit', '--amend', '--no-edit', cwd=repo_dir)
        git('push', 'origin', f'{branch_name}:{branch_name}', '-f', cwd=repo_dir)


def handle_merged(args: argparse.Namespace, event: dict, token: str) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    pr_number = pull_request['number']
    branch_name = manifest_branch_name(repo_name, pr_number)
    merge_sha = pull_request['merge_commit_sha']

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = clone_repo(token, args.forked_repo, Path(tmp) / 'fork', branch_name)
        west_file = repo_dir / WEST_FILE
        project_key = west_mod.project_key_by_repo_path(west_file, repo_name)
        west_mod.set_project_revision(west_file, project_key, merge_sha)

        git('add', WEST_FILE, cwd=repo_dir)
        git('commit', '--amend', '--no-edit', cwd=repo_dir)
        git('remote', 'add', 'upstream', f'https://github.com/{args.target_repo}.git', cwd=repo_dir)
        git('fetch', 'upstream', cwd=repo_dir)

        merge_tree = subprocess.run(
            (
                'git',
                'merge-tree',
                '--write-tree',
                '--name-only',
                f'upstream/{args.base_branch}',
                branch_name,
            ),
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        log(f'has_conflict is {merge_tree.returncode}')
        if merge_tree.returncode == 1:
            git('rebase', f'upstream/{args.base_branch}', '-X', 'theirs', cwd=repo_dir)
        git('push', 'origin', f'{branch_name}:{branch_name}', '-f', cwd=repo_dir)


def gh_optional(*args: str) -> None:
    gh_cmd = ('gh',) + args
    subprocess.run(gh_cmd, check=False)


def handle_closed(args: argparse.Namespace, event: dict) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    pr_number = pull_request['number']
    branch_name = manifest_branch_name(repo_name, pr_number)
    gh_optional(
        'pr',
        'close',
        '-R',
        args.target_repo,
        f'NordicBuilder:{branch_name}',
        '--comment',
        'Automatically closed by action-manifest-pr GH action',
    )


def handle_reopened(args: argparse.Namespace, event: dict) -> None:
    pull_request = event['pull_request']
    repo_name = event['repository']['name']
    pr_number = pull_request['number']
    branch_name = manifest_branch_name(repo_name, pr_number)
    gh_optional(
        'pr',
        'reopen',
        '-R',
        args.target_repo,
        f'NordicBuilder:{branch_name}',
        '--comment',
        'Automatically reopened by action-manifest-pr GH action',
    )


def main() -> None:
    global _logging

    parser = argparse.ArgumentParser(
        description='Create and manage manifest PRs from triggering repo PRs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--target-repo', default='nrfconnect/sdk-nrf')
    parser.add_argument('--base-branch', default='main')
    parser.add_argument('--forked-repo', default='nordicbuilder/sdk-nrf')
    parser.add_argument('--skip-string', default='manifest-pr-skip')
    parser.add_argument('--manifest-pr-title-details', default='Update revision')
    parser.add_argument('--draft-pr', action='store_true')
    parser.add_argument('-v', '--verbosity-level', default='0')
    args = parser.parse_args()
    _logging = int(args.verbosity_level)

    token = require_token()
    os.environ['GH_TOKEN'] = token
    os.environ['GITHUB_TOKEN'] = token

    event = load_event()
    if skip_string_detected(event, args.skip_string):
        log('Skip string detected. Will skip following steps.')
        return

    repository = event['repository']['full_name']
    pr_number = event['pull_request']['number']
    check_external_contribution(token, repository, pr_number)

    action = event['action']
    pull_request = event['pull_request']

    setup_git()

    if action == 'opened':
        handle_opened(args, event, token)
    elif action == 'synchronize':
        handle_synchronize(args, event, token)
    elif action == 'closed':
        if pull_request.get('merged'):
            handle_merged(args, event, token)
        else:
            handle_closed(args, event)
    elif action == 'reopened':
        handle_reopened(args, event)
    else:
        log(f'No handler for action {action!r}')


if __name__ == '__main__':
    main()
