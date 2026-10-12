"""Service for generating the GitHub PR markdown compliance report."""

from typing import List, Optional
from app.models.analysis import ComplianceReport, ComplianceScore, CriterionVerification
from app.models.requirement import RequirementCriterion, RequirementStatus


class ReportService:
    """Formats requirement analysis results into a clear GitHub markdown comment."""

    COMMENT_MARKER = "<!-- reqguard-ai-report -->"

    @classmethod
    def generate_markdown(
        cls,
        jira_key: Optional[str],
        jira_summary: Optional[str],
        jira_url: Optional[str],
        pr_number: int,
        pr_title: str,
        pr_url: str,
        commit_sha: str,
        score: ComplianceScore,
        requirements: List[RequirementCriterion],
        verifications: List[CriterionVerification],
        warnings: Optional[List[str]] = None
    ) -> str:
        warnings = warnings or []
        short_sha = commit_sha[:7] if commit_sha else "HEAD"

        # Determine badge color based on coverage score
        if score.is_score_available and score.coverage_percentage is not None:
            pct = score.coverage_percentage
            if pct >= 80:
                score_color = "brightgreen"
            elif pct >= 50:
                score_color = "yellow"
            elif pct > 0:
                score_color = "orange"
            else:
                score_color = "red"
            coverage_badge = f"![Coverage](https://img.shields.io/badge/Coverage-{pct}%25-{score_color}?style=for-the-badge&logo=target)"
        else:
            coverage_badge = "![Coverage](https://img.shields.io/badge/Coverage-N%2FA-lightgrey?style=for-the-badge)"

        reqguard_badge = "![ReqGuard AI](https://img.shields.io/badge/ReqGuard-AI%20Checked-blueviolet?style=for-the-badge&logo=shield)"

        impl_badge = f"![Implemented](https://img.shields.io/badge/Implemented-{score.implemented_count}-2ea44f?style=flat-square)"
        part_badge = f"![Partial](https://img.shields.io/badge/Partial-{score.partial_count}-dfb317?style=flat-square)"
        miss_badge = f"![Missing](https://img.shields.io/badge/Missing-{score.missing_count}-d73a49?style=flat-square)"
        need_badge = f"![Needs Verification](https://img.shields.io/badge/Needs%20Verification-{score.needs_verification_count}-0366d6?style=flat-square)"

        lines = [
            cls.COMMENT_MARKER,
            f"## 🛡️ ReqGuard AI — Requirement Compliance Report\n",
            f"{reqguard_badge} {coverage_badge}\n",
        ]

        # Metadata table
        jira_link_str = f"[{jira_key}]({jira_url})" if (jira_key and jira_url) else (jira_key or "N/A")
        if jira_summary:
            jira_link_str += f" — **{jira_summary}**"

        lines.append(f"> 🎯 **Jira Issue:** {jira_link_str}")
        lines.append(f"> 🔀 **Pull Request:** [#{pr_number} {pr_title}]({pr_url}) (`{short_sha}`)\n")

        # Visual Score Card Table
        lines.append("### 📊 Compliance Summary\n")
        lines.append(f"| Status | Count | Indicator |")
        lines.append(f"| :--- | :---: | :--- |")
        lines.append(f"| **Implemented** | `{score.implemented_count}` | {impl_badge} |")
        lines.append(f"| **Partial** | `{score.partial_count}` | {part_badge} |")
        lines.append(f"| **Missing** | `{score.missing_count}` | {miss_badge} |")
        lines.append(f"| **Needs Verification** | `{score.needs_verification_count}` | {need_badge} |")
        lines.append(f"| **Total Evaluated** | `{score.total_requirements}` | `100% of Jira Criteria` |\n")

        # Requirement Checklist
        lines.append("### 📋 Requirements Verification Breakdown\n")

        if not requirements:
            lines.append("> ⚠️ *No acceptance criteria found in Jira ticket or could not be decomposed.*\n")
        else:
            verif_map = {v.requirement_id: v for v in verifications}

            for req in requirements:
                v = verif_map.get(req.id)
                status = v.status if v else RequirementStatus.NEEDS_VERIFICATION

                # Badges and check icons
                if status == RequirementStatus.IMPLEMENTED:
                    checkbox = "[x]"
                    status_badge = "![Implemented](https://img.shields.io/badge/IMPLEMENTED-2ea44f?style=flat-square)"
                elif status == RequirementStatus.PARTIAL:
                    checkbox = "[~]"
                    status_badge = "![Partial](https://img.shields.io/badge/PARTIAL-dfb317?style=flat-square)"
                elif status == RequirementStatus.MISSING:
                    checkbox = "[ ]"
                    status_badge = "![Missing](https://img.shields.io/badge/MISSING-d73a49?style=flat-square)"
                else:
                    checkbox = "[?]"
                    status_badge = "![Needs Verification](https://img.shields.io/badge/NEEDS_VERIFICATION-0366d6?style=flat-square)"

                weight_note = f" `(Weight: {req.weight})`" if req.weight != 1.0 else ""
                lines.append(f"- {checkbox} **`{req.id}`**: {req.description}{weight_note} &nbsp; {status_badge}")

                if v:
                    lines.append(f"  <details><summary>🔍 <b>View Evidence & Evaluation Details</b></summary>")
                    lines.append(f"  <br/>\n")
                    lines.append(f"  - **Analysis:** {v.explanation}")

                    if v.changed_file_paths:
                        files_str = ", ".join([f"`{f}`" for f in v.changed_file_paths])
                        lines.append(f"  - **Evidence Files:** 📁 {files_str}")

                    if v.quoted_code_evidence:
                        lines.append("  - **Code Quotes (Traceability):**")
                        for q in v.quoted_code_evidence[:3]:
                            lines.append(f"    ```\n    {q.strip()}\n    ```")

                    if v.relevant_tests:
                        tests_str = ", ".join([f"`{t}`" for t in v.relevant_tests])
                        lines.append(f"  - **Tests Referenced:** 🧪 {tests_str}")

                    if v.identified_gaps:
                        gaps_str = "; ".join(v.identified_gaps)
                        lines.append(f"  - **Identified Gaps:** ⚠️ *{gaps_str}*")

                    if v.suggested_corrective_action:
                        lines.append(f"  - **Suggested Action:** 💡 {v.suggested_corrective_action}")

                    if v.downgrade_reason:
                        lines.append(f"  - **Evidence Guardrail Downgrade:** 🔻 `{v.downgrade_reason}`")

                    lines.append(f"  </details>\n")

        # Recommended Actions
        all_actions = []
        for v in verifications:
            if v.suggested_corrective_action and v.status in (
                RequirementStatus.PARTIAL,
                RequirementStatus.MISSING,
                RequirementStatus.NEEDS_VERIFICATION,
            ):
                all_actions.append(f"- 🔹 **`{v.requirement_id}`**: {v.suggested_corrective_action}")

        if all_actions:
            lines.append("### 💡 Recommended Actions\n")
            lines.extend(all_actions)
            lines.append("")

        # Warnings / Limitations
        if warnings:
            lines.append("### ⚠️ Notices & Warnings\n")
            for w in warnings:
                lines.append(f"- 🔸 {w}")
            lines.append("")

        # Professional Disclaimer Footer
        lines.append("---")
        lines.append(
            "> ℹ️ **Audit Notice:** *An exact code quote establishes syntactic traceability within the diff, not semantic correctness. "
            "ReqGuard never assumes test execution passed unless explicit CI output confirms it. "
            "This report is AI-assisted and designed for engineer code review.*"
        )

        return "\n".join(lines)

    @classmethod
    def build_report(
        cls,
        jira_key: Optional[str],
        jira_summary: Optional[str],
        jira_url: Optional[str],
        pr_number: int,
        pr_title: str,
        pr_url: str,
        commit_sha: str,
        score: ComplianceScore,
        requirements: List[RequirementCriterion],
        verifications: List[CriterionVerification],
        warnings: Optional[List[str]] = None
    ) -> ComplianceReport:
        markdown = cls.generate_markdown(
            jira_key=jira_key,
            jira_summary=jira_summary,
            jira_url=jira_url,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_url=pr_url,
            commit_sha=commit_sha,
            score=score,
            requirements=requirements,
            verifications=verifications,
            warnings=warnings
        )

        return ComplianceReport(
            jira_key=jira_key,
            jira_summary=jira_summary,
            jira_url=jira_url,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_url=pr_url,
            commit_sha=commit_sha,
            score=score,
            verifications=verifications,
            requirements=requirements,
            warnings=warnings or [],
            markdown_content=markdown,
            comment_marker=cls.COMMENT_MARKER
        )
