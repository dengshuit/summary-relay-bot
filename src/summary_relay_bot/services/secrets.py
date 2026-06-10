from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SecretError(ValueError):
    pass


class SecretService:
    def __init__(self, encryption_key: str) -> None:
        try:
            self._fernet = Fernet(encryption_key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise SecretError("SETTINGS_ENCRYPTION_KEY must be a valid Fernet key") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")

    def encrypt(self, value: str) -> str:
        if value == "":
            raise SecretError("secret value must not be empty")
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_value: str) -> str:
        if encrypted_value == "":
            raise SecretError("encrypted secret value must not be empty")
        try:
            return self._fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretError("encrypted secret value cannot be decrypted") from exc


def redact_configured_secret(value: str | None) -> str:
    return "configured" if value else "not_configured"
