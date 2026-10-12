"""LangGraph workflow definition with conditional branching and robust execution."""

import logging
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, START, END

from app.graph.state import ReqGuardGraphState
from app.graph.nodes import WorkflowNodes
from app.integrations.jira_client import JiraCloudClient
from app.integrations.github_client import GitHubClient
from app.integrations.groq_provider import LLMProvider, GroqProvider

logger = logging.getLogger(__name__)


def should_continue_after_jira(state: ReqGuardGraphState) -> str:
    """Conditional router: if no Jira key or Jira fetch failed, jump to report generation."""
    if not state.get("jira_key"):
        return "generate_report"
    if state.get("status") == "jira_fetch_failed":
        return "generate_report"
    return "fetch_pr_changes"


def should_continue_after_diff(state: ReqGuardGraphState) -> str:
    """Conditional router: if diff is missing or PR fetch failed, jump to report."""
    if state.get("status") == "github_fetch_failed":
        return "generate_report"
    return "extract_criteria"


def should_continue_after_criteria(state: ReqGuardGraphState) -> str:
    """Conditional router: if no criteria extracted, jump to calculate score."""
    requirements = state.get("requirements", [])
    if not requirements:
        return "calculate_score"
    return "analyze_requirements"


def build_reqguard_graph(
    jira_client: Optional[JiraCloudClient] = None,
    github_client: Optional[GitHubClient] = None,
    llm_provider: Optional[LLMProvider] = None
) -> StateGraph:
    """
    Constructs the ReqGuard LangGraph workflow graph:
    START -> fetch_jira -> fetch_pr_changes -> extract_criteria ->
    analyze_requirements -> validate_evidence -> calculate_score ->
    generate_report -> publish_comment -> END
    """
    jira_client = jira_client or JiraCloudClient()
    github_client = github_client or GitHubClient()
    llm_provider = llm_provider or GroqProvider()

    nodes = WorkflowNodes(
        jira_client=jira_client,
        github_client=github_client,
        llm_provider=llm_provider
    )

    builder = StateGraph(ReqGuardGraphState)

    # Register nodes
    builder.add_node("fetch_jira", nodes.fetch_jira_node)
    builder.add_node("fetch_pr_changes", nodes.fetch_pr_changes_node)
    builder.add_node("extract_criteria", nodes.extract_criteria_node)
    builder.add_node("analyze_requirements", nodes.analyze_requirements_node)
    builder.add_node("validate_evidence", nodes.validate_evidence_node)
    builder.add_node("calculate_score", nodes.calculate_score_node)
    builder.add_node("generate_report", nodes.generate_report_node)
    builder.add_node("publish_comment", nodes.publish_comment_node)

    # Add edges and conditional branches
    builder.add_edge(START, "fetch_jira")

    builder.add_conditional_edges(
        "fetch_jira",
        should_continue_after_jira,
        {
            "fetch_pr_changes": "fetch_pr_changes",
            "generate_report": "generate_report",
        }
    )

    builder.add_conditional_edges(
        "fetch_pr_changes",
        should_continue_after_diff,
        {
            "extract_criteria": "extract_criteria",
            "generate_report": "generate_report",
        }
    )

    builder.add_conditional_edges(
        "extract_criteria",
        should_continue_after_criteria,
        {
            "analyze_requirements": "analyze_requirements",
            "calculate_score": "calculate_score",
        }
    )

    builder.add_edge("analyze_requirements", "validate_evidence")
    builder.add_edge("validate_evidence", "calculate_score")
    builder.add_edge("calculate_score", "generate_report")
    builder.add_edge("generate_report", "publish_comment")
    builder.add_edge("publish_comment", END)

    return builder.compile()
