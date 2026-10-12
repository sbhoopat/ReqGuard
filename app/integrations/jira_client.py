"""Jira Cloud REST API v3 client with Atlassian Document Format (ADF) parser."""

import logging
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def parse_adf_node(node: Any) -> str:
    """Recursively parse Atlassian Document Format (ADF) nodes into plain text."""
    if not isinstance(node, dict):
        return str(node) if node is not None else ""

    node_type = node.get("type", "")
    text = ""

    # Direct text node
    if node_type == "text":
        return node.get("text", "")

    # Content children recursion
    content = node.get("content", [])
    child_texts = [parse_adf_node(child) for child in content]

    if node_type == "paragraph":
        return "".join(child_texts) + "\n"
    elif node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        return f"{'#' * level} " + "".join(child_texts) + "\n"
    elif node_type == "bulletList":
        return "".join([f"- {item.strip()}\n" for item in child_texts if item.strip()])
    elif node_type == "orderedList":
        return "".join([f"1. {item.strip()}\n" for item in child_texts if item.strip()])
    elif node_type == "listItem":
        return "".join(child_texts)
    elif node_type == "codeBlock":
        language = node.get("attrs", {}).get("language", "")
        return f"```{language}\n" + "".join(child_texts) + "\n```\n"
    elif node_type == "blockquote":
        return "> " + "".join(child_texts) + "\n"
    else:
        return "".join(child_texts)


def extract_adf_text(adf_data: Any) -> str:
    """Convert ADF root object to readable markdown/plain text."""
    if not adf_data:
        return ""
    if isinstance(adf_data, str):
        return adf_data
    if isinstance(adf_data, dict) and adf_data.get("type") == "doc":
        return parse_adf_node(adf_data).strip()
    return str(adf_data)


class JiraCloudClient:
    """Client for interacting with Jira Cloud REST API v3."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.base_url = (base_url or settings.JIRA_BASE_URL).rstrip("/")
        self.email = email or settings.JIRA_USER_EMAIL
        self.api_token = api_token or settings.JIRA_API_TOKEN
        self.timeout = timeout

    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Fetch issue details from Jira Cloud REST API v3.
        Returns extracted key, summary, description, acceptance criteria, and subtasks.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        auth = (self.email, self.api_token)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, auth=auth, headers=headers)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Jira API HTTP error for issue {issue_key}: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Jira API for issue {issue_key}: {e}")
                raise

        fields = data.get("fields", {})
        summary = fields.get("summary", "")
        raw_description = fields.get("description")
        description_text = extract_adf_text(raw_description)

        # Jira Cloud custom fields often store Acceptance Criteria (e.g. customfield_10020 or similar).
        # We search fields for any custom field labeled or containing acceptance criteria, or parse it from description.
        acceptance_criteria_text = ""
        for field_name, field_val in fields.items():
            if "acceptance" in field_name.lower() or "criteria" in field_name.lower():
                if field_val:
                    acceptance_criteria_text += "\n" + extract_adf_text(field_val)

        # Extract subtasks if any
        subtasks = []
        for st in fields.get("subtasks", []):
            st_key = st.get("key", "")
            st_summary = st.get("fields", {}).get("summary", "")
            subtasks.append(f"{st_key}: {st_summary}")

        issue_url = f"{self.base_url}/browse/{issue_key}"

        return {
            "key": issue_key,
            "summary": summary,
            "description": description_text,
            "acceptance_criteria": acceptance_criteria_text.strip(),
            "subtasks": subtasks,
            "issue_url": issue_url,
            "raw_fields": fields
        }
