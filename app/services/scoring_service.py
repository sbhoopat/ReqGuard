"""Deterministic scoring engine implementing the ReqGuard compliance formula."""

from typing import Dict, List, Optional
from app.models.analysis import ComplianceScore, CriterionVerification
from app.models.requirement import RequirementCriterion, RequirementStatus


class ScoringEngine:
    """
    Deterministic scoring engine calculating requirements compliance coverage.
    Policy:
      - Implemented: 1.0
      - Partial: 0.5
      - Missing: 0.0
      - Needs verification: 0.0

    Formula:
      Coverage percentage = (sum(weight * score) / sum(weights)) * 100
      Rounded to nearest integer.
      All criteria remain in the denominator.
    """

    STATUS_SCORES: Dict[RequirementStatus, float] = {
        RequirementStatus.IMPLEMENTED: 1.0,
        RequirementStatus.PARTIAL: 0.5,
        RequirementStatus.MISSING: 0.0,
        RequirementStatus.NEEDS_VERIFICATION: 0.0,
    }

    @classmethod
    def calculate_score(
        cls,
        requirements: List[RequirementCriterion],
        verifications: List[CriterionVerification]
    ) -> ComplianceScore:
        """
        Calculate compliance score deterministically.
        If no requirements exist, return undefined/unavailable score.
        """
        if not requirements:
            return ComplianceScore(
                coverage_percentage=None,
                implemented_count=0,
                partial_count=0,
                missing_count=0,
                needs_verification_count=0,
                total_requirements=0,
                is_score_available=False,
                score_notes="No acceptance criteria or requirements extracted from Jira."
            )

        # Map verifications by requirement_id
        verif_map: Dict[str, CriterionVerification] = {
            v.requirement_id: v for v in verifications
        }

        weights_used: Dict[str, float] = {}
        total_weight = 0.0
        weighted_score = 0.0

        implemented_count = 0
        partial_count = 0
        missing_count = 0
        needs_verification_count = 0

        for req in requirements:
            weight = req.weight if req.weight > 0 else 1.0
            weights_used[req.id] = weight
            total_weight += weight

            verif = verif_map.get(req.id)
            if verif:
                status = verif.status
            else:
                # If an extracted requirement was not verified by LLM, treat as needs_verification
                status = RequirementStatus.NEEDS_VERIFICATION

            score_val = cls.STATUS_SCORES.get(status, 0.0)
            weighted_score += weight * score_val

            if status == RequirementStatus.IMPLEMENTED:
                implemented_count += 1
            elif status == RequirementStatus.PARTIAL:
                partial_count += 1
            elif status == RequirementStatus.MISSING:
                missing_count += 1
            else:
                needs_verification_count += 1

        if total_weight <= 0.0:
            percentage = 0
        else:
            percentage = round((weighted_score / total_weight) * 100)

        return ComplianceScore(
            coverage_percentage=percentage,
            implemented_count=implemented_count,
            partial_count=partial_count,
            missing_count=missing_count,
            needs_verification_count=needs_verification_count,
            total_requirements=len(requirements),
            weights_used=weights_used,
            is_score_available=True,
            score_notes=None
        )
