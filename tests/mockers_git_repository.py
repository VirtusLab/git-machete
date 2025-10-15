import os
import re
import subprocess
from os import mkdir
from tempfile import mkdtemp
from typing import List, Optional, Tuple

from tests.mockers import execute, popen, write_to_file


def create_repo(name: str = "local", bare: bool = False, switch_dir_to_new_repo: bool = True) -> str:
    path = os.path.join(mkdtemp(), name)
    mkdir(path)
    previous_dir = os.getcwd()
    os.chdir(path)
    bare_opt = '--bare' if bare else ''
    execute(f'git init --quiet "{path}" {bare_opt}')
    if not bare:
        set_git_config_key("user.email", "tester@test.com")
        set_git_config_key("user.name", "Tester Test")
    if not switch_dir_to_new_repo:
        os.chdir(previous_dir)
    return path


def create_repo_with_remote(local_name: str = "local", remote_name: str = "remote") -> Tuple[str, str]:
    remote_path = create_repo(remote_name, bare=True, switch_dir_to_new_repo=False)
    local_path = create_repo(local_name)
    add_remote("origin", remote_path)
    return local_path, remote_path


def new_branch(branch_name: str) -> None:
    execute(f"git checkout -b {branch_name}")


def new_orphan_branch(branch_name: str) -> None:
    execute(f"git checkout --orphan {branch_name}")


def check_out(branch: str) -> None:
    execute(f"git checkout {branch}")


counter = 0


def next_integer() -> int:
    global counter
    counter += 1
    return counter


def commit(message: Optional[str] = None) -> None:
    if message is None:
        message = f"Some commit message-{next_integer()}"
    f = message.splitlines()[0].replace(' ', '').replace('.', '')
    f += '.txt'
    execute(f"touch {f}")
    execute(f"git add {f}")
    write_to_file(".git/commit-message", message)
    # Not passing the message directly via `-m` so that multiline messages can be handled correctly on Windows.
    execute('git commit --file=.git/commit-message')


def commit_n_times(count: int) -> None:
    for _ in range(count):
        commit()


def add_file_and_commit(file_path: str = 'file_name.txt', file_content: str = 'Some file content\n',
                        message: str = "Some commit message.") -> None:
    write_to_file(file_path=file_path, file_content=file_content)
    execute(f"git add {file_path}")
    execute(f'git commit -m "{message}"')


def amend_commit(message: str = "Some commit message.") -> None:
    execute(f'git commit -a --amend -m "{message}"')


def push(remote: str = 'origin', set_upstream: bool = True, tracking_branch: Optional[str] = None) -> None:
    branch = popen("git symbolic-ref -q --short HEAD")
    tracking_branch = tracking_branch or branch
    execute(f"git push {'--set-upstream' if set_upstream else ''} {remote} {branch}:{tracking_branch}")


def pull() -> None:
    execute("git pull")


def fetch() -> None:
    execute("git fetch")


def merge(branch_name: str) -> None:
    execute(f'git merge {branch_name}')


def reset_to(revision: str) -> None:
    execute(f'git reset --keep "{revision}"')


def delete_branch(branch: str) -> None:
    execute(f'git branch -D "{branch}"')


def delete_remote_branch(branch: str) -> None:
    execute(f'git branch -D -r "{branch}"')


def add_remote(remote: str, url: str) -> None:
    execute(f'git remote add {remote} "{url}"')


def set_remote_url(remote: str, url: str) -> None:
    execute(f'git remote set-url {remote} "{url}"')


def remove_remote(remote: str = 'origin') -> None:
    execute(f'git remote remove {remote}')


def get_local_branches() -> List[str]:
    return popen('git for-each-ref refs/heads/ "--format=%(refname:short)"').splitlines()


def is_ancestor_or_equal(earlier: str, later: str) -> bool:
    return subprocess.call(f'git merge-base --is-ancestor  "{earlier}"  "{later}"', shell=True) == 0


def get_current_commit_hash() -> str:
    return get_commit_hash("HEAD")


def get_current_branch() -> str:
    return popen("git symbolic-ref --short HEAD")


def get_commit_hash(revision: str) -> str:
    return popen(f"git rev-parse {revision}")


def get_git_version() -> Tuple[int, int, int]:
    raw = re.search(r"(\d+).(\d+).(\d+)", popen("git version"))
    assert raw
    return int(raw.group(1)), int(raw.group(2)), int(raw.group(3))


def set_git_config_key(key: str, value: str) -> None:
    execute(f'git config {key} "{value}"')


def unset_git_config_key(key: str) -> None:
    execute(f'git config --unset {key}')
