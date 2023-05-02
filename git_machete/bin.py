import sys

# Since this shim needs to be compatible with Python 2,
# let's skip mypy checks, as type annotations were only introduced in Python 3.5.


def main():  # type: ignore
    def validate_python_version():  # type: ignore
        if sys.version_info[:2] < (3, 6):
            # String interpolations were only introduced in Python 3.6
            version_str = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)  # noqa: FS002
            sys.stderr.write(
                "Python {} is no longer supported. \n".format(version_str) +  # noqa: FS002
                "Please switch to Python 3.6 or higher.\n")
            sys.exit(1)

    validate_python_version()  # type: ignore

    from . import cli

    cli.main()
