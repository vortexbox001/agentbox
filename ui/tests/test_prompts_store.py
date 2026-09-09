"""Tests for prompts_store: listing, reading, and inline creation guards."""
import os

import pytest

import prompts_store as ps


def test_list_ordering_and_fields(settings):
    prompts = ps.list_prompts()
    names = [p["filename"] for p in prompts]
    assert names == sorted(names)
    for p in prompts:
        assert set(p) == {"filename", "size", "modified"}
        assert p["modified"].endswith("Z")


def test_read_prompt(settings):
    content = ps.read_prompt("repo-librarian.md")
    assert isinstance(content, str) and content


def test_read_missing_raises(settings):
    with pytest.raises(FileNotFoundError):
        ps.read_prompt("does-not-exist.md")


def test_create_auto_appends_md(settings):
    name = ps.create_prompt("my-agent", "hello world")
    assert name == "my-agent.md"
    assert ps.exists("my-agent.md")


def test_create_collision_raises(settings):
    ps.create_prompt("dup.md", "content")
    with pytest.raises(FileExistsError):
        ps.create_prompt("dup.md", "other")


def test_create_rejects_traversal(settings):
    for bad in ("../escape.md", "sub/dir.md", "a\\b.md"):
        with pytest.raises(ps.PromptValidationError):
            ps.create_prompt(bad, "content")


def test_create_rejects_bad_name(settings):
    with pytest.raises(ps.PromptValidationError):
        ps.create_prompt("Bad Name.md", "content")


def test_create_rejects_empty_content(settings):
    with pytest.raises(ps.PromptValidationError):
        ps.create_prompt("empty.md", "   ")


def test_create_makes_directory_when_missing(settings, tmp_path, monkeypatch):
    fresh = tmp_path / "no-prompts-yet"
    monkeypatch.setattr(settings, "PROMPTS_DIR", str(fresh))
    assert not fresh.exists()
    ps.create_prompt("first.md", "content")
    assert (fresh / "first.md").is_file()
