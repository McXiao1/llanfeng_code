from __future__ import annotations

OLD_SERIOUS_PYTHON_RUNTIME_BLOCK = (
    'string(REPLACE "\\\\" "/" SERIOUS_PYTHON_WINDIR "$ENV{WINDIR}")\n'
    "set(serious_python_windows_bundled_libraries\n"
    '  "${PYTHON_PACKAGE}/python312$<$<CONFIG:Debug>:_d>.dll"\n'
    '  "${PYTHON_PACKAGE}/python3$<$<CONFIG:Debug>:_d>.dll"\n'
    '  "${SERIOUS_PYTHON_WINDIR}/System32/msvcp140.dll"\n'
    '  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140.dll"\n'
    '  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140_1.dll"\n'
    "  PARENT_SCOPE\n"
    ")\n"
)

NEW_SERIOUS_PYTHON_RUNTIME_BLOCK = (
    'set(SERIOUS_PYTHON_VC_RUNTIME_DIR "$ENV{SERIOUS_PYTHON_VC_RUNTIME_DIR}")\n'
    "if(NOT SERIOUS_PYTHON_VC_RUNTIME_DIR)\n"
    '  message(FATAL_ERROR "SERIOUS_PYTHON_VC_RUNTIME_DIR must point to the '
    'x64 VC runtime directory")\n'
    "endif()\n"
    'string(REPLACE "\\\\" "/" SERIOUS_PYTHON_VC_RUNTIME_DIR '
    '"${SERIOUS_PYTHON_VC_RUNTIME_DIR}")\n'
    "set(serious_python_windows_bundled_libraries\n"
    '  "${PYTHON_PACKAGE}/python312$<$<CONFIG:Debug>:_d>.dll"\n'
    '  "${PYTHON_PACKAGE}/python3$<$<CONFIG:Debug>:_d>.dll"\n'
    '  "${SERIOUS_PYTHON_VC_RUNTIME_DIR}/msvcp140.dll"\n'
    '  "${SERIOUS_PYTHON_VC_RUNTIME_DIR}/vcruntime140.dll"\n'
    '  "${SERIOUS_PYTHON_VC_RUNTIME_DIR}/vcruntime140_1.dll"\n'
    "  PARENT_SCOPE\n"
    ")\n"
)

OLD_SERIOUS_PYTHON_PACKAGE_BLOCK = (
    "set(PYTHON_PACKAGE ${CMAKE_BINARY_DIR}/python)\n"
    'set(PYTHON_URL "https://github.com/flet-dev/python-build/releases/download/v3.12/'
    'python-windows-for-dart-3.12.zip")\n'
    "set(PYTHON_FILE ${CMAKE_BINARY_DIR}/python-windows-for-dart.zip)\n"
    "if (NOT EXISTS ${PYTHON_FILE})\n"
    "  file(DOWNLOAD ${PYTHON_URL} ${PYTHON_FILE})\n"
    "  file(ARCHIVE_EXTRACT INPUT ${PYTHON_FILE} DESTINATION ${PYTHON_PACKAGE})\n"
    "endif()\n"
)

NEW_SERIOUS_PYTHON_PACKAGE_BLOCK = (
    "set(PYTHON_PACKAGE ${CMAKE_BINARY_DIR}/python)\n"
    'set(SERIOUS_PYTHON_BUILD_PYTHON_DIR "$ENV{SERIOUS_PYTHON_BUILD_PYTHON_DIR}")\n'
    "if(SERIOUS_PYTHON_BUILD_PYTHON_DIR AND EXISTS "
    '"${SERIOUS_PYTHON_BUILD_PYTHON_DIR}/python312.dll")\n'
    '  string(REPLACE "\\\\" "/" SERIOUS_PYTHON_BUILD_PYTHON_DIR '
    '"${SERIOUS_PYTHON_BUILD_PYTHON_DIR}")\n'
    '  set(PYTHON_PACKAGE "${SERIOUS_PYTHON_BUILD_PYTHON_DIR}")\n'
    "else()\n"
    '  set(PYTHON_URL "https://github.com/flet-dev/python-build/releases/download/v3.12/'
    'python-windows-for-dart-3.12.zip")\n'
    "  set(PYTHON_FILE ${CMAKE_BINARY_DIR}/python-windows-for-dart.zip)\n"
    "  if (NOT EXISTS ${PYTHON_FILE})\n"
    "    file(DOWNLOAD ${PYTHON_URL} ${PYTHON_FILE} STATUS PYTHON_DOWNLOAD_STATUS)\n"
    "    list(GET PYTHON_DOWNLOAD_STATUS 0 PYTHON_DOWNLOAD_CODE)\n"
    "    if(NOT PYTHON_DOWNLOAD_CODE EQUAL 0)\n"
    '      message(FATAL_ERROR "Failed to download Python runtime: '
    '${PYTHON_DOWNLOAD_STATUS}")\n'
    "    endif()\n"
    "    file(ARCHIVE_EXTRACT INPUT ${PYTHON_FILE} DESTINATION ${PYTHON_PACKAGE})\n"
    "  endif()\n"
    "endif()\n"
)


def _patch_cleanup_commands(content: str) -> tuple[str, bool]:
    lines = content.splitlines(keepends=True)
    patched_lines: list[str] = []
    cleanup_replaced = False

    for line in lines:
        stripped = line.strip()
        is_del_command = stripped.startswith("COMMAND DEL ")
        is_if_del_command = stripped.startswith("COMMAND IF ") and " DEL " in stripped
        if is_del_command or is_if_del_command:
            if not cleanup_replaced:
                patched_lines.append(
                    '  COMMAND ${CMAKE_COMMAND} -E echo "Skipping optional Python DLL cleanup"\n'
                )
                cleanup_replaced = True
            continue
        patched_lines.append(line)

    return "".join(patched_lines), cleanup_replaced


def patch_serious_python_windows_cmake(content: str) -> str:
    """Patch serious_python_windows to bundle x64 Visual C++ runtime DLLs.

    Args:
        content: Original CMakeLists.txt content from serious_python_windows.

    Returns:
        Patched CMakeLists.txt content. Already patched content is returned unchanged.

    Raises:
        ValueError: If the expected runtime block is not present.
    """
    patched = content
    package_replaced = False
    if OLD_SERIOUS_PYTHON_PACKAGE_BLOCK in patched:
        patched = patched.replace(
            OLD_SERIOUS_PYTHON_PACKAGE_BLOCK,
            NEW_SERIOUS_PYTHON_PACKAGE_BLOCK,
        )
        package_replaced = True

    runtime_replaced = False
    if OLD_SERIOUS_PYTHON_RUNTIME_BLOCK in patched:
        patched = patched.replace(
            OLD_SERIOUS_PYTHON_RUNTIME_BLOCK,
            NEW_SERIOUS_PYTHON_RUNTIME_BLOCK,
        )
        runtime_replaced = True
    elif (
        "serious_python_windows_bundled_libraries" in patched
        and "SERIOUS_PYTHON_VC_RUNTIME_DIR" not in patched
    ):
        raise ValueError("serious_python_windows runtime block was not found")

    patched, cleanup_replaced = _patch_cleanup_commands(patched)
    if (
        not runtime_replaced
        and not package_replaced
        and not cleanup_replaced
        and "SERIOUS_PYTHON_VC_RUNTIME_DIR" not in patched
        and "SERIOUS_PYTHON_BUILD_PYTHON_DIR" not in patched
        and "Skipping optional Python DLL cleanup" not in patched
    ):
        raise ValueError("serious_python_windows patch targets were not found")

    return patched
