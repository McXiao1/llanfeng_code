from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src_dir = Path(__file__).resolve().parent / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))


def main() -> int:
    _ensure_src_on_path()

    # In serious_python / Flet builds the Flutter launcher opens a blank window
    # BEFORE calling Python.  When running in inject-only mode we must call
    # os._exit() to terminate the whole process (and close that window) after
    # injection completes.  A normal "return" is not enough because it only
    # exits the Python side; the Flutter UI stays open indefinitely.
    if os.environ.get("LLANFENG_INJECT_MODE") == "1":
        from llanfeng_code_assistant.inject_launch import run_with_loading_ui
        result = run_with_loading_ui()
        os._exit(result)

    from llanfeng_code_assistant.__main__ import main as package_main
    return package_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
