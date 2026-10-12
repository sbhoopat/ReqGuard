"""Manual PR analysis endpoint protected by authentication."""

import logging
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.config import settings
from app.graph.workflow import build_reqguard_graph
from app.graph.state import ReqGuardGraphState
from app.integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analysis"])


class ManualAnalysisRequest(BaseModel):
    repo_full_name: str = Field(
        ...,
        description="Repository full name, e.g. 'owner/repo'",
        examples=["octocat/Hello-World"]
    )
    pr_number: int = Field(..., ge=1, description="Pull Request number")
    override_jira_key: Optional[str] = Field(
        None,
        description="Optional manual Jira key override (e.g., 'PROJ-123')"
    )

    @field_validator("repo_full_name")
    def validate_repo_name(cls, v: str) -> str:
        parts = v.strip().split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Repository must be in 'owner/repo' format without scheme or URL")
        return v.strip()


def verify_api_token(authorization: str | None = Header(None)) -> str:
    """Validate Bearer API secret key."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be Bearer token",
        )
    token = parts[1]
    if token != settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API secret token",
        )
    return token


@router.post("/analyze")
async def trigger_manual_analysis(
    request_data: ManualAnalysisRequest,
    _token: str = Depends(verify_api_token)
):
    """
    Manually triggers requirement compliance analysis for an authorized repository PR.
    Protected with Bearer API_SECRET_KEY.
    """
    repo = request_data.repo_full_name
    pr_number = request_data.pr_number

    # Repository restriction
    if not settings.is_repo_allowed(repo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Repository '{repo}' is not allowed",
        )

    # Fetch PR details from GitHub to initialize state
    gh_client = GitHubClient()
    try:
        pr_info = await gh_client.get_pull_request(repo, pr_number)
    except Exception as e:
        logger.error(f"Failed to fetch PR #{pr_number} from {repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not retrieve PR #{pr_number} from GitHub: {str(e)}",
        )

    pr_title = pr_info.get("title", "")
    pr_body = pr_info.get("body", "") or ""
    branch_name = pr_info.get("head", {}).get("ref", "")
    commit_sha = pr_info.get("head", {}).get("sha", "")
    pr_url = pr_info.get("html_url", "")

    # Resolve Jira key (override or auto-detect)
    jira_key = request_data.override_jira_key or (
        settings.extract_jira_key(pr_title)
        or settings.extract_jira_key(branch_name)
        or settings.extract_jira_key(pr_body)
    )

    initial_state: ReqGuardGraphState = {
        "repo_full_name": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "branch_name": branch_name,
        "commit_sha": commit_sha,
        "pr_url": pr_url,
        "jira_key": jira_key,
        "investigation_attempts": 0,
        "warnings": [],
        "changed_files": [],
        "diff_text": "",
        "requirements": [],
        "verifications": [],
    }

    graph = build_reqguard_graph(github_client=gh_client)
    final_state = await graph.ainvoke(initial_state)

    score = final_state.get("score")
    report = final_state.get("report")

    return {
        "status": "success",
        "repo": repo,
        "pr_number": pr_number,
        "jira_key": jira_key,
        "coverage_percentage": score.coverage_percentage if score else None,
        "score_summary": {
            "implemented": score.implemented_count if score else 0,
            "partial": score.partial_count if score else 0,
            "missing": score.missing_count if score else 0,
            "needs_verification": score.needs_verification_count if score else 0,
        } if score else {},
        "comment_published": final_state.get("comment_published", False),
        "comment_id": final_state.get("comment_id"),
        "warnings": final_state.get("warnings", []),
        "report_markdown": report.markdown_content if report else None,
    }
