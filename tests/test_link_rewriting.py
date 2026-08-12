"""Tests for internal page-link rewriting in recursive downloads."""

import argparse

import confluence_md
from confluence_md import confluence_storage_to_md

PAGE_URL = "https://org.atlassian.net/wiki/spaces/ENG/pages/1"


def _link(title, label=None):
    body = (
        f"<ac:plain-text-link-body><![CDATA[{label}]]></ac:plain-text-link-body>" if label else ""
    )
    return f'<ac:link><ri:page ri:content-title="{title}" />{body}</ac:link>'


class TestPlaceholderEmission:
    def test_placeholder_when_resolving(self):
        out = confluence_storage_to_md(
            f"<p>see {_link('Other Page', 'the docs')}</p>", resolve_page_links=True
        )
        assert "[the docs](confluence-page://Other%20Page)" in out

    def test_plain_text_by_default(self):
        out = confluence_storage_to_md(f"<p>see {_link('Other Page', 'the docs')}</p>")
        assert "the docs" in out
        assert "confluence-page://" not in out


class FakeClient:
    """Tree root(1) -> child(2); pages link to each other and outside."""

    PAGES = {
        "1": {
            "title": "Root Page",
            "body": f"<p>go to {_link('Child Page', 'the child')} or {_link('Missing Page', 'elsewhere')}</p>",
            "children": ["2"],
        },
        "2": {
            "title": "Child Page",
            "body": f"<p>back to {_link('Root Page', 'the root')}</p>",
            "children": [],
        },
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


def _download(tmp_path, monkeypatch, recursive=True):
    monkeypatch.setattr(confluence_md, "get_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(page_url=PAGE_URL, output=None, recursive=recursive)
    confluence_md.cmd_download(args)


def test_links_within_tree_become_relative(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch)
    root = (tmp_path / "Root_Page.md").read_text(encoding="utf-8")
    child = (tmp_path / "Root_Page" / "Child_Page.md").read_text(encoding="utf-8")
    assert "[the child](Root_Page/Child_Page.md)" in root
    assert "[the root](../Root_Page.md)" in child


def test_links_outside_tree_become_plain_text(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch)
    root = (tmp_path / "Root_Page.md").read_text(encoding="utf-8")
    assert "elsewhere" in root
    assert "confluence-page://" not in root
    assert "[elsewhere]" not in root


def test_non_recursive_keeps_plain_text(tmp_path, monkeypatch):
    _download(tmp_path, monkeypatch, recursive=False)
    root = (tmp_path / "Root_Page.md").read_text(encoding="utf-8")
    assert "the child" in root
    assert "confluence-page://" not in root
