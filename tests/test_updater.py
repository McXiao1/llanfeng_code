from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from llanfeng_code_assistant.updater import (
    DownloadProgress,
    ReleaseInfo,
    UpdateChecker,
    UpdateDownloadError,
    UpdateInstallerService,
    is_newer,
)


def test_is_newer_normalizes_prefix_and_missing_version_parts() -> None:
    assert is_newer("v1.2.1", "1.2") is True
    assert is_newer("1.2", "1.2.0") is False
    assert is_newer("invalid", "1.0.0") is False


async def test_update_checker_prefers_setup_asset_and_reads_integrity_metadata() -> None:
    digest = "a" * 64

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "llanfeng-code-assistant"
        return httpx.Response(
            200,
            json={
                "tag_name": "v1.2.0",
                "body": "Changes",
                "assets": [
                    {
                        "name": "Llanfeng-Code-Assistant-Portable-1.2.0.exe",
                        "browser_download_url": "https://github.com/example/portable.exe",
                        "size": 12,
                    },
                    {
                        "name": "Llanfeng-Code-Assistant-Setup-1.2.0.exe",
                        "browser_download_url": "https://github.com/example/setup.exe",
                        "size": 34,
                        "digest": f"sha256:{digest}",
                    },
                ],
            },
        )

    checker = UpdateChecker(
        "https://api.github.com/repos/example/app/releases/latest",
        "1.1.1",
        transport=httpx.MockTransport(handler),
    )

    release = await checker.check()

    assert release == ReleaseInfo(
        version="1.2.0",
        download_url="https://github.com/example/setup.exe",
        changelog="Changes",
        filename="Llanfeng-Code-Assistant-Setup-1.2.0.exe",
        download_size=34,
        sha256=digest,
    )


async def test_update_checker_ignores_release_without_direct_installer() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "tag_name": "v9.0.0",
                "html_url": "https://github.com/example/releases/tag/v9.0.0",
                "assets": [
                    {
                        "name": "Llanfeng-Code-Assistant-Portable.exe",
                        "browser_download_url": "https://github.com/example/portable.exe",
                    },
                    {"name": "checksums.txt"},
                ],
            },
        )
    )
    checker = UpdateChecker(
        "https://api.github.com/repos/example/app/releases/latest",
        "1.0.0",
        transport=transport,
    )

    assert await checker.check() is None


async def test_update_installer_downloads_to_app_directory_and_reports_progress(
    tmp_path: Path,
) -> None:
    payload = b"MZ" + (b"update-data" * 40_000)
    digest = hashlib.sha256(payload).hexdigest()
    progress: list[DownloadProgress] = []
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=payload,
            headers={"Content-Length": str(len(payload))},
            request=request,
        )
    )
    release = ReleaseInfo(
        version="1.2.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="Llanfeng-Code-Assistant-Setup-1.2.0.exe",
        download_size=len(payload),
        sha256=digest,
    )
    service = UpdateInstallerService(tmp_path, transport=transport)

    installer_path = await service.download(release, progress.append)

    assert installer_path == tmp_path / release.filename
    assert installer_path.read_bytes() == payload
    assert not (tmp_path / f"{release.filename}.part").exists()
    assert progress
    assert progress[-1].downloaded_bytes == len(payload)
    assert progress[-1].total_bytes == len(payload)
    assert progress[-1].fraction == 1.0


async def test_update_installer_deletes_partial_file_when_digest_mismatches(
    tmp_path: Path,
) -> None:
    payload = b"MZ-invalid-installer"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=payload, request=request)
    )
    release = ReleaseInfo(
        version="1.2.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="Setup.exe",
        download_size=len(payload),
        sha256="0" * 64,
    )
    service = UpdateInstallerService(tmp_path, transport=transport)

    with pytest.raises(UpdateDownloadError, match="校验失败"):
        await service.download(release)

    assert not (tmp_path / "Setup.exe").exists()
    assert not (tmp_path / "Setup.exe.part").exists()


async def test_update_installer_rejects_unsafe_installer_filename(tmp_path: Path) -> None:
    release = ReleaseInfo(
        version="1.2.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="../Setup.exe",
    )
    service = UpdateInstallerService(tmp_path)

    with pytest.raises(UpdateDownloadError, match="文件名无效"):
        await service.download(release)



def test_update_installer_starts_downloaded_setup_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer_path = tmp_path / "Setup.exe"
    installer_path.write_bytes(b"MZ")
    launched: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(command: list[str], **kwargs: object) -> object:
        launched.append((command, kwargs))
        return object()

    monkeypatch.setattr("llanfeng_code_assistant.updater.subprocess.Popen", fake_popen)
    service = UpdateInstallerService(tmp_path)

    service.start_installer(installer_path)

    assert len(launched) == 1
    command, kwargs = launched[0]
    assert command == [
        str(installer_path.resolve()),
        "/SP-",
        "/CLOSEAPPLICATIONS",
    ]
    assert kwargs == {"cwd": str(tmp_path.resolve()), "close_fds": True}
