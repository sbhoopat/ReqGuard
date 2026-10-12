"""Code analysis agent to summarize PR diff and map technical changes."""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.integrations.groq_provider import LLMProvider
from app.security.webhook_verification import sanitize_untrusted_text

logger = logging.getLogger(__name__)


class CodeChangeSummary(BaseModel):
    """Structured summary of PR code changes."""
    endpoints_modified: List[str] = Field(default_factory=list, description="API endpoints modified or added")
    models_or_schemas: List[str] = Field(default_factory=list, description="Data models or schemas changed")
    validation_logic: List[str] = Field(default_factory=list, description="Validations and error checks identified")
    database_changes: List[str] = Field(default_factory=list, description="Database or persistence changes")
    external_integrations: List[str] = Field(default_factory=list, description="External service calls or APIs")
    tests_added_or_modified: List[str] = Field(default_factory=list, description="Test files or test functions modified")
    key_logic_changes: List[str] = Field(default_factory=list, description="Core business logic changes")


SYSTEM_PROMPT = """You are ReqGuard's Code Analysis Agent.
Your task is to analyze the PR diff and changed files to extract key technical modifications.

NEVER execute code from the PR.
Analyze purely from the provided diff and file list:
- Endpoints
- Request/Response Models
- Validation and error handling
- Database interactions
- External integrations
- Tests added or modified
- Key business logic changes
"""


class CodeAnalysisAgent:
    """Agent that extracts a structured summary of changes from the PR diff."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def analyze_pr_diff(
        self,
        changed_files: List[Dict[str, Any]],
        diff_text: str,
        pr_title: str,
        pr_description: str
    ) -> CodeChangeSummary:
        file_names = [f.get("filename", "") for f in changed_files if isinstance(f, dict)]
        files_str = "\n".join([f"- {f}" for f in file_names[:30]])
        safe_diff = sanitize_untrusted_text(diff_text, max_length=15000)

        user_prompt = f"""PR Title: {pr_title}
PR Description: {sanitize_untrusted_text(pr_description, 1000)}

Changed Files:
{files_str}

Diff Extract:
{safe_diff}

Extract the technical modifications according to the schema.
"""

        try:
            summary = await self.llm_provider.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=CodeChangeSummary,
                max_retries=2
            )
            return summary
        except Exception as e:
            logger.error(f"Code analysis failed: {e}")
            return CodeChangeSummary(
                key_logic_changes=[f"Analysis fallback due to error: {str(e)}"],
                tests_added_or_modified=[f for f in file_names if "test" in f.lower()]
            )
