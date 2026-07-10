from __future__ import annotations


def test_single_instance_acquires_mutex_on_windows() -> None:
    from llanfeng_code_assistant.single_instance import SingleInstance

    class FakeKernel32:
        def __init__(self) -> None:
            self.closed: list[int] = []

        def CreateMutexW(self, security_attributes, initial_owner, name):
            self.name = name
            self.security_attributes = security_attributes
            self.initial_owner = initial_owner
            return 101

        def GetLastError(self) -> int:
            return 0

        def CloseHandle(self, handle: int) -> bool:
            self.closed.append(handle)
            return True

    kernel32 = FakeKernel32()

    with SingleInstance(kernel32=kernel32, platform="win32") as instance:
        assert instance.acquired is True
        assert kernel32.name == "Global\\LlanfengCodeAssistant"
        assert kernel32.closed == []

    assert kernel32.closed == [101]


def test_single_instance_rejects_existing_mutex_on_windows() -> None:
    from llanfeng_code_assistant.single_instance import ERROR_ALREADY_EXISTS, SingleInstance

    class FakeKernel32:
        def __init__(self) -> None:
            self.closed: list[int] = []

        def CreateMutexW(self, security_attributes, initial_owner, name):
            return 202

        def GetLastError(self) -> int:
            return ERROR_ALREADY_EXISTS

        def CloseHandle(self, handle: int) -> bool:
            self.closed.append(handle)
            return True

    kernel32 = FakeKernel32()
    instance = SingleInstance(kernel32=kernel32, platform="win32")

    assert instance.acquire() is False
    assert instance.acquired is False
    assert kernel32.closed == [202]
