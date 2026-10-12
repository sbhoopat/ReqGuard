"""Requirement data models."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RequirementStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    MISSING = "missing"
    NEEDS_VERIFICATION = "needs_verification"


class RequirementCriterion(BaseModel):
    """A structured acceptance criterion decomposed from Jira."""
    id: str = Field(description="Unique requirement ID (e.g., REQ-1)")
    description: str = Field(description="Clear description of the requirement")
    weight: float = Field(default=1.0, ge=0.0, description="Importance or weight of the requirement")
    verification_approach: str = Field(
        default="Inspect changed files, endpoints, logic, and tests",
        description="Suggested verification approach"
    )
    is_ambiguous: bool = Field(default=False, description="Flagged if criterion was ambiguous or missing detail")


class RequirementList(BaseModel):
    """Collection of decomposed requirements from Jira."""
    ticket_key: str
    requirements: List[RequirementCriterion] = Field(default_factory=list)
    has_ambiguous_requirements: bool = False
    notes: Optional[str] = None
