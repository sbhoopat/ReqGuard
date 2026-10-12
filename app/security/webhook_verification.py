"""Webhook signature verification and security utilities."""

import hmac
import hashlib
from typing import Tuple
from fastapi import Request, HTTPException, status
from app.config import settings


def verify_github_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Verify GitHub X-Hub-Signature-256 HMAC SHA-256 signature.
    Signature header format: sha256=<hex_digest>
    """
    if not signature_header:
        return False
    if not secret:
        # In production, secret MUST be configured
        return False

    elements = signature_header.split("=", 1)
    if len(elements) != 2 or elements[0].lower() != "sha256":
        return False

    expected_sig = elements[1].strip()
    mac = hmac.new(secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    computed_sig = mac.hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


def sanitize_untrusted_text(text: str, max_length: int = 5000) -> str:
    """
    Sanitize external text from PRs, Jira, comments to prevent prompt injection or formatting breaks.
    Replaces null bytes and trims to maximum length.
    """
    if not text:
        return ""
    # Strip null bytes and normalize line endings
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "\n... [content truncated for safety]"
    return cleaned
