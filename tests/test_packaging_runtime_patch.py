from __future__ import annotations

from llanfeng_code_assistant.packaging import (
    patch_serious_python_windows_cmake,
)


def test_patch_serious_python_windows_cmake_uses_x64_vc_runtime_env_var() -> None:
    original = """
string(REPLACE "\\\\" "/" SERIOUS_PYTHON_WINDIR "$ENV{WINDIR}")
set(serious_python_windows_bundled_libraries
  "${PYTHON_PACKAGE}/python312$<$<CONFIG:Debug>:_d>.dll"
  "${PYTHON_PACKAGE}/python3$<$<CONFIG:Debug>:_d>.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/msvcp140.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140_1.dll"
  PARENT_SCOPE
)
"""

    patched = patch_serious_python_windows_cmake(original)

    assert 'SERIOUS_PYTHON_VC_RUNTIME_DIR "$ENV{SERIOUS_PYTHON_VC_RUNTIME_DIR}"' in patched
    assert "SERIOUS_PYTHON_VC_RUNTIME_DIR must point to the x64 VC runtime directory" in patched
    assert '"${SERIOUS_PYTHON_VC_RUNTIME_DIR}/msvcp140.dll"' in patched
    assert "System32/msvcp140.dll" not in patched
    assert "System32/vcruntime140_1.dll" not in patched


def test_patch_serious_python_windows_cmake_prefers_packaging_python_runtime() -> None:
    original = """
set(PYTHON_PACKAGE ${CMAKE_BINARY_DIR}/python)
set(PYTHON_URL "https://github.com/flet-dev/python-build/releases/download/v3.12/python-windows-for-dart-3.12.zip")
set(PYTHON_FILE ${CMAKE_BINARY_DIR}/python-windows-for-dart.zip)
if (NOT EXISTS ${PYTHON_FILE})
  file(DOWNLOAD ${PYTHON_URL} ${PYTHON_FILE})
  file(ARCHIVE_EXTRACT INPUT ${PYTHON_FILE} DESTINATION ${PYTHON_PACKAGE})
endif()
"""

    patched = patch_serious_python_windows_cmake(original)

    assert "SERIOUS_PYTHON_BUILD_PYTHON_DIR" in patched
    assert 'EXISTS "${SERIOUS_PYTHON_BUILD_PYTHON_DIR}/python312.dll"' in patched
    assert 'set(PYTHON_PACKAGE "${SERIOUS_PYTHON_BUILD_PYTHON_DIR}")' in patched
    assert "PYTHON_DOWNLOAD_STATUS" in patched
    assert "Failed to download Python runtime" in patched


def test_patch_serious_python_windows_cmake_is_idempotent() -> None:
    original = """
string(REPLACE "\\\\" "/" SERIOUS_PYTHON_WINDIR "$ENV{WINDIR}")
set(serious_python_windows_bundled_libraries
  "${PYTHON_PACKAGE}/python312$<$<CONFIG:Debug>:_d>.dll"
  "${PYTHON_PACKAGE}/python3$<$<CONFIG:Debug>:_d>.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/msvcp140.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140.dll"
  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140_1.dll"
  PARENT_SCOPE
)
"""

    patched_once = patch_serious_python_windows_cmake(original)
    patched_twice = patch_serious_python_windows_cmake(patched_once)

    assert patched_twice == patched_once


def test_patch_serious_python_windows_cmake_removes_windows_del_cleanup() -> None:
    runner_dlls = (
        "${CMAKE_BINARY_DIR}/runner/"
        "$<$<CONFIG:Release>:Release>$<$<CONFIG:Debug>:Debug>/DLLs"
    )
    release_dlls = "${CMAKE_BINARY_DIR}/runner/Release/DLLs"
    original = "\n".join(
        [
            "add_custom_command(TARGET CopyPythonDLLs POST_BUILD",
            "  COMMAND ${CMAKE_COMMAND} -E copy_directory",
            '    "${PYTHON_PACKAGE}/DLLs"',
            f'    "{runner_dlls}"',
            '  COMMAND IF \\"$<$<CONFIG:Release>:release>\\" == \\"release\\" '
            f'DEL \\"{release_dlls}\\\\*_d.*\\" /S /Q',
            f'  COMMAND DEL \\"{runner_dlls}\\\\*.ico\\" /S /Q',
            f'  COMMAND DEL \\"{runner_dlls}\\\\*.cat\\" /S /Q',
            f'  COMMAND DEL \\"{runner_dlls}\\\\tcl86t.dll\\" /Q',
            f'  COMMAND DEL \\"{runner_dlls}\\\\tk86t.dll\\" /Q',
            ")",
            "",
        ]
    )

    patched = patch_serious_python_windows_cmake(original)

    assert "COMMAND DEL" not in patched
    assert "COMMAND IF" not in patched
    assert "Skipping optional Python DLL cleanup" in patched
