from __future__ import annotations

import argparse

from . import __version__
from .app import run_app
from .single_instance import SingleInstance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    @param argv: Optional argument list.
    @returns: Parsed namespace.
    """

    parser = argparse.ArgumentParser(prog="llanfeng-code-assistant")
    parser.add_argument("--import-url", dest="import_url")
    parser.add_argument("--version", action="store_true")
    parser.add_argument(
        "--inject",
        action="store_true",
        help="Skip the GUI and directly launch ChatGPT Desktop with CDP injection.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Application entrypoint.

    @param argv: Optional argument list.
    @returns: Process exit code.
    """

    args = parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.inject:
        from .inject_launch import main as inject_main
        return inject_main()
    with SingleInstance() as instance:
        if not instance.acquired:
            return 0
        run_app(import_url=args.import_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
