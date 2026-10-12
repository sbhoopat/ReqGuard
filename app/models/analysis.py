"""Analysis result and report models."""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.models.requirement import RequirementStatus, RequirementCriterion


class CriterionVerification(BaseModel):
    """Evaluation result for an individual criterion."""
    requirement_id: str = Field(description="Matches RequirementCriterion id")
    status: RequirementStatus = Field(description="Verification status")
    explanation: str = Field(description="Explanation of the evaluation")
    changed_file_paths: List[str] = Field(
        default_factory=list,
        description="List of changed file paths evidencing this criterion"
    )
    quoted_code_evidence: List[str] = Field(
        default_factory=list,
        description="Exact code snippets quoted from PR diff"
    )
    relevant_tests: List[str] = Field(
        default_factory=list,
        description="Relevant test files or test names identified"
    )
    identified_gaps: List[str] = Field(
        default_factory=list,
        description="Identified gaps or missing parts"
    )
    suggested_corrective_action: Optional[str] = Field(
        default=None,
        description="Suggested action to resolve missing/partial requirement"
    )
    evidence_validated: bool = Field(
        default=False,
        description="Whether deterministic evidence validation confirmed the quotes & files"
    )
    downgrade_reason: Optional[str] = Field(
        default=None,
        description="Reason if status was downgraded from implemented to needs_verification"
    )


class RequirementAnalysisResult(BaseModel):
    """Raw output from LLM verification agent."""
    verifications: List[CriterionVerification] = Field(default_factory=list)
    overall_summary: Optional[str] = None


class ComplianceScore(BaseModel):
    """Deterministic score calculated by Python ScoringEngine."""
    coverage_percentage: Optional[int] = Field(
        default=None,
        description="Integer percentage (0-100) or None if no requirements exist"
    )
    implemented_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    needs_verification_count: int = 0
    total_requirements: int = 0
    weights_used: Dict[str, float] = Field(default_factory=dict)
    is_score_available: bool = True
    score_notes: Optional[str] = None


class ComplianceReport(BaseModel):
    """Structured report ready for GitHub PR comment publication."""
    jira_key: Optional[str] = None
    jira_summary: Optional[str] = None
    jira_url: Optional[str] = None
    pr_number: int
    pr_title: str
    pr_url: str
    commit_sha: str
    score: ComplianceScore
    verifications: List[CriterionVerification] = Field(default_factory=list)
    requirements: List[RequirementCriterion] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    markdown_content: str
    comment_marker: str = "<!-- reqguard-ai-report -->"
