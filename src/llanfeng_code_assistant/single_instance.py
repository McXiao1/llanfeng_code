from __future__ import annotations

import ctypes
import sys
from types import TracebackType
from typing import Any, Self

ERROR_ALREADY_EXISTS = 183
DEFAULT_MUTEX_NAME = "Global\\LlanfengCodeAssistant"


class SingleInstance:
    """Windows named-mutex guard used to keep one app instance alive."""

    def __init__(
        self,
        name: str = DEFAULT_MUTEX_NAME,
        *,
        kernel32: Any | None = None,
        platform: str = sys.platform,
    ) -> None:
        self._name = name
        self._platform = platform
        self._kernel32 = kernel32
        self._handle: int | None = None
        self.acquired = False

    def _load_kernel32(self) -> Any:
        if self._kernel32 is None:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return self._kernel32

    def acquire(self) -> bool:
        """Acquire the process-wide singleton guard.

        @returns: `True` if this process owns the singleton slot.
        @throws OSError: If Windows cannot create a mutex handle.
        """

        if self._platform != "win32":
            self.acquired = True
            return True

        kernel32 = self._load_kernel32()
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")

        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            self._handle = None
            self.acquired = False
            return False

        self._handle = handle
        self.acquired = True
        return True

    def release(self) -> None:
        """Release the singleton mutex when held."""

        if self._handle is None:
            self.acquired = False
            return
        self._load_kernel32().CloseHandle(self._handle)
        self._handle = None
        self.acquired = False

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
