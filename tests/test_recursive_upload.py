"""Tests for recursive upload (folder sync) using a fake client."""

import argparse

import pytest

import confluence_md
from confluence_md import split_leading_h1

PARENT_URL = "https://org.atlassian.net/wiki/spaces/ENG/pages/100"


class TestSplitLeadingH1:
    def test_h1_extracted_and_stripped(self):
        title, rest = split_leading_h1("# My Page\n\nbody text")
        assert title == "My Page"
        assert rest == "body text"

    def test_h1_alone_without_trailing_newline(self):
        title, rest = split_leading_h1("# My Page")
        assert title == "My Page"
        assert rest == ""

    def test_no_h1(self):
        title, rest = split_leading_h1("just body")
        assert title is None
        assert rest == "just body"

    def test_h2_not_taken(self):
        title, rest = split_leading_h1("## Section\n\nbody")
        assert title is None


class FakeClient:
    """Records page creation/update calls; serves lookups from a registry."""

    def __init__(self, existing_by_title=None, versions=None):
        self.existing_by_title = existing_by_title or {}
        self.versions = versions or {}
        self.created = []  # (title, parent_id)
        self.updated = []  # (page_id, title)
        self._next_id = 200

    def get_page_by_title(self, space, title):
        page_id = self.existing_by_title.get(title)
        return {"id": page_id} if page_id else None

    def get_page_by_id(self, page_id, expand=None):
        return {"id": str(page_id), "version": {"number": self.versions.get(str(page_id), 1)}}

    def create_page(self, space, title, body, parent_id, representation):
        self._next_id += 1
        self.created.append((title, parent_id))
        return {"id": str(self._next_id)}

    def update_page(self, page_id, title, body, representation):
        self.updated.append((str(page_id), title))


def _upload(monkeypatch, client, folder, force=False):
    monkeypatch.setattr(confluence_md, "get_client", lambda: client)
    args = argparse.Namespace(
        file=str(folder), parent_url=PARENT_URL, title=None, recursive=True, force=force
    )
    confluence_md.cmd_upload(args)


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "Alpha.md").write_text("# Alpha Page\n\nalpha body", encoding="utf-8")
    sub = tmp_path / "Alpha"
    sub.mkdir()
    (sub / "Beta.md").write_text("# Beta Page\n\nbeta body", encoding="utf-8")
    return tmp_path


def test_tree_created_with_hierarchy(tree, monkeypatch):
    client = FakeClient()
    _upload(monkeypatch, client, tree)

    assert ("Alpha Page", "100") in client.created
    alpha_id = "201"  # first created page id from the fake
    assert ("Beta Page", alpha_id) in client.created
    assert client.updated == []


def test_existing_title_updated_not_created(tree, monkeypatch):
    client = FakeClient(existing_by_title={"Alpha Page": "55"})
    _upload(monkeypatch, client, tree)

    assert ("55", "Alpha Page") in client.updated
    assert all(title != "Alpha Page" for title, _ in client.created)
    # Beta is created under the existing Alpha page.
    assert ("Beta Page", "55") in client.created


def test_marker_targets_page_and_guards_version(tmp_path, monkeypatch, capsys):
    md = tmp_path / "Doc.md"
    md.write_text(
        "<!-- confluence-md page_id=77 version=2 -->\n# Doc\n\nbody",
        encoding="utf-8",
    )
    client = FakeClient(versions={"77": 5})
    _upload(monkeypatch, client, tmp_path)

    assert client.updated == []
    assert "version 2 -> 5" in capsys.readouterr().out


def test_marker_conflict_overridden_by_force(tmp_path, monkeypatch):
    md = tmp_path / "Doc.md"
    md.write_text(
        "<!-- confluence-md page_id=77 version=2 -->\n# Doc\n\nbody",
        encoding="utf-8",
    )
    client = FakeClient(versions={"77": 5})
    _upload(monkeypatch, client, tmp_path, force=True)

    assert ("77", "Doc") in client.updated


def test_title_falls_back_to_filename(tmp_path, monkeypatch):
    (tmp_path / "Release_Notes.md").write_text("no heading here", encoding="utf-8")
    client = FakeClient()
    _upload(monkeypatch, client, tmp_path)

    assert ("Release Notes", "100") in client.created
