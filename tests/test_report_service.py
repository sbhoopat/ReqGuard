"""Unit tests for ReportService formatting."""

import pytest
from app.models.analysis import ComplianceScore, CriterionVerification
from app.models.requirement import RequirementCriterion, RequirementStatus
from app.services.report_service import ReportService


def test_markdown_report_formatting():
    score = ComplianceScore(
        coverage_percentage=75,
        implemented_count=3,
        partial_count=1,
        missing_count=0,
        needs_verification_count=0,
        total_requirements=4,
    )
    reqs = [
        RequirementCriterion(id="REQ-1", description="Image upload endpoint"),
        RequirementCriterion(id="REQ-2", description="File type validation"),
    ]
    verifs = [
        CriterionVerification(
            requirement_id="REQ-1",
            status=RequirementStatus.IMPLEMENTED,
            explanation="Endpoint created in app/routes.py",
            changed_file_paths=["app/routes.py"],
            quoted_code_evidence=["@router.post('/upload')"],
        ),
        CriterionVerification(
            requirement_id="REQ-2",
            status=RequirementStatus.PARTIAL,
            explanation="Only PNG checked, JPEG missing",
            suggested_corrective_action="Add JPEG support",
        ),
    ]

    report = ReportService.build_report(
        jira_key="PROJ-123",
        jira_summary="Upload image capability",
        jira_url="https://jira.example.com/browse/PROJ-123",
        pr_number=42,
        pr_title="feat: add upload endpoint",
        pr_url="https://github.com/org/repo/pull/42",
        commit_sha="abcdef1234567890",
        score=score,
        requirements=reqs,
        verifications=verifs,
        warnings=["Test warning"],
    )

    md = report.markdown_content
    assert ReportService.COMMENT_MARKER in md
    assert "PROJ-123" in md
    assert "**Estimated coverage:** 75%" in md
    assert "- [x] **REQ-1**" in md
    assert "- [~] **REQ-2**" in md
    assert "Add JPEG support" in md
    assert "Test warning" in md
    assert "AI-assisted and intended for engineer review" in md
