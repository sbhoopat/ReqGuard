"""Unit tests for GitHub HMAC signature verification and security sanitization."""

import hashlib
import hmac
import pytest
from app.security.webhook_verification import verify_github_signature, sanitize_untrusted_text


def test_valid_github_signature():
    secret = "test-secret-key"
    payload = b'{"action":"opened","pull_request":{"id":1}}'
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    signature_header = f"sha256={mac.hexdigest()}"

    assert verify_github_signature(payload, signature_header, secret) is True


def test_invalid_github_signature():
    secret = "test-secret-key"
    payload = b'{"action":"opened"}'
    signature_header = "sha256=wrongsignature1234567890abcdef"

    assert verify_github_signature(payload, signature_header, secret) is False


def test_missing_signature():
    assert verify_github_signature(b"data", None, "secret") is False
    assert verify_github_signature(b"data", "", "secret") is False


def test_empty_secret():
    assert verify_github_signature(b"data", "sha256=123", "") is False


def test_sanitize_untrusted_text_truncates_and_strips_null_bytes():
    malicious_input = "Hello\x00World! " + ("A" * 6000)
    sanitized = sanitize_untrusted_text(malicious_input, max_length=50)

    assert "\x00" not in sanitized
    assert len(sanitized) < 100
    assert "... [content truncated for safety]" in sanitized
