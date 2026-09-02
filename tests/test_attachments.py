"""Tests for fetching a page's attachments across API pages."""

import confluence_md
from confluence_md import get_page_attachments


class PagedClient:
    """Serves attachments in server-sized pages, like Confluence Cloud.

    The server ignores the requested limit above its own cap and signals
    remaining pages through "_links.next".
    """

    CAP = 2

    def __init__(self, titles):
        self.titles = titles
        self.calls = []

    def get_attachments_from_content(self, page_id, start=0, limit=50):
        self.calls.append((start, limit))
        page = self.titles[start : start + self.CAP]
        links = {"next": "/next"} if start + self.CAP < len(self.titles) else {}
        return {"results": [{"title": t} for t in page], "size": len(page), "_links": links}


class ListClient:
    """Returns a plain list, as older client versions do."""

    def __init__(self, titles):
        self.titles = titles

    def get_attachments_from_content(self, page_id, start=0, limit=50):
        return [{"title": t} for t in self.titles[start : start + limit]]


class TestGetPageAttachments:
    def test_follows_next_links_past_server_cap(self):
        client = PagedClient(["a.png", "b.png", "c.png", "d.png", "e.png"])
        titles = [a["title"] for a in get_page_attachments(client, "1")]
        assert titles == ["a.png", "b.png", "c.png", "d.png", "e.png"]
        assert [start for start, _ in client.calls] == [0, 2, 4]

    def test_single_page_makes_one_call(self):
        client = PagedClient(["a.png"])
        assert [a["title"] for a in get_page_attachments(client, "1")] == ["a.png"]
        assert len(client.calls) == 1

    def test_empty_page(self):
        assert get_page_attachments(PagedClient([]), "1") == []

    def test_plain_list_response_pages_by_limit(self):
        titles = [f"{i}.png" for i in range(120)]
        got = [a["title"] for a in get_page_attachments(ListClient(titles), "1")]
        assert got == titles


class ManyAttachmentsClient(PagedClient):
    """A paged client whose attachments can also be downloaded."""

    def get_attachments_from_content(self, page_id, start=0, limit=50):
        response = super().get_attachments_from_content(page_id, start, limit)
        for attachment in response["results"]:
            attachment["_links"] = {"download": f"/download/{attachment['title']}"}
        return response

    def get(self, path, not_json_response=False):
        return b"DATA"


def test_download_finds_attachment_beyond_first_page(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(confluence_md, "CONFLUENCE_URL", "https://org.atlassian.net/wiki")
    client = ManyAttachmentsClient(["a.png", "b.png", "last.png"])
    page = {
        "id": "1",
        "title": "Page",
        "space": {"key": "ENG"},
        "version": {"number": 1},
        "body": {
            "storage": {
                "value": '<ac:image ac:alt="a"><ri:attachment ri:filename="last.png" /></ac:image>'
            }
        },
    }
    confluence_md.download_page(client, page, tmp_path / "Page.md")
    assert (tmp_path / "Page_attachments" / "last.png").read_bytes() == b"DATA"
    assert "not found" not in capsys.readouterr().out
