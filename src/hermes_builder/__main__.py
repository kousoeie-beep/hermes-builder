from __future__ import annotations

import sys

from hermes_builder import __version__


def entrypoint() -> None:
    if sys.argv[1:] == ["--version"]:
        print(f"hermes-builder {__version__}")
        raise SystemExit(0)

    from hermes_builder.cli import main

    main()


if __name__ == "__main__":
    entrypoint()
