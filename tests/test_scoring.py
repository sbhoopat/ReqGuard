"""Unit tests for deterministic scoring engine."""

import pytest
from app.models.analysis import CriterionVerification
from app.models.requirement import RequirementCriterion, RequirementStatus
from app.services.scoring_service import ScoringEngine


def test_empty_requirements_returns_unavailable_score():
    score = ScoringEngine.calculate_score(requirements=[], verifications=[])
    assert score.is_score_available is False
    assert score.coverage_percentage is None
    assert score.total_requirements == 0
    assert score.implemented_count == 0


def test_all_implemented_equal_weights():
    reqs = [
        RequirementCriterion(id="REQ-1", description="Endpoint implemented"),
        RequirementCriterion(id="REQ-2", description="Validation added"),
    ]
    verifs = [
        CriterionVerification(
            requirement_id="REQ-1",
            status=RequirementStatus.IMPLEMENTED,
            explanation="Done",
        ),
        CriterionVerification(
            requirement_id="REQ-2",
            status=RequirementStatus.IMPLEMENTED,
            explanation="Done",
        ),
    ]

    score = ScoringEngine.calculate_score(reqs, verifs)
    assert score.is_score_available is True
    assert score.coverage_percentage == 100
    assert score.implemented_count == 2
    assert score.partial_count == 0
    assert score.missing_count == 0
    assert score.needs_verification_count == 0


def test_mixed_statuses_equal_weights():
    # 1 implemented (1.0), 1 partial (0.5), 1 missing (0.0), 1 needs_verification (0.0)
    # Sum = 1.0 + 0.5 + 0.0 + 0.0 = 1.5 out of 4 -> 1.5 / 4 = 37.5% -> rounds to 38%
    reqs = [
        RequirementCriterion(id="REQ-1", description="One"),
        RequirementCriterion(id="REQ-2", description="Two"),
        RequirementCriterion(id="REQ-3", description="Three"),
        RequirementCriterion(id="REQ-4", description="Four"),
    ]
    verifs = [
        CriterionVerification(requirement_id="REQ-1", status=RequirementStatus.IMPLEMENTED, explanation=""),
        CriterionVerification(requirement_id="REQ-2", status=RequirementStatus.PARTIAL, explanation=""),
        CriterionVerification(requirement_id="REQ-3", status=RequirementStatus.MISSING, explanation=""),
        CriterionVerification(requirement_id="REQ-4", status=RequirementStatus.NEEDS_VERIFICATION, explanation=""),
    ]

    score = ScoringEngine.calculate_score(reqs, verifs)
    assert score.coverage_percentage == 38
    assert score.implemented_count == 1
    assert score.partial_count == 1
    assert score.missing_count == 1
    assert score.needs_verification_count == 1


def test_weighted_scoring():
    # REQ-1 (weight 3.0, implemented 1.0) -> 3.0
    # REQ-2 (weight 1.0, missing 0.0) -> 0.0
    # Total weight = 4.0. Score = 3.0 / 4.0 = 75%
    reqs = [
        RequirementCriterion(id="REQ-1", description="Heavy feature", weight=3.0),
        RequirementCriterion(id="REQ-2", description="Light feature", weight=1.0),
    ]
    verifs = [
        CriterionVerification(requirement_id="REQ-1", status=RequirementStatus.IMPLEMENTED, explanation=""),
        CriterionVerification(requirement_id="REQ-2", status=RequirementStatus.MISSING, explanation=""),
    ]

    score = ScoringEngine.calculate_score(reqs, verifs)
    assert score.coverage_percentage == 75
    assert score.weights_used["REQ-1"] == 3.0
    assert score.weights_used["REQ-2"] == 1.0


def test_unverified_requirement_defaults_to_needs_verification():
    # If 2 requirements extracted, but LLM only evaluated 1
    reqs = [
        RequirementCriterion(id="REQ-1", description="One"),
        RequirementCriterion(id="REQ-2", description="Two"),
    ]
    verifs = [
        CriterionVerification(requirement_id="REQ-1", status=RequirementStatus.IMPLEMENTED, explanation=""),
    ]

    score = ScoringEngine.calculate_score(reqs, verifs)
    assert score.total_requirements == 2
    assert score.implemented_count == 1
    assert score.needs_verification_count == 1
    assert score.coverage_percentage == 50
