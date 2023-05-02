# flake8: noqa
import sys


def main():
    # Check for correct python version
    # Since function below needs to be compatible with python 2, lets skip Mypy checks, cause type annotations were introduced in python 3.5
    def validate_python_version():  # type: ignore
        if sys.version_info[:2] < (3, 6):
            version_str = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
            sys.stderr.write(
                "Python {} is no longer supported. \n".format(version_str) +
                "Please switch to Python 3.6 or higher.\n")
            sys.exit(1)

    validate_python_version()  # type: ignore

    from . import cli

    cli.main()
