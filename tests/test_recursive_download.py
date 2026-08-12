"""Tests for recursive page-tree download using a fake client."""

import argparse

import confluence_md
from confluence_md import safe_filename

PAGE_URL = "https://org.atlassian.net/wiki/spaces/ENG/pages/1"


class TestSafeFilename:
    def test_spaces_to_underscores(self):
        assert safe_filename("My Great Page") == "My_Great_Page"

    def test_special_chars_stripped(self):
        assert safe_filename("Q2/Q3: plans? (draft)") == "Q2Q3_plans_draft"

    def test_empty_falls_back(self):
        assert safe_filename("///") == "page"


class FakeClient:
    """Serves a small page tree: root(1) -> child(2) -> grandchild(3)."""

    PAGES = {
        "1": {"title": "Root Page", "body": "<p>root body</p>", "children": ["2"]},
        "2": {"title": "Child Page", "body": "<p>child body</p>", "children": ["3"]},
        "3": {"title": "Grand Child", "body": "<p>grandchild body</p>", "children": []},
    }

    def get_page_by_id(self, page_id, expand=None):
        page = self.PAGES[str(page_id)]
        return {
            "id": str(page_id),
            "title": page["title"],
            "space": {"key": "ENG"},
            "version": {"number": 1},
            "body": {"storage": {"value": page["body"]}},
        }

    def get_page_child_by_type(self, page_id, type="page", start=0, limit=50):
        ids = self.PAGES[str(page_id)]["children"][start : start + limit]
        return {"results": [{"id": i, "title": self.PAGES[i]["title"]} for i in ids]}


def _download(tmp_path, monkeypatch, recursive):
    monkeypatch.setattr(confluence_md, "get_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(page_url=PAGE_URL, output=None, recursive=recursive)
    confluence_md.cmd_download(args)


def test_non_recursive_downloads_single_file(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch, recursive=False)
    assert (tmp_path / "Root_Page.md").is_file()
    assert not (tmp_path / "Root_Page").exists()


def test_recursive_mirrors_page_tree(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch, recursive=True)
    root = tmp_path / "Root_Page.md"
    child = tmp_path / "Root_Page" / "Child_Page.md"
    grandchild = tmp_path / "Root_Page" / "Child_Page" / "Grand_Child.md"
    assert root.is_file()
    assert child.is_file()
    assert grandchild.is_file()
    assert "child body" in child.read_text(encoding="utf-8")
    assert "grandchild body" in grandchild.read_text(encoding="utf-8")


def test_recursive_files_carry_version_markers(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch, recursive=True)
    child = (tmp_path / "Root_Page" / "Child_Page.md").read_text(encoding="utf-8")
    assert child.startswith("<!-- confluence-md page_id=2 version=1 -->")
