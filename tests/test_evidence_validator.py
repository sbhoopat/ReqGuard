"""Unit tests for deterministic evidence validation and guardrails."""

import pytest
from app.models.analysis import CriterionVerification, RequirementAnalysisResult
from app.models.requirement import RequirementStatus
from app.services.evidence_validator import EvidenceValidator


def test_valid_evidence_passes():
    diff = """
diff --git a/app/routes/upload.py b/app/routes/upload.py
--- a/app/routes/upload.py
+++ b/app/routes/upload.py
@@ -10,4 +10,6 @@
+if file.size > 10 * 1024 * 1024:
+    raise HTTPException(status_code=400, detail="File too large")
"""
    v = CriterionVerification(
        requirement_id="REQ-1",
        status=RequirementStatus.IMPLEMENTED,
        explanation="File size check added",
        changed_file_paths=["app/routes/upload.py"],
        quoted_code_evidence=['if file.size > 10 * 1024 * 1024:'],
    )

    validated = EvidenceValidator.validate_verification(
        verification=v,
        valid_file_paths=["app/routes/upload.py"],
        raw_diff=diff,
    )

    assert validated.status == RequirementStatus.IMPLEMENTED
    assert validated.evidence_validated is True
    assert validated.downgrade_reason is None


def test_invalid_file_downgrades_implemented_status():
    diff = "+print('hello')"
    v = CriterionVerification(
        requirement_id="REQ-1",
        status=RequirementStatus.IMPLEMENTED,
        explanation="File size check",
        changed_file_paths=["nonexistent_file.py"],
        quoted_code_evidence=["print('hello')"],
    )

    validated = EvidenceValidator.validate_verification(
        verification=v,
        valid_file_paths=["app/main.py"],
        raw_diff=diff,
    )

    assert validated.status == RequirementStatus.NEEDS_VERIFICATION
    assert validated.evidence_validated is False
    assert "Cited files not in PR: nonexistent_file.py" in validated.downgrade_reason


def test_quote_not_in_diff_downgrades_status():
    diff = """
+def upload_image():
+    return True
"""
    v = CriterionVerification(
        requirement_id="REQ-1",
        status=RequirementStatus.IMPLEMENTED,
        explanation="Validates max size",
        changed_file_paths=["app/upload.py"],
        quoted_code_evidence=["validate_file_size(10)"],  # hallucinated quote
    )

    validated = EvidenceValidator.validate_verification(
        verification=v,
        valid_file_paths=["app/upload.py"],
        raw_diff=diff,
    )

    assert validated.status == RequirementStatus.NEEDS_VERIFICATION
    assert validated.evidence_validated is False
    assert "Cited code snippet(s) not found in PR diff" in validated.downgrade_reason


def test_empty_evidence_downgrades_status():
    diff = "+x = 1"
    v = CriterionVerification(
        requirement_id="REQ-1",
        status=RequirementStatus.IMPLEMENTED,
        explanation="Implemented",
        changed_file_paths=[],
        quoted_code_evidence=[],
    )

    validated = EvidenceValidator.validate_verification(
        verification=v,
        valid_file_paths=["app/upload.py"],
        raw_diff=diff,
    )

    assert validated.status == RequirementStatus.NEEDS_VERIFICATION
    assert validated.evidence_validated is False
    assert "No file paths or code evidence provided" in validated.downgrade_reason


def test_missing_and_partial_are_not_downgraded_but_marked_unvalidated():
    diff = "+x = 1"
    v = CriterionVerification(
        requirement_id="REQ-1",
        status=RequirementStatus.MISSING,
        explanation="Not found in PR",
        changed_file_paths=[],
        quoted_code_evidence=[],
    )

    validated = EvidenceValidator.validate_verification(
        verification=v,
        valid_file_paths=["app/upload.py"],
        raw_diff=diff,
    )

    assert validated.status == RequirementStatus.MISSING
    assert validated.evidence_validated is False
    assert validated.downgrade_reason is None
