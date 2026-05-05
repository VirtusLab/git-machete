import os
import subprocess


def execute(command: str) -> None:
    subprocess.check_call(command, shell=True)


def execute_ignoring_exit_code(command: str) -> None:
    subprocess.call(command, shell=True)


def popen(command: str) -> str:
    return subprocess.check_output(command, shell=True, timeout=5).decode("utf-8").strip()


def read_file(file_name: str) -> str:
    with open(file_name) as f:
        return f.read()


def write_to_file(file_path: str, file_content: str) -> None:
    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(file_content)


def set_file_executable(file_name: str) -> None:
    os.chmod(file_name, 0o700)


def remove_directory(file_path: str) -> None:
    execute(f'rm -rf "./{file_path}"')
