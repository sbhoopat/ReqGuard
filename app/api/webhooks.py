"""GitHub webhook endpoint handling PR events."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from app.config import settings
from app.security.webhook_verification import verify_github_signature
from app.graph.workflow import build_reqguard_graph
from app.graph.state import ReqGuardGraphState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SUPPORTED_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
):
    """
    Handle GitHub webhook events with HMAC SHA-256 signature verification.
    Listens for 'pull_request' events: opened, reopened, synchronize, ready_for_review.
    """
    payload_bytes = await request.body()

    # 1. Validate HMAC signature
    if not verify_github_signature(
        payload_body=payload_bytes,
        signature_header=x_hub_signature_256,
        secret=settings.GITHUB_WEBHOOK_SECRET,
    ):
        logger.warning("Rejected webhook due to invalid X-Hub-Signature-256.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    # 2. Check event type
    if x_github_event != "pull_request":
        logger.info(f"Ignoring non-pull_request event: {x_github_event}")
        return {"status": "ignored", "reason": f"Event {x_github_event} is not supported"}

    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    action = payload.get("action")
    if action not in SUPPORTED_ACTIONS:
        logger.info(f"Ignoring unsupported PR action: {action}")
        return {"status": "ignored", "reason": f"Action '{action}' is not analyzed"}

    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    repo_full_name = repo_data.get("full_name", "")
    pr_number = pr_data.get("number")
    pr_title = pr_data.get("title", "")
    pr_body = pr_data.get("body", "") or ""
    branch_name = pr_data.get("head", {}).get("ref", "")
    commit_sha = pr_data.get("head", {}).get("sha", "")
    pr_url = pr_data.get("html_url", "")

    # Security: check if repository is in allowed list
    if not settings.is_repo_allowed(repo_full_name):
        logger.warning(f"Repository {repo_full_name} is not in ALLOWED_REPOSITORIES list.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not permitted for automated analysis",
        )

    # Extract Jira ticket key from PR title, body, or branch name
    jira_key = (
        settings.extract_jira_key(pr_title)
        or settings.extract_jira_key(branch_name)
        or settings.extract_jira_key(pr_body)
    )

    initial_state: ReqGuardGraphState = {
        "repo_full_name": repo_full_name,
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

    logger.info(
        f"Triggering ReqGuard workflow for {repo_full_name}#{pr_number} (Jira: {jira_key or 'None'})"
    )

    # MVP runs synchronously for small PRs; designed for future background queue task
    graph = build_reqguard_graph()
    final_state = await graph.ainvoke(initial_state)

    return {
        "status": "processed",
        "repo": repo_full_name,
        "pr_number": pr_number,
        "jira_key": jira_key,
        "coverage_percentage": final_state.get("score", {}).coverage_percentage
        if final_state.get("score")
        else None,
        "comment_published": final_state.get("comment_published", False),
    }
