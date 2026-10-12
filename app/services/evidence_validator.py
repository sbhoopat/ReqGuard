"""Deterministic evidence validator to verify LLM citations against actual PR diff and file list."""

import logging
from typing import List, Tuple
from app.models.analysis import CriterionVerification, RequirementAnalysisResult
from app.models.requirement import RequirementStatus

logger = logging.getLogger(__name__)


class EvidenceValidator:
    """
    Validates LLM-generated code evidence against actual ground-truth PR files and diff.
    Downgrades 'implemented' finding to 'needs_verification' if cited files or quotes
    do not exist in the PR diff.
    """

    @staticmethod
    def normalize_snippet(text: str) -> str:
        """Normalize whitespace for resilient substring matching."""
        if not text:
            return ""
        # Remove empty lines and trailing/leading whitespace per line
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        return "\n".join(lines)

    @classmethod
    def validate_verification(
        cls,
        verification: CriterionVerification,
        valid_file_paths: List[str],
        raw_diff: str
    ) -> CriterionVerification:
        """
        Validate single criterion verification.
        Rules:
        1. All cited file paths must exist in valid_file_paths.
        2. All quoted code evidence must exist in the raw diff (or normalized form).
        3. If status is 'implemented' and evidence fails or is empty, downgrade to 'needs_verification'.
        """
        # Ensure valid_file_paths set
        file_set = {f.lower().strip() for f in valid_file_paths if f}
        raw_diff_clean = cls.normalize_snippet(raw_diff)

        # Check files
        invalid_files = []
        for file_path in verification.changed_file_paths:
            if file_path.lower().strip() not in file_set:
                invalid_files.append(file_path)

        # Check quoted evidence
        invalid_quotes = []
        for quote in verification.quoted_code_evidence:
            quote_clean = cls.normalize_snippet(quote)
            if not quote_clean:
                continue
            # Match directly in raw diff or normalized diff
            if quote not in raw_diff and quote_clean not in raw_diff_clean:
                invalid_quotes.append(quote)

        # Check if validation succeeded
        has_file_errors = len(invalid_files) > 0
        has_quote_errors = len(invalid_quotes) > 0
        has_no_evidence = (
            len(verification.changed_file_paths) == 0 and len(verification.quoted_code_evidence) == 0
        )

        if not has_file_errors and not has_quote_errors and not has_no_evidence:
            verification.evidence_validated = True
            return verification

        # If it was marked implemented, but fails evidence check:
        if verification.status == RequirementStatus.IMPLEMENTED:
            reasons = []
            if invalid_files:
                reasons.append(f"Cited files not in PR: {', '.join(invalid_files)}")
            if invalid_quotes:
                reasons.append(f"Cited code snippet(s) not found in PR diff")
            if has_no_evidence:
                reasons.append("No file paths or code evidence provided")

            downgrade_reason = "; ".join(reasons)
            logger.warning(
                f"Downgrading requirement {verification.requirement_id} from IMPLEMENTED to NEEDS_VERIFICATION: {downgrade_reason}"
            )
            verification.status = RequirementStatus.NEEDS_VERIFICATION
            verification.downgrade_reason = downgrade_reason
            verification.evidence_validated = False
            verification.identified_gaps.append(
                f"[Evidence Check Downgrade] Claimed implemented but failed evidence validation: {downgrade_reason}"
            )
        else:
            # If already partial, missing, or needs_verification, record evidence_validated as False
            verification.evidence_validated = False

        return verification

    @classmethod
    def validate_analysis_result(
        cls,
        analysis_result: RequirementAnalysisResult,
        valid_file_paths: List[str],
        raw_diff: str
    ) -> RequirementAnalysisResult:
        """Validate all verifications in the analysis result."""
        validated_verifications = []
        for v in analysis_result.verifications:
            validated_verifications.append(
                cls.validate_verification(v, valid_file_paths, raw_diff)
            )
        analysis_result.verifications = validated_verifications
        return analysis_result
