import os
import subprocess
import time
from tempfile import mkdtemp
from typing import List, Optional

from git_machete.git_operations import GitContext


def popen(command: str) -> str:
    with os.popen(command) as process:
        return process.read().strip()


git: GitContext = GitContext()


class BaseTest:
    def setup_method(self) -> None:
        self.repo_sandbox = GitRepositorySandbox()
        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )


class GitRepositorySandbox:
    second_remote_path = mkdtemp()

    def __init__(self) -> None:
        self.remote_path = mkdtemp()
        self.local_path = mkdtemp()
        self.file_counter = 0

    def execute(self, command: str) -> "GitRepositorySandbox":
        subprocess.check_call(command, shell=True)
        return self

    def new_repo(self, *args: str, switch_dir_to_new_repo: bool = True) -> "GitRepositorySandbox":
        previous_dir = os.getcwd()
        os.chdir(args[0])
        opts = args[1:]
        self.execute(f"git init --quiet {' '.join(opts)}")
        if not switch_dir_to_new_repo:
            os.chdir(previous_dir)
        return self

    def new_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout -b {branch_name}")
        return self

    def new_root_branch(self, branch_name: str) -> "GitRepositorySandbox":
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
        self.execute(f'git commit -m "{message}"')
        return self

    def add_file_and_commit(self, file_path: str = 'file_name.txt', file_content: str = 'Some file content\n',
                            message: str = "Some commit message.") -> "GitRepositorySandbox":
        self.write_to_file(file_path=file_path, file_content=file_content)
        self.execute(f"git add {file_path}")
        self.execute(f'git commit -m "{message}"')
        return self

    def commit_amend(self, message: str) -> "GitRepositorySandbox":
        self.execute(f'git commit --amend -m "{message}"')
        return self

    def push(self, remote: str = 'origin', set_upstream: bool = True, tracking_branch: Optional[str] = None) -> "GitRepositorySandbox":
        branch = popen("git symbolic-ref -q --short HEAD")
        tracking_branch = tracking_branch or branch
        self.execute(f"git push {'--set-upstream' if set_upstream else ''} {remote} {branch}:{tracking_branch}")
        return self

    def merge(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f'git merge {branch_name}')
        return self

    def reset_to(self, revision: str) -> "GitRepositorySandbox":
        self.execute(f'git reset --keep "{revision}"')
        return self

    def delete_branch(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f'git branch -d "{branch}"')
        return self

    def add_remote(self, remote: str, url: str) -> "GitRepositorySandbox":
        self.execute(f'git remote add {remote} {url}')
        return self

    def remove_remote(self, remote: str = 'origin') -> "GitRepositorySandbox":
        self.execute(f'git remote remove {remote}')
        return self

    def get_local_branches(self) -> List[str]:
        return popen('git for-each-ref refs/heads/ "--format=%(refname:short)"').splitlines()

    def is_ancestor(self, earlier: str, later: str) -> bool:
        return subprocess.call(f"git merge-base --is-ancestor  '{earlier}'  '{later}'", shell=True) == 0

    def get_current_commit_hash(self) -> str:
        return self.get_commit_hash("HEAD")

    def get_commit_hash(self, revision: str) -> str:
        return popen(f"git rev-parse {revision}")

    def set_git_config_key(self, key: str, value: str) -> "GitRepositorySandbox":
        self.execute(f'git config {key} {value}')
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

    def remove_file(self, file_path: str) -> "GitRepositorySandbox":
        self.execute(f"rm -rf './{file_path}'")
        return self

    def set_file_executable(self, file_name: str) -> "GitRepositorySandbox":
        os.chmod(file_name, 0o700)
        return self

    def sleep(self, seconds: int) -> "GitRepositorySandbox":
        time.sleep(seconds)
        return self
