from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))


_ensure_src_on_path()

from llanfeng_code_assistant.packaging import patch_serious_python_windows_cmake  # noqa: E402


def _default_cmake_paths() -> list[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []

    cache_root = Path(local_app_data) / "Pub" / "Cache" / "hosted" / "pub.dev"
    return sorted(cache_root.glob("serious_python_windows-*/windows/CMakeLists.txt"))


def main() -> int:
    """Patch installed serious_python_windows package files in Pub Cache."""
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()

    cmake_paths = args.paths or _default_cmake_paths()
    if not cmake_paths:
        print("serious_python_windows CMakeLists.txt was not found", file=sys.stderr)
        return 1

    for cmake_path in cmake_paths:
        content = cmake_path.read_text(encoding="utf-8")
        patched = patch_serious_python_windows_cmake(content)
        if patched != content:
            cmake_path.write_text(patched, encoding="utf-8")
            print(f"Patched {cmake_path}")
        else:
            print(f"Already patched {cmake_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
