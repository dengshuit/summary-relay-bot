from __future__ import annotations

import pytest

from summary_relay_bot.services.secrets import SecretError, SecretService, redact_configured_secret


def test_secret_service_encrypts_and_decrypts_without_plaintext_storage() -> None:
    service = SecretService(SecretService.generate_key())

    encrypted = service.encrypt("secret-token")

    assert encrypted != "secret-token"
    assert "secret-token" not in encrypted
    assert service.decrypt(encrypted) == "secret-token"


def test_secret_service_rejects_invalid_key() -> None:
    with pytest.raises(SecretError, match="valid Fernet key"):
        SecretService("not-a-fernet-key")


def test_secret_service_rejects_empty_secret_values() -> None:
    service = SecretService(SecretService.generate_key())

    with pytest.raises(SecretError, match="must not be empty"):
        service.encrypt("")


def test_redact_configured_secret_returns_state_only() -> None:
    assert redact_configured_secret("encrypted-value") == "configured"
    assert redact_configured_secret(None) == "not_configured"
