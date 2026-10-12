# ReqGuard AI 🛡️

**AI-powered Jira Requirement Compliance Checker for GitHub Pull Requests.**

ReqGuard AI analyzes pull requests against Jira Cloud tickets, evaluates acceptance criteria against implementation evidence, calculates a deterministic compliance score, and publishes an evidence-based compliance report directly as a GitHub PR comment.

---

## 🌟 Key Features

1. **Stateful LangGraph Workflow**: Controlled, predictable multi-node agent orchestration with deterministic guardrails.
2. **Groq LLM Integration**: Fast inference with configurable models (`GROQ_MODEL`) and strict Pydantic JSON schema validation.
3. **Deterministic Python Scoring**: Exact formula calculations:
   $$\text{Coverage \%} = \left(\frac{\sum (\text{weight} \times \text{score})}{\sum \text{weights}}\right) \times 100$$
   *(Implemented = 1.0, Partial = 0.5, Missing = 0.0, Needs Verification = 0.0)*
4. **Deterministic Evidence Validation**: Prevents LLM hallucinations by verifying that cited files exist in the PR and quoted snippets are verbatim matches in the diff. Unsupported claims are downgraded to `needs_verification`.
5. **Jira Cloud REST API v3**: Automatic Atlassian Document Format (ADF) parser for descriptions, acceptance criteria, and subtasks.
6. **GitHub REST API & Webhooks**:
   - HMAC SHA-256 signature verification (`X-Hub-Signature-256`).
   - Idempotent PR commenting (updates existing comments instead of creating duplicates).
7. **Security Hardening**: Untrusted input sanitization, repository restrictions, and bounded retries.

---

## 🏗️ Architecture

```
START 
  │
  ▼
[Fetch Jira] ──(No Key / Failed)──► [Generate Report] ──► [Publish Comment] ──► END
  │
  ▼
[Fetch PR Changes] ──(Failed)──────► [Generate Report] ──► [Publish Comment] ──► END
  │
  ▼
[Extract Criteria] ──(No Criteria)─► [Calculate Score] ──► [Generate Report] ──► [Publish Comment] ──► END
  │
  ▼
[Analyze Requirements]
  │
  ▼
[Validate Evidence] (Deterministic Python Guardrail)
  │
  ▼
[Calculate Score] (Deterministic Python Engine)
  │
  ▼
[Generate Report]
  │
  ▼
[Publish Comment] (Idempotent GitHub API)
  │
  ▼
 END
```

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.12+
- Git
- Docker (optional)

### 1. Windows Setup
```powershell
# Clone and navigate to repository
cd c:\Users\echsa\codebase\ReqGuard

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create .env from template
copy .env.example .env
```

### 2. Linux / macOS Setup
```bash
# Clone and navigate to repository
cd ReqGuard

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
```

### 3. Docker Setup
```bash
docker compose up -d --build
```

---

## ⚙️ Configuration & Credentials

Edit `.env` with your credentials:

### Groq Cloud Setup
1. Sign up at [https://console.groq.com](https://console.groq.com)
2. Generate an API Key and set:
   ```env
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

### Jira Cloud Setup
1. Obtain your Jira base URL (e.g., `https://yourcompany.atlassian.net`).
2. Generate an API token at [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
3. Set:
   ```env
   JIRA_BASE_URL=https://yourcompany.atlassian.net
   JIRA_USER_EMAIL=service-account@example.com
   JIRA_API_TOKEN=your_jira_api_token
   ```

### GitHub Webhook & Token Setup
1. Generate a GitHub Personal Access Token (or GitHub App installation token) with `repo` or `pull_requests:write` + `issues:write` permissions.
2. In your GitHub repository settings, go to **Settings > Webhooks > Add webhook**:
   - **Payload URL**: `https://<your-public-url>/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: Set a random secret string.
   - **Events**: Select **Let me select individual events** -> check **Pull requests**.
3. Set in `.env`:
   ```env
   GITHUB_TOKEN=ghp_your_token_here
   GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
   API_SECRET_KEY=your_manual_api_secret_key
   ```

---

## 🧪 Running the Service

Start the FastAPI application:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Test the health endpoint:
```bash
curl http://localhost:8000/health
```

Run manual PR analysis:
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer <API_SECRET_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"repo_full_name": "owner/repo", "pr_number": 42}'
```

---

## 📋 Example PR Compliance Report

```markdown
<!-- reqguard-ai-report -->
## ReqGuard AI — Requirement Compliance Report

**Jira:** [IMG-245](https://jira.company.com/browse/IMG-245) — *Profile Image Upload API*
**Pull Request:** [#42 feat: implement profile image upload](https://github.com/company/repo/pull/42) (`a7b9c1d`)
**Estimated coverage:** 67%

| Implemented | Partial | Missing | Needs Verification | Total |
| :---: | :---: | :---: | :---: | :---: |
| 2 | 0 | 1 | 0 | 3 |

### Requirements Checklist

- [x] **REQ-1**: Image upload endpoint implemented — ✅ **Implemented**
  - **Analysis:** Dedicated POST endpoint implemented in upload router.
  - **Evidence Files:** `app/routes/upload.py`
  - **Code Quotes (Traceability):**
    > `@router.post("/images/upload")`
  - **Tests Referenced:** `tests/test_upload.py`

- [x] **REQ-2**: File type validation implemented — ✅ **Implemented**
  - **Analysis:** MIME type check ensures only JPEG and PNG are processed.
  - **Evidence Files:** `app/services/image_validator.py`
  - **Code Quotes (Traceability):**
    > `if content_type not in ["image/jpeg", "image/png"]:`

- [ ] **REQ-3**: File size limit of 10 MB — ❌ **Missing**
  - **Analysis:** No file size boundary validation found in diff or handler.
  - **Gaps:** Size validation logic is absent.
  - **Corrective Action:** Add 10MB file size limit check and return HTTP 413.

### Recommended Actions

- **REQ-3**: Add 10MB file size limit check and return HTTP 413.

---
> ℹ️ **Notice:** An exact quote establishes traceability within the diff, not semantic correctness. ReqGuard never assumes tests passed unless explicit CI output confirms it. This report is AI-assisted and intended for engineer review.
```

---

## 🛠️ Troubleshooting Guide

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `401 Unauthorized` on `/webhooks/github` | Webhook secret mismatch or missing header | Verify `GITHUB_WEBHOOK_SECRET` in `.env` matches the secret in GitHub webhook settings. |
| `403 Forbidden` on `/webhooks/github` | Repository is not in `ALLOWED_REPOSITORIES` | Add repository to `ALLOWED_REPOSITORIES` in `.env` or leave empty to allow all. |
| `No Jira key detected` | PR title, body, or branch doesn't match key format | Ensure PR title or branch contains Jira key matching `JIRA_ISSUE_KEY_REGEX` (e.g. `PROJ-123`). |
| `Requirement downgraded to needs_verification` | Cited quote was not found verbatim in PR diff | Evidence validator guardrail detected hallucinated or absent code quote; ensure diff contains code changes. |
| Groq rate limit / timeout | Provider quota reached or network lag | Increase `GROQ_TIMEOUT_SECONDS` or use a different supported model like `llama-3.1-8b-instant`. |
