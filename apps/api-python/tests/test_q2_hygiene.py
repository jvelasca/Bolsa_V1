"""Tests Q2.4 log redact."""

from bolsa_api.logging_redact import redact_text


def test_redact_authorization_and_password() -> None:
    s = redact_text("Authorization: Bearer secret-token password=hunter2")
    assert "secret-token" not in s
    assert "hunter2" not in s
    assert "***" in s
