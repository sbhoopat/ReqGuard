"""LangGraph typed graph state definition."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from app.models.analysis import ComplianceReport, ComplianceScore, CriterionVerification
from app.models.requirement import RequirementCriterion


class ReqGuardGraphState(TypedDict, total=False):
    """
    Typed state object managed throughout the LangGraph workflow.
    """
    # PR Metadata
    repo_full_name: str
    pr_number: int
    pr_title: str
    pr_body: str
    branch_name: str
    commit_sha: str
    pr_url: str

    # Jira Key & Data
    jira_key: Optional[str]
    jira_summary: Optional[str]
    jira_description: Optional[str]
    jira_acceptance_criteria: Optional[str]
    jira_subtasks: List[str]
    jira_url: Optional[str]

    # PR Code Changes
    changed_files: List[Dict[str, Any]]
    diff_text: str

    # Decomposed Criteria
    requirements: List[RequirementCriterion]
    has_ambiguous_requirements: bool

    # Technical Diff Summary
    code_summary_notes: str

    # Verification Findings
    verifications: List[CriterionVerification]

    # Deterministic Score
    score: ComplianceScore

    # Report & Comments
    report: ComplianceReport
    comment_published: bool
    comment_id: Optional[int]

    # Execution Metadata & Guardrails
    investigation_attempts: int
    warnings: List[str]
    error_message: Optional[str]
    status: str
