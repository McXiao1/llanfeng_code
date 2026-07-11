from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src_dir = Path(__file__).resolve().parent / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))


def main() -> int:
    _ensure_src_on_path()
    from llanfeng_code_assistant.__main__ import main as package_main
    return package_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
