"""Unit tests for Jira ADF (Atlassian Document Format) parser."""

import pytest
from app.integrations.jira_client import extract_adf_text, parse_adf_node


def test_adf_paragraph_and_text():
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Users must be able to upload images."}
                ]
            }
        ]
    }
    extracted = extract_adf_text(adf)
    assert extracted == "Users must be able to upload images."


def test_adf_bullet_list():
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}
                        ]
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 2"}]}
                        ]
                    }
                ]
            }
        ]
    }
    extracted = extract_adf_text(adf)
    assert "- Item 1" in extracted
    assert "- Item 2" in extracted


def test_adf_plain_string_fallback():
    assert extract_adf_text("Direct string acceptance criteria") == "Direct string acceptance criteria"
    assert extract_adf_text(None) == ""
