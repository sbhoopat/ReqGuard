"""Workflow node functions for the LangGraph orchestration."""

import logging
from typing import Any, Dict, List
from app.config import settings
from app.graph.state import ReqGuardGraphState
from app.integrations.jira_client import JiraCloudClient
from app.integrations.github_client import GitHubClient
from app.integrations.groq_provider import LLMProvider, GroqProvider
from app.agents.requirement_agent import JiraRequirementAgent
from app.agents.code_analysis_agent import CodeAnalysisAgent
from app.agents.verification_agent import RequirementVerificationAgent
from app.services.evidence_validator import EvidenceValidator
from app.services.scoring_service import ScoringEngine
from app.services.report_service import ReportService
from app.models.requirement import RequirementStatus, RequirementCriterion

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """Encapsulates node execution logic for LangGraph."""

    def __init__(
        self,
        jira_client: JiraCloudClient,
        github_client: GitHubClient,
        llm_provider: LLMProvider
    ):
        self.jira_client = jira_client
        self.github_client = github_client
        self.llm_provider = llm_provider
        self.req_agent = JiraRequirementAgent(llm_provider)
        self.code_agent = CodeAnalysisAgent(llm_provider)
        self.verif_agent = RequirementVerificationAgent(llm_provider)

    async def fetch_jira_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Fetch Jira ticket data using Jira REST API v3."""
        jira_key = state.get("jira_key")
        warnings = list(state.get("warnings", []))

        if not jira_key:
            logger.info("No Jira key present in PR metadata.")
            warnings.append("No Jira issue key detected in PR title, body, or branch name.")
            return {
                **state,
                "warnings": warnings,
                "status": "missing_jira_key"
            }

        try:
            issue_data = await self.jira_client.get_issue(jira_key)
            return {
                **state,
                "jira_summary": issue_data.get("summary", ""),
                "jira_description": issue_data.get("description", ""),
                "jira_acceptance_criteria": issue_data.get("acceptance_criteria", ""),
                "jira_subtasks": issue_data.get("subtasks", []),
                "jira_url": issue_data.get("issue_url", ""),
                "warnings": warnings,
            }
        except Exception as e:
            logger.error(f"Error fetching Jira issue {jira_key}: {e}")
            warnings.append(f"Failed to fetch Jira ticket {jira_key}: {str(e)}")
            return {
                **state,
                "warnings": warnings,
                "status": "jira_fetch_failed"
            }

    async def fetch_pr_changes_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Fetch PR changed files list and raw diff from GitHub."""
        repo = state["repo_full_name"]
        pr_number = state["pr_number"]
        warnings = list(state.get("warnings", []))

        try:
            files = await self.github_client.get_pull_request_files(repo, pr_number)
            diff_text = await self.github_client.get_pull_request_diff(repo, pr_number)

            if not diff_text.strip():
                warnings.append("PR diff is empty or unavailable.")

            return {
                **state,
                "changed_files": files,
                "diff_text": diff_text,
                "warnings": warnings,
            }
        except Exception as e:
            logger.error(f"Error fetching GitHub changes for {repo}#{pr_number}: {e}")
            warnings.append(f"Failed to fetch GitHub PR changes: {str(e)}")
            return {
                **state,
                "changed_files": [],
                "diff_text": "",
                "warnings": warnings,
                "status": "github_fetch_failed"
            }

    async def extract_criteria_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Decompose Jira acceptance criteria into structured requirements."""
        jira_key = state.get("jira_key")
        jira_desc = state.get("jira_description", "")
        jira_ac = state.get("jira_acceptance_criteria", "")
        jira_summary = state.get("jira_summary", "")
        jira_subtasks = state.get("jira_subtasks", [])
        warnings = list(state.get("warnings", []))

        if not jira_key or (not jira_desc and not jira_ac):
            warnings.append("No Jira description or acceptance criteria found to decompose.")
            return {
                **state,
                "requirements": [],
                "warnings": warnings,
                "status": "no_criteria"
            }

        try:
            req_list = await self.req_agent.decompose_requirements(
                ticket_key=jira_key,
                summary=jira_summary,
                description=jira_desc,
                acceptance_criteria=jira_ac,
                subtasks=jira_subtasks
            )

            if req_list.has_ambiguous_requirements:
                warnings.append("Some Jira acceptance criteria were flagged as ambiguous or lacked detail.")

            if not req_list.requirements:
                warnings.append("Zero discrete requirements could be decomposed from the Jira ticket.")

            return {
                **state,
                "requirements": req_list.requirements,
                "has_ambiguous_requirements": req_list.has_ambiguous_requirements,
                "warnings": warnings,
            }
        except Exception as e:
            logger.error(f"Error extracting criteria: {e}")
            warnings.append(f"Requirement decomposition error: {str(e)}")
            return {
                **state,
                "requirements": [],
                "warnings": warnings,
            }

    async def analyze_requirements_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Analyze PR diff and evaluate each requirement."""
        requirements = state.get("requirements", [])
        changed_files = state.get("changed_files", [])
        diff_text = state.get("diff_text", "")
        warnings = list(state.get("warnings", []))

        if not requirements:
            return {
                **state,
                "verifications": [],
                "code_summary_notes": "No requirements extracted to verify.",
                "warnings": warnings,
            }

        # Step A: Summarize code changes
        code_summary = await self.code_agent.analyze_pr_diff(
            changed_files=changed_files,
            diff_text=diff_text,
            pr_title=state.get("pr_title", ""),
            pr_description=state.get("pr_body", "")
        )

        code_notes = (
            f"Endpoints: {', '.join(code_summary.endpoints_modified)}; "
            f"Models: {', '.join(code_summary.models_or_schemas)}; "
            f"Validations: {', '.join(code_summary.validation_logic)}; "
            f"Tests: {', '.join(code_summary.tests_added_or_modified)}"
        )

        # Step B: Verify criteria
        analysis_result = await self.verif_agent.verify_requirements(
            requirements=requirements,
            changed_files=changed_files,
            diff_text=diff_text,
            code_summary_notes=code_notes
        )

        return {
            **state,
            "verifications": analysis_result.verifications,
            "code_summary_notes": code_notes,
            "warnings": warnings,
        }

    async def validate_evidence_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Run deterministic validation of evidence quotes and cited files."""
        changed_files = state.get("changed_files", [])
        diff_text = state.get("diff_text", "")
        verifications = state.get("verifications", [])
        warnings = list(state.get("warnings", []))

        valid_file_names = [f.get("filename", "") for f in changed_files if isinstance(f, dict)]

        # Validate each verification deterministically
        validated_verifs = []
        downgrades = 0
        for v in verifications:
            updated_v = EvidenceValidator.validate_verification(
                verification=v,
                valid_file_paths=valid_file_names,
                raw_diff=diff_text
            )
            if updated_v.downgrade_reason:
                downgrades += 1
            validated_verifs.append(updated_v)

        if downgrades > 0:
            warnings.append(
                f"{downgrades} requirement(s) claimed as implemented were downgraded to needs_verification "
                f"because cited files or code quotes were not present in the PR diff."
            )

        return {
            **state,
            "verifications": validated_verifs,
            "warnings": warnings,
        }

    async def calculate_score_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Run deterministic Python scoring engine."""
        requirements = state.get("requirements", [])
        verifications = state.get("verifications", [])

        score = ScoringEngine.calculate_score(requirements, verifications)
        return {
            **state,
            "score": score
        }

    async def generate_report_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Generate markdown report for GitHub PR comment."""
        report = ReportService.build_report(
            jira_key=state.get("jira_key"),
            jira_summary=state.get("jira_summary"),
            jira_url=state.get("jira_url"),
            pr_number=state.get("pr_number", 0),
            pr_title=state.get("pr_title", ""),
            pr_url=state.get("pr_url", ""),
            commit_sha=state.get("commit_sha", ""),
            score=state.get("score") or ScoringEngine.calculate_score([], []),
            requirements=state.get("requirements", []),
            verifications=state.get("verifications", []),
            warnings=state.get("warnings", [])
        )

        return {
            **state,
            "report": report
        }

    async def publish_comment_node(self, state: ReqGuardGraphState) -> ReqGuardGraphState:
        """Publish or update report comment on GitHub PR."""
        report = state.get("report")
        repo = state.get("repo_full_name")
        pr_number = state.get("pr_number")
        warnings = list(state.get("warnings", []))

        if not report or not repo or not pr_number:
            return {
                **state,
                "comment_published": False,
                "warnings": warnings
            }

        try:
            resp = await self.github_client.publish_or_update_comment(
                repo_full_name=repo,
                pr_number=pr_number,
                comment_body=report.markdown_content,
                marker=report.comment_marker
            )
            comment_id = resp.get("id")
            return {
                **state,
                "comment_published": True,
                "comment_id": comment_id,
                "status": "completed"
            }
        except Exception as e:
            logger.error(f"Failed to publish PR comment: {e}")
            warnings.append(f"Could not publish GitHub comment: {str(e)}")
            return {
                **state,
                "comment_published": False,
                "warnings": warnings,
                "status": "comment_publish_failed"
            }
