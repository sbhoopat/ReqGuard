"""GitHub REST API client for fetching PR diffs, file lists, and publishing comments."""

import logging
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub REST API v3 operations."""

    def __init__(
        self,
        token: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.token = token or settings.GITHUB_TOKEN
        self.api_base = (api_base or settings.GITHUB_API_BASE).rstrip("/")
        self.timeout = timeout

    def _headers(self, accept: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "ReqGuard-AI-Bot",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_pull_request(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR metadata."""
        url = f"{self.api_base}/repos/{repo_full_name}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_pull_request_files(self, repo_full_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch list of changed files in PR."""
        url = f"{self.api_base}/repos/{repo_full_name}/pulls/{pr_number}/files"
        files = []
        page = 1
        per_page = 50

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while page <= 2:  # Bounded to protect rate limits
                resp = await client.get(url, headers=self._headers(), params={"page": page, "per_page": per_page})
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                files.extend(data)
                if len(data) < per_page or len(files) >= settings.MAX_CHANGED_FILES:
                    break
                page += 1

        return files

    async def get_pull_request_diff(self, repo_full_name: str, pr_number: int) -> str:
        """Fetch raw git diff for PR with size limits."""
        url = f"{self.api_base}/repos/{repo_full_name}/pulls/{pr_number}"
        # Accept diff format
        headers = self._headers(accept="application/vnd.github.v3.diff")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            diff_text = resp.text

        if len(diff_text) > settings.MAX_DIFF_CHARACTERS:
            logger.warning(
                f"Diff length {len(diff_text)} exceeds MAX_DIFF_CHARACTERS ({settings.MAX_DIFF_CHARACTERS}). Truncating."
            )
            diff_text = diff_text[:settings.MAX_DIFF_CHARACTERS] + "\n\n... [diff truncated due to size limit]"

        return diff_text

    async def get_file_content(self, repo_full_name: str, path: str, ref: str) -> Optional[str]:
        """Fetch additional read-only source context for a specific file when diff is insufficient."""
        url = f"{self.api_base}/repos/{repo_full_name}/contents/{path}"
        headers = self._headers(accept="application/vnd.github.v3.raw")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, headers=headers, params={"ref": ref})
                if resp.status_code == 200:
                    content = resp.text
                    if len(content) > 10000:
                        content = content[:10000] + "\n... [content truncated]"
                    return content
                return None
            except Exception as e:
                logger.warning(f"Could not retrieve file content for {path} at {ref}: {e}")
                return None

    async def find_existing_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        marker: str = "<!-- reqguard-ai-report -->"
    ) -> Optional[int]:
        """Find existing ReqGuard comment ID on PR to avoid duplicate comments."""
        url = f"{self.api_base}/repos/{repo_full_name}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers(), params={"per_page": 50})
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch PR comments: {resp.status_code}")
                return None
            comments = resp.json()
            for comment in comments:
                body = comment.get("body", "")
                if marker in body:
                    return comment.get("id")
        return None

    async def publish_or_update_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        comment_body: str,
        marker: str = "<!-- reqguard-ai-report -->"
    ) -> Dict[str, Any]:
        """Post a new comment or update existing ReqGuard comment idempotently."""
        existing_comment_id = await self.find_existing_comment(repo_full_name, pr_number, marker)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if existing_comment_id:
                # Update existing comment
                update_url = f"{self.api_base}/repos/{repo_full_name}/issues/comments/{existing_comment_id}"
                logger.info(f"Updating existing comment {existing_comment_id} on {repo_full_name}#{pr_number}")
                resp = await client.patch(
                    update_url,
                    headers=self._headers(),
                    json={"body": comment_body}
                )
                resp.raise_for_status()
                return resp.json()
            else:
                # Create new comment
                create_url = f"{self.api_base}/repos/{repo_full_name}/issues/{pr_number}/comments"
                logger.info(f"Creating new comment on {repo_full_name}#{pr_number}")
                resp = await client.post(
                    create_url,
                    headers=self._headers(),
                    json={"body": comment_body}
                )
                resp.raise_for_status()
                return resp.json()
