from __future__ import annotations

from typing import Protocol

import keyring

from .constants import KEYRING_SERVICE


class SecretStore(Protocol):
    """Secret storage interface."""

    def set_secret(self, reference: str, value: str) -> None:
        """Store a secret value.

        @param reference: Stable secret reference.
        @param value: Secret value.
        """

    def get_secret(self, reference: str) -> str | None:
        """Read a secret value.

        @param reference: Stable secret reference.
        @returns: Secret value, or `None`.
        """

    def delete_secret(self, reference: str) -> None:
        """Delete a secret value.

        @param reference: Stable secret reference.
        """


class KeyringSecretStore:
    """System keyring-backed secret store."""

    def __init__(self, service_name: str = KEYRING_SERVICE) -> None:
        self._service_name = service_name

    def set_secret(self, reference: str, value: str) -> None:
        """Store a secret in the OS credential vault.

        @param reference: Stable secret reference.
        @param value: Secret value.
        """

        keyring.set_password(self._service_name, reference, value)

    def get_secret(self, reference: str) -> str | None:
        """Read a secret from the OS credential vault.

        @param reference: Stable secret reference.
        @returns: Secret value, or `None`.
        """

        return keyring.get_password(self._service_name, reference)

    def delete_secret(self, reference: str) -> None:
        """Delete a secret from the OS credential vault.

        @param reference: Stable secret reference.
        """

        try:
            keyring.delete_password(self._service_name, reference)
        except keyring.errors.PasswordDeleteError:
            return


class MemorySecretStore:
    """In-memory secret store for tests and dry runs."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def set_secret(self, reference: str, value: str) -> None:
        """Store a secret value.

        @param reference: Stable secret reference.
        @param value: Secret value.
        """

        self._values[reference] = value

    def get_secret(self, reference: str) -> str | None:
        """Read a secret value.

        @param reference: Stable secret reference.
        @returns: Secret value, or `None`.
        """

        return self._values.get(reference)

    def delete_secret(self, reference: str) -> None:
        """Delete a secret value.

        @param reference: Stable secret reference.
        """

        self._values.pop(reference, None)
