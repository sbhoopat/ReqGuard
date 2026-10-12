"""Configuration management using Pydantic Settings."""

import re
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Server settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    API_SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")
    GITHUB_WEBHOOK_SECRET: str = Field(default="dev-webhook-secret")
    ALLOWED_REPOSITORIES: str = Field(default="")  # Comma-separated list e.g. "org/repo1,org/repo2"

    # Groq LLM Configuration
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="openai/gpt-oss-120b")
    GROQ_TEMPERATURE: float = Field(default=0.0)
    GROQ_MAX_TOKENS: int = Field(default=4096)
    GROQ_TIMEOUT_SECONDS: float = Field(default=60.0)

    # GitHub Integration
    GITHUB_TOKEN: str = Field(default="")
    GITHUB_API_BASE: str = Field(default="https://api.github.com")

    # Jira Cloud Integration
    JIRA_BASE_URL: str = Field(default="https://example.atlassian.net")
    JIRA_USER_EMAIL: str = Field(default="user@example.com")
    JIRA_API_TOKEN: str = Field(default="")

    # Jira Regex Pattern
    JIRA_ISSUE_KEY_REGEX: str = Field(default=r"([A-Z][A-Z0-9]+-\d+)")

    # Analysis Limits & Guardrails
    MAX_DIFF_CHARACTERS: int = Field(default=60000)
    MAX_CHANGED_FILES: int = Field(default=50)
    MAX_INVESTIGATION_ATTEMPTS: int = Field(default=2)

    @property
    def allowed_repositories_list(self) -> List[str]:
        if not self.ALLOWED_REPOSITORIES.strip():
            return []
        return [repo.strip().lower() for repo in self.ALLOWED_REPOSITORIES.split(",") if repo.strip()]

    def is_repo_allowed(self, repo_full_name: str) -> bool:
        allowed = self.allowed_repositories_list
        if not allowed:
            return True
        return repo_full_name.strip().lower() in allowed

    def extract_jira_key(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(self.JIRA_ISSUE_KEY_REGEX, text)
        if match:
            return match.group(1).upper()
        return None


# Global settings instance
settings = Settings()
