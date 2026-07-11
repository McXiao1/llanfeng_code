"""In-app update checking, installer downloading, and installer launch support."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import httpx

from .paths import downloads_dir

logger = logging.getLogger(__name__)

_DOWNLOAD_CHUNK_SIZE = 256 * 1024
_PROGRESS_UPDATE_INTERVAL_SECONDS = 0.1
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple.

    Strips a leading ``v`` or ``V`` prefix and splits on ``.``.

    @param v: Version string such as ``"1.2.3"`` or ``"v1.2.3"``.
    @returns: Integer tuple suitable for comparison.
    """
    try:
        return tuple(int(x) for x in v.strip().lstrip("vV").split("."))
    except ValueError:
        return (0,)


def is_newer(candidate: str, current: str) -> bool:
    """Return True when *candidate* is strictly newer than *current*.

    @param candidate: Version string to test (e.g. ``"1.1.1"``).
    @param current: Currently running version string.
    @returns: Whether the candidate version is greater.
    """
    candidate_parts = _parse_version(candidate)
    current_parts = _parse_version(current)
    length = max(len(candidate_parts), len(current_parts))
    candidate_parts += (0,) * (length - len(candidate_parts))
    current_parts += (0,) * (length - len(current_parts))
    return candidate_parts > current_parts


@dataclass(frozen=True)
class ReleaseInfo:
    """Metadata for a published GitHub release installer."""

    version: str
    """Tag version with the leading ``v`` stripped."""

    download_url: str
    """Direct HTTPS URL for the Windows ``.exe`` installer asset."""

    changelog: str
    """Release body / notes published on GitHub."""

    filename: str = ""
    """Installer asset filename."""

    download_size: int | None = None
    """Expected installer size in bytes, when supplied by GitHub."""

    sha256: str | None = None
    """Expected lowercase SHA-256 digest, when supplied by GitHub."""


@dataclass(frozen=True)
class DownloadProgress:
    """Progress snapshot emitted while an update installer is downloaded."""

    downloaded_bytes: int
    """Number of bytes written to the temporary installer file."""

    total_bytes: int | None
    """Expected total byte count, or ``None`` when the server did not provide it."""

    @property
    def fraction(self) -> float | None:
        """Return progress in the inclusive range 0..1 when total size is known.

        @returns: Fractional progress, or ``None`` for indeterminate downloads.
        """
        if self.total_bytes is None or self.total_bytes <= 0:
            return None
        return min(self.downloaded_bytes / self.total_bytes, 1.0)


ProgressCallback = Callable[[DownloadProgress], None]


class UpdateDownloadError(RuntimeError):
    """Raised when an update installer cannot be safely downloaded."""


class UpdateInstallationError(RuntimeError):
    """Raised when a downloaded update installer cannot be started."""


def _parse_sha256_digest(raw_digest: object) -> str | None:
    if not isinstance(raw_digest, str):
        return None
    algorithm, separator, digest = raw_digest.strip().partition(":")
    if separator != ":" or algorithm.lower() != "sha256":
        return None
    return digest.lower() if _SHA256_PATTERN.fullmatch(digest) else None


def _select_installer_asset(raw_assets: object) -> dict[str, object] | None:
    if not isinstance(raw_assets, list):
        return None

    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            continue
        name = raw_asset.get("name")
        url = raw_asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and "setup" in name.lower()
            and name.lower().endswith(".exe")
            and isinstance(url, str)
            and url
        ):
            return raw_asset
    return None


class UpdateChecker:
    """Async update checker that queries the GitHub releases API.

    Usage::

        checker = UpdateChecker(GITHUB_RELEASES_LATEST_URL, __version__)
        info = await checker.check()
        if info:
            # A newer version exists — show the in-app download banner
            ...
    """

    def __init__(
        self,
        releases_url: str,
        current_version: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the release checker.

        @param releases_url: ``/releases/latest`` API endpoint URL.
        @param current_version: Semver string of the currently running build.
        @param transport: Optional HTTP transport used by tests or custom hosts.
        """
        self._releases_url = releases_url
        self._current_version = current_version
        self._transport = transport

    async def check(self) -> ReleaseInfo | None:
        """Fetch the latest GitHub release and return info if it is newer.

        Network and parse failures are logged at debug level so a flaky
        connection never interrupts application startup. Releases without a
        direct Windows installer are ignored because updates must stay inside
        the application instead of opening a browser page.

        @returns: :class:`ReleaseInfo` when a newer downloadable version is
            available, otherwise ``None``.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.get(
                    self._releases_url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "llanfeng-code-assistant",
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
            return None

        if not isinstance(data, dict):
            return None

        raw_tag = data.get("tag_name")
        tag = raw_tag.lstrip("vV") if isinstance(raw_tag, str) else ""
        if not tag or not is_newer(tag, self._current_version):
            return None

        installer_asset = _select_installer_asset(data.get("assets"))
        if installer_asset is None:
            return None

        raw_name = installer_asset.get("name")
        raw_url = installer_asset.get("browser_download_url")
        if not isinstance(raw_name, str) or not isinstance(raw_url, str):
            return None

        raw_body = data.get("body")
        changelog = raw_body if isinstance(raw_body, str) else ""
        raw_size = installer_asset.get("size")
        download_size = raw_size if type(raw_size) is int and raw_size > 0 else None

        return ReleaseInfo(
            version=tag,
            download_url=raw_url,
            changelog=changelog,
            filename=raw_name,
            download_size=download_size,
            sha256=_parse_sha256_digest(installer_asset.get("digest")),
        )


class UpdateInstallerService:
    """Download verified update installers and start the local setup program."""

    def __init__(
        self,
        download_dir: Path | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the update installer service.

        @param download_dir: Application-owned directory for update installers.
        @param transport: Optional HTTP transport used by tests or custom hosts.
        """
        self._download_dir = download_dir or downloads_dir()
        self._transport = transport

    async def download(
        self,
        release: ReleaseInfo,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        """Download an installer to a temporary file and verify it before use.

        The final ``.exe`` path is only created after the byte count and the
        optional GitHub SHA-256 digest match. Partial files are deleted on all
        error and cancellation paths.

        @param release: Release metadata containing the direct installer URL.
        @param on_progress: Optional throttled progress callback.
        @returns: Verified local installer path.
        @throws UpdateDownloadError: If the URL, response, file, or integrity
            validation is invalid.
        """
        self._validate_download_url(release.download_url)
        filename = self._installer_filename(release)
        expected_size = self._expected_size(release.download_size)
        expected_sha256 = self._expected_sha256(release.sha256)
        destination = self._download_dir / filename
        partial_path = destination.with_name(f"{destination.name}.part")
        completed = False

        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
            downloaded_bytes = 0
            timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    transport=self._transport,
                    follow_redirects=True,
                ) as client,
                client.stream(
                    "GET",
                    release.download_url,
                    headers={
                        "Accept": "application/octet-stream",
                        "Accept-Encoding": "identity",
                        "User-Agent": "llanfeng-code-assistant",
                    },
                ) as response,
            ):
                response.raise_for_status()
                self._validate_download_url(str(response.url))
                response_size = self._response_size(response)
                if (
                    expected_size is not None
                    and response_size is not None
                    and expected_size != response_size
                ):
                    raise UpdateDownloadError("安装包大小与发布信息不一致: 已取消下载")
                total_bytes = expected_size or response_size
                digest = hashlib.sha256()
                last_progress_at = 0.0
                last_reported_bytes = -1

                with partial_path.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes(_DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        downloaded_bytes += len(chunk)
                        if total_bytes is not None and downloaded_bytes > total_bytes:
                            raise UpdateDownloadError("安装包大小超出发布信息: 已取消下载")
                        file_handle.write(chunk)
                        digest.update(chunk)

                        now = time.monotonic()
                        should_report = (
                            now - last_progress_at >= _PROGRESS_UPDATE_INTERVAL_SECONDS
                            or downloaded_bytes == total_bytes
                        )
                        if on_progress is not None and should_report:
                            on_progress(DownloadProgress(downloaded_bytes, total_bytes))
                            last_progress_at = now
                            last_reported_bytes = downloaded_bytes

                    file_handle.flush()
                    os.fsync(file_handle.fileno())

                if downloaded_bytes <= 0:
                    raise UpdateDownloadError("下载到的安装包为空: 请重试")
                if total_bytes is not None and downloaded_bytes != total_bytes:
                    raise UpdateDownloadError("安装包下载不完整: 请重试")
                if expected_sha256 is not None and not hmac.compare_digest(
                    digest.hexdigest(), expected_sha256
                ):
                    raise UpdateDownloadError("安装包校验失败: 已删除临时文件")

                final_total = total_bytes or downloaded_bytes
                if on_progress is not None and last_reported_bytes != downloaded_bytes:
                    on_progress(DownloadProgress(downloaded_bytes, final_total))

            os.replace(partial_path, destination)
            completed = True
            return destination
        except UpdateDownloadError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("Update installer download failed: %s", exc)
            raise UpdateDownloadError("下载安装包失败: 请检查网络连接后重试") from exc
        except OSError as exc:
            logger.warning("Unable to save update installer: %s", exc)
            raise UpdateDownloadError("无法保存安装包: 请检查磁盘空间和目录权限") from exc
        finally:
            if not completed:
                try:
                    partial_path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.debug("Unable to remove partial update installer: %s", exc)

    def start_installer(self, path: Path) -> None:
        """Start a verified Inno Setup installer without opening a browser.

        @param path: Installer path returned by :meth:`download`.
        @throws UpdateInstallationError: If the path is invalid or setup cannot
            be started.
        """
        try:
            installer_path = path.resolve(strict=True)
            download_root = self._download_dir.resolve(strict=True)
        except OSError as exc:
            raise UpdateInstallationError("本地安装包不存在: 请重新下载") from exc

        if (
            not installer_path.is_file()
            or installer_path.parent != download_root
            or installer_path.suffix.lower() != ".exe"
        ):
            raise UpdateInstallationError("本地安装包路径无效: 请重新下载")

        try:
            subprocess.Popen(
                [str(installer_path), "/SP-", "/CLOSEAPPLICATIONS"],
                cwd=str(installer_path.parent),
                close_fds=True,
            )
        except OSError as exc:
            logger.warning("Unable to start update installer: %s", exc)
            raise UpdateInstallationError("无法启动安装程序: 请稍后重试") from exc

    @staticmethod
    def _validate_download_url(url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise UpdateDownloadError("更新地址无效: 已取消下载")

    @staticmethod
    def _installer_filename(release: ReleaseInfo) -> str:
        filename = release.filename.strip()
        if not filename:
            filename = unquote(PurePosixPath(urlsplit(release.download_url).path).name)

        invalid_characters = '<>:"/\\|?*'
        if (
            not filename
            or filename in {".", ".."}
            or not filename.lower().endswith(".exe")
            or filename.endswith((" ", "."))
            or any(character in invalid_characters for character in filename)
            or any(ord(character) < 32 for character in filename)
        ):
            raise UpdateDownloadError("安装包文件名无效: 已取消下载")
        return filename

    @staticmethod
    def _expected_size(raw_size: int | None) -> int | None:
        if raw_size is None:
            return None
        if raw_size <= 0:
            raise UpdateDownloadError("安装包大小信息无效: 已取消下载")
        return raw_size

    @staticmethod
    def _expected_sha256(raw_digest: str | None) -> str | None:
        if raw_digest is None:
            return None
        if not _SHA256_PATTERN.fullmatch(raw_digest):
            raise UpdateDownloadError("安装包校验信息无效: 已取消下载")
        return raw_digest.lower()

    @staticmethod
    def _response_size(response: httpx.Response) -> int | None:
        raw_size = response.headers.get("Content-Length")
        if raw_size is None:
            return None
        try:
            parsed_size = int(raw_size)
        except ValueError:
            return None
        return parsed_size if parsed_size > 0 else None
