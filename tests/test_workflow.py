"""End-to-end integration test of the LangGraph workflow using mocked clients."""

import pytest
from app.graph.workflow import build_reqguard_graph
from app.graph.state import ReqGuardGraphState
from app.integrations.groq_provider import LLMProvider
from app.models.requirement import RequirementCriterion, RequirementList, RequirementStatus
from app.models.analysis import CriterionVerification, RequirementAnalysisResult
from app.agents.code_analysis_agent import CodeChangeSummary


class MockLLMProvider(LLMProvider):
    async def generate_structured(self, system_prompt, user_prompt, response_model, max_retries=2):
        if response_model == RequirementList:
            return RequirementList(
                ticket_key="IMG-245",
                requirements=[
                    RequirementCriterion(id="REQ-1", description="Image upload endpoint implemented", weight=1.0),
                    RequirementCriterion(id="REQ-2", description="File type validation implemented", weight=1.0),
                    RequirementCriterion(id="REQ-3", description="File size limit of 10 MB", weight=1.0),
                ]
            )
        elif response_model == CodeChangeSummary:
            return CodeChangeSummary(
                endpoints_modified=["POST /images"],
                validation_logic=["file extension checked"],
                tests_added_or_modified=["tests/test_upload.py"],
            )
        elif response_model == RequirementAnalysisResult:
            return RequirementAnalysisResult(
                verifications=[
                    CriterionVerification(
                        requirement_id="REQ-1",
                        status=RequirementStatus.IMPLEMENTED,
                        explanation="Endpoint defined in upload.py",
                        changed_file_paths=["app/upload.py"],
                        quoted_code_evidence=['@app.post("/upload")'],
                    ),
                    CriterionVerification(
                        requirement_id="REQ-2",
                        status=RequirementStatus.IMPLEMENTED,
                        explanation="Extension validated",
                        changed_file_paths=["app/upload.py"],
                        quoted_code_evidence=['if ext not in ALLOWED_EXTS:'],
                    ),
                    CriterionVerification(
                        requirement_id="REQ-3",
                        status=RequirementStatus.MISSING,
                        explanation="No file size check found in diff",
                        changed_file_paths=[],
                        quoted_code_evidence=[],
                        suggested_corrective_action="Add 10MB file size limit validation",
                    ),
                ]
            )
        raise ValueError(f"Unhandled response model: {response_model}")


class MockJiraClient:
    async def get_issue(self, issue_key: str):
        return {
            "key": issue_key,
            "summary": "Implement Image Upload API",
            "description": "Users need to upload profile images with validations.",
            "acceptance_criteria": "- Endpoint implemented\n- File type validation\n- File size limit 10MB",
            "subtasks": [],
            "issue_url": f"https://mock-jira.atlassian.net/browse/{issue_key}"
        }


class MockGitHubClient:
    async def get_pull_request_files(self, repo: str, pr_num: int):
        return [{"filename": "app/upload.py"}, {"filename": "tests/test_upload.py"}]

    async def get_pull_request_diff(self, repo: str, pr_num: int):
        return """
diff --git a/app/upload.py b/app/upload.py
+@app.post("/upload")
+def upload():
+    if ext not in ALLOWED_EXTS:
+        raise ValueError("Invalid format")
+    return {"ok": True}
"""

    async def publish_or_update_comment(self, repo_full_name: str, pr_number: int, comment_body: str, marker: str):
        return {"id": 999, "body": comment_body}


@pytest.mark.asyncio
async def test_full_workflow_execution():
    graph = build_reqguard_graph(
        jira_client=MockJiraClient(),
        github_client=MockGitHubClient(),
        llm_provider=MockLLMProvider()
    )

    initial_state: ReqGuardGraphState = {
        "repo_full_name": "acme/service",
        "pr_number": 42,
        "pr_title": "IMG-245: Add image upload",
        "pr_body": "Resolves IMG-245",
        "branch_name": "feature/img-245",
        "commit_sha": "abc123456",
        "pr_url": "https://github.com/acme/service/pull/42",
        "jira_key": "IMG-245",
        "investigation_attempts": 0,
        "warnings": [],
    }

    final_state = await graph.ainvoke(initial_state)

    score = final_state.get("score")
    assert score is not None
    assert score.is_score_available is True
    # 2 implemented (1.0 each) + 1 missing (0.0) out of 3 = 2/3 = 67%
    assert score.coverage_percentage == 67
    assert score.implemented_count == 2
    assert score.missing_count == 1
    assert score.partial_count == 0

    assert final_state.get("comment_published") is True
    assert "## ReqGuard AI" in final_state["report"].markdown_content
    assert "**Estimated coverage:** 67%" in final_state["report"].markdown_content
