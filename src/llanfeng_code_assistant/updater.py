"""Auto-update checker that queries the GitHub releases API."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


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
    c = _parse_version(candidate)
    base = _parse_version(current)
    # Pad to equal length so (1,) == (1, 0, 0)
    length = max(len(c), len(base))
    c += (0,) * (length - len(c))
    base += (0,) * (length - len(base))
    return c > base


@dataclass(frozen=True)
class ReleaseInfo:
    """Metadata for a published GitHub release."""

    version: str
    """Tag version with the leading ``v`` stripped."""

    download_url: str
    """Direct URL for the ``.exe`` installer asset, or the release HTML page."""

    changelog: str
    """Release body / notes published on GitHub."""


class UpdateChecker:
    """Async update checker that queries the GitHub releases API.

    Usage::

        checker = UpdateChecker(GITHUB_RELEASES_LATEST_URL, __version__)
        info = await checker.check()
        if info:
            # A newer version exists — show the banner
            ...
    """

    def __init__(self, releases_url: str, current_version: str) -> None:
        """
        @param releases_url: ``/releases/latest`` API endpoint URL.
        @param current_version: Semver string of the currently running build.
        """
        self._releases_url = releases_url
        self._current_version = current_version

    async def check(self) -> ReleaseInfo | None:
        """Fetch the latest GitHub release and return info if it is newer.

        Silently swallows all network and parse errors so a flaky connection
        never surfaces an unhandled exception to the user.

        @returns: :class:`ReleaseInfo` when a newer version is available,
            ``None`` otherwise (up-to-date or unreachable).
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self._releases_url,
                    headers={"Accept": "application/vnd.github+json"},
                    follow_redirects=True,
                )
                response.raise_for_status()
                data: dict = response.json()
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
            return None

        tag: str = data.get("tag_name", "").lstrip("vV")
        body: str = data.get("body", "")
        assets: list[dict] = data.get("assets", [])

        # Prefer a direct .exe asset; fall back to the release HTML page.
        exe_asset = next(
            (a for a in assets if a.get("name", "").endswith(".exe")),
            None,
        )
        download_url: str = (
            exe_asset["browser_download_url"]
            if exe_asset
            else data.get("html_url", "")
        )

        if not tag or not download_url:
            return None

        if not is_newer(tag, self._current_version):
            return None

        return ReleaseInfo(version=tag, download_url=download_url, changelog=body)
