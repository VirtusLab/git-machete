import os
import re
import subprocess
import time
from os import mkdir
from tempfile import mkdtemp
from typing import List, Optional, Tuple


class GitRepositorySandbox:
    def __init__(self) -> None:
        self.__sandbox_dir = mkdtemp()
        self.remote_path = self.create_repo("remote", bare=True)
        self.local_path = self.create_repo("local", bare=False, switch_dir_to_new_repo=True)
        self.add_remote("origin", self.remote_path)
        self.file_counter = 0

    def create_repo(self, name: str, bare: bool, switch_dir_to_new_repo: bool = False) -> str:
        path = os.path.join(self.__sandbox_dir, name)
        mkdir(path)
        previous_dir = os.getcwd()
        os.chdir(path)
        bare_opt = '--bare' if bare else ''
        self.execute(f'git init --quiet "{path}" {bare_opt}')
        if not bare:
            self.set_git_config_key("user.email", "tester@test.com")
            self.set_git_config_key("user.name", "Tester Test")
        if not switch_dir_to_new_repo:
            os.chdir(previous_dir)
        return path

    def popen(self, command: str) -> str:
        return subprocess.check_output(command, shell=True, timeout=5).decode("utf-8").strip()

    def execute(self, command: str) -> "GitRepositorySandbox":
        subprocess.check_call(command, shell=True)
        return self

    def execute_ignoring_exit_code(self, command: str) -> "GitRepositorySandbox":
        subprocess.call(command, shell=True)
        return self

    def chdir(self, path: str) -> "GitRepositorySandbox":
        os.chdir(path)
        return self

    def new_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout -b {branch_name}")
        return self

    def new_orphan_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout --orphan {branch_name}")
        return self

    def check_out(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout {branch}")
        return self

    def commit(self, message: str = "Some commit message.") -> "GitRepositorySandbox":
        f = f'{self.file_counter}.txt'
        self.file_counter += 1
        self.execute(f"touch {f}")
        self.execute(f"git add {f}")
        self.write_to_file(".git/commit-message", message)
        # Not passing the message directly via `-m` so that multiline messages can be handled correctly on Windows.
        self.execute('git commit --file=.git/commit-message')
        return self

    def commit_n_times(self, count: int) -> "GitRepositorySandbox":
        for _ in range(count):
            self.commit()
        return self

    def add_file_and_commit(self, file_path: str = 'file_name.txt', file_content: str = 'Some file content\n',
                            message: str = "Some commit message.") -> "GitRepositorySandbox":
        self.write_to_file(file_path=file_path, file_content=file_content)
        self.execute(f"git add {file_path}")
        self.execute(f'git commit -m "{message}"')
        return self

    def amend_commit(self, message: str = "Some commit message.") -> "GitRepositorySandbox":
        self.execute(f'git commit -a --amend -m "{message}"')
        return self

    def push(self, remote: str = 'origin', set_upstream: bool = True, tracking_branch: Optional[str] = None) -> "GitRepositorySandbox":
        branch = self.popen("git symbolic-ref -q --short HEAD")
        tracking_branch = tracking_branch or branch
        self.execute(f"git push {'--set-upstream' if set_upstream else ''} {remote} {branch}:{tracking_branch}")
        return self

    def pull(self) -> "GitRepositorySandbox":
        self.execute("git pull")
        return self

    def fetch(self) -> "GitRepositorySandbox":
        self.execute("git fetch")
        return self

    def merge(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f'git merge {branch_name}')
        return self

    def reset_to(self, revision: str) -> "GitRepositorySandbox":
        self.execute(f'git reset --keep "{revision}"')
        return self

    def delete_branch(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f'git branch -D "{branch}"')
        return self

    def delete_remote_branch(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f'git branch -D -r "{branch}"')
        return self

    def add_remote(self, remote: str, url: str) -> "GitRepositorySandbox":
        self.execute(f'git remote add {remote} "{url}"')
        return self

    def set_remote_url(self, remote: str, url: str) -> "GitRepositorySandbox":
        self.execute(f'git remote set-url {remote} "{url}"')
        return self

    def remove_remote(self, remote: str = 'origin') -> "GitRepositorySandbox":
        self.execute(f'git remote remove {remote}')
        return self

    def get_local_branches(self) -> List[str]:
        return self.popen('git for-each-ref refs/heads/ "--format=%(refname:short)"').splitlines()

    def is_ancestor_or_equal(self, earlier: str, later: str) -> bool:
        return subprocess.call(f'git merge-base --is-ancestor  "{earlier}"  "{later}"', shell=True) == 0

    def get_current_commit_hash(self) -> str:
        return self.get_commit_hash("HEAD")

    def get_current_branch(self) -> str:
        return self.popen("git symbolic-ref --short HEAD")

    def get_commit_hash(self, revision: str) -> str:
        return self.popen(f"git rev-parse {revision}")

    def get_git_version(self) -> Tuple[int, int, int]:
        raw = re.search(r"(\d+).(\d+).(\d+)", self.popen("git version"))
        assert raw
        return int(raw.group(1)), int(raw.group(2)), int(raw.group(3))

    def set_git_config_key(self, key: str, value: str) -> "GitRepositorySandbox":
        self.execute(f'git config {key} "{value}"')
        return self

    def unset_git_config_key(self, key: str) -> "GitRepositorySandbox":
        self.execute(f'git config --unset {key}')
        return self

    def read_file(self, file_name: str) -> str:
        with open(file_name) as f:
            return f.read()

    def write_to_file(self, file_path: str, file_content: str) -> "GitRepositorySandbox":
        dirname = os.path.dirname(file_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(file_content)
        return self

    def remove_directory(self, file_path: str) -> "GitRepositorySandbox":
        self.execute(f'rm -rf "./{file_path}"')
        return self

    def set_file_executable(self, file_name: str) -> "GitRepositorySandbox":
        os.chmod(file_name, 0o700)
        return self

    def sleep(self, seconds: int) -> "GitRepositorySandbox":
        time.sleep(seconds)
        return self
