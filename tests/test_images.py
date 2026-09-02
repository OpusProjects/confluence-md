"""Tests for image conversion in both pipelines."""

import confluence_md
from confluence_md import confluence_storage_to_md, md_to_confluence_storage


class TestMarkdownToStorage:
    def test_local_image_becomes_attachment_macro(self):
        out = md_to_confluence_storage("![diagram](images/diagram.png)")
        assert '<ac:image ac:alt="diagram">' in out
        assert '<ri:attachment ri:filename="diagram.png" />' in out

    def test_local_image_path_collected(self):
        paths: list[str] = []
        md_to_confluence_storage("![a](img/one.png)\n\n![b](two.jpg)", paths)
        assert paths == ["img/one.png", "two.jpg"]

    def test_percent_encoded_path_decoded(self):
        paths: list[str] = []
        out = md_to_confluence_storage("![a](img/my%20file%20%281%29.png)", paths)
        assert '<ri:attachment ri:filename="my file (1).png" />' in out
        assert paths == ["img/my file (1).png"]

    def test_external_image_becomes_url_macro(self):
        out = md_to_confluence_storage("![logo](https://example.com/logo.svg)")
        assert '<ri:url ri:value="https://example.com/logo.svg" />' in out
        assert "ri:attachment" not in out

    def test_external_image_not_collected(self):
        paths: list[str] = []
        md_to_confluence_storage("![x](https://example.com/x.png)", paths)
        assert paths == []


class TestStorageToMarkdown:
    def test_attachment_image_with_prefix(self):
        storage = '<ac:image ac:alt="diagram"><ri:attachment ri:filename="d.png" /></ac:image>'
        out = confluence_storage_to_md(storage, attachment_prefix="Page_attachments/")
        assert "![diagram](Page_attachments/d.png)" in out

    def test_attachment_image_alt_falls_back_to_filename(self):
        storage = '<ac:image><ri:attachment ri:filename="chart.png" /></ac:image>'
        out = confluence_storage_to_md(storage)
        assert "![chart.png](chart.png)" in out

    def test_attachment_filename_percent_encoded_in_link(self):
        storage = '<ac:image ac:alt="a"><ri:attachment ri:filename="my file (1).png" /></ac:image>'
        out = confluence_storage_to_md(storage, attachment_prefix="P_attachments/")
        assert "![a](P_attachments/my%20file%20%281%29.png)" in out

    def test_external_image_keeps_url(self):
        storage = (
            '<ac:image ac:alt="logo"><ri:url ri:value="https://example.com/l.svg" /></ac:image>'
        )
        out = confluence_storage_to_md(storage)
        assert "![logo](https://example.com/l.svg)" in out

    def test_image_inside_paragraph(self):
        storage = '<p>see <ac:image><ri:attachment ri:filename="x.png" /></ac:image> here</p>'
        out = confluence_storage_to_md(storage)
        assert "see ![x.png](x.png) here" in out


class TestRoundTrip:
    def test_local_image_round_trip(self):
        md = "![diagram](diagram.png)"
        storage = md_to_confluence_storage(md)
        assert "![diagram](diagram.png)" in confluence_storage_to_md(storage)

    def test_external_image_round_trip(self):
        md = "![logo](https://example.com/logo.svg)"
        storage = md_to_confluence_storage(md)
        assert md in confluence_storage_to_md(storage)

    def test_filename_with_spaces_round_trip(self):
        storage = '<ac:image ac:alt="a"><ri:attachment ri:filename="my file.png" /></ac:image>'
        md = confluence_storage_to_md(storage, attachment_prefix="P_attachments/")
        paths: list[str] = []
        out = md_to_confluence_storage(md, paths)
        assert '<ri:attachment ri:filename="my file.png" />' in out
        assert paths == ["P_attachments/my file.png"]


class AttachmentClient:
    """Serves one page whose only attachment has a space in its name."""

    def get_attachments_from_content(self, page_id, start=0, limit=50):
        return {
            "results": [{"title": "my file.png", "_links": {"download": "/download/my%20file.png"}}]
        }

    def get(self, path, not_json_response=False):
        assert path == "/download/my%20file.png"
        return b"PNGDATA"


def test_download_saves_attachment_with_spaces_in_name(tmp_path, monkeypatch):
    monkeypatch.setattr(confluence_md, "CONFLUENCE_URL", "https://org.atlassian.net/wiki")
    page = {
        "id": "1",
        "title": "Page",
        "space": {"key": "ENG"},
        "version": {"number": 1},
        "body": {
            "storage": {
                "value": '<ac:image ac:alt="a"><ri:attachment ri:filename="my file.png" /></ac:image>'
            }
        },
    }
    confluence_md.download_page(AttachmentClient(), page, tmp_path / "Page.md")
    assert (tmp_path / "Page_attachments" / "my file.png").read_bytes() == b"PNGDATA"
    md = (tmp_path / "Page.md").read_text(encoding="utf-8")
    assert "![a](Page_attachments/my%20file.png)" in md
