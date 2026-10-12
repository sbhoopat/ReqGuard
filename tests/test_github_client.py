"""Unit tests for GitHub client comment idempotency and PR diff handling."""

import pytest
from app.integrations.github_client import GitHubClient


@pytest.mark.asyncio
async def test_find_existing_comment_found(monkeypatch):
    client = GitHubClient(token="fake-token")

    async def mock_get(self, url, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return [
                    {"id": 101, "body": "Normal comment"},
                    {"id": 102, "body": "<!-- reqguard-ai-report -->\n## ReqGuard AI Report"},
                ]
        return MockResp()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    comment_id = await client.find_existing_comment("owner/repo", 1)
    assert comment_id == 102


@pytest.mark.asyncio
async def test_find_existing_comment_not_found(monkeypatch):
    client = GitHubClient(token="fake-token")

    async def mock_get(self, url, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return [{"id": 101, "body": "Normal comment"}]
        return MockResp()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    comment_id = await client.find_existing_comment("owner/repo", 1)
    assert comment_id is None
